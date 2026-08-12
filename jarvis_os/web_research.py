"""Small, dependency-light web search client for answer grounding.

Every source here is a documented public API. The previous HTML scraper stopped
working when DuckDuckGo began returning a bot-challenge page instead of results,
and defeating that check is not something this assistant should do.

Without a key the assistant relies on encyclopedic sources, which answer
"what is X" style questions well but cover breaking news poorly. Set
SERPAPI_API_KEY for full current-events coverage.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import requests

from .diagnostics_log import failure


USER_AGENT = "JARVIS-OS/7.0 (personal desktop assistant)"

# Encyclopedic endpoints match on topic, not on question wording. Searching
# "what is the meaning of ai" verbatim returns articles that merely contain
# those words, so reduce a spoken question to the thing being asked about.
_QUESTION_LEAD = re.compile(
    r"""^\s*(?:
        (?:what|who|which|where)\s+(?:is|are|was|were)\s+(?:the\s+)?
            (?:meaning|definition|purpose|point|idea)\s+(?:of|behind)\s+
      | (?:what|who|which)\s+(?:is|are|was|were)\s+(?:(?:a|an|the)\s+)?
      | (?:tell\s+me|explain|describe)\s+(?:about\s+)?(?:(?:a|an|the)\s+)?
      | define\s+(?:(?:a|an|the)\s+)?
      | (?:the\s+)?meaning\s+of\s+
    )""",
    re.IGNORECASE | re.VERBOSE,
)

_ABBREVIATIONS = {
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "llm": "large language model",
    "vpn": "virtual private network",
    "gpu": "graphics processing unit",
    "cpu": "central processing unit",
    "api": "application programming interface",
}


def topic_of(query: str) -> str:
    """Reduce a spoken question to the subject an encyclopedia can look up."""
    value = re.sub(r"\s+", " ", str(query)).strip().strip("?.!")
    value = _QUESTION_LEAD.sub("", value).strip()
    value = re.sub(r"^(?:a|an|the)\s+", "", value, flags=re.IGNORECASE).strip()
    if not value:
        return str(query).strip()
    return _ABBREVIATIONS.get(value.lower(), value)


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str

    def passage(self) -> str:
        return f"SOURCE: {self.title}\nURL: {self.url}\nSUMMARY: {self.snippet}".strip()


class WebResearch:
    def __init__(self, session=requests, timeout: int = 12):
        self.session = session
        self.timeout = timeout

    @property
    def has_full_web_access(self) -> bool:
        return bool(os.getenv("SERPAPI_API_KEY", "").strip())

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        key = os.getenv("SERPAPI_API_KEY", "").strip()
        if key:
            results = self._collect(self._serpapi, query, limit, key)
            if results:
                return results[:limit]
        topic = topic_of(query)
        results = self._collect(self._instant_answer, topic, limit)
        if len(results) < limit:
            results.extend(self._collect(self._wikipedia, topic, limit - len(results)))
        return self._deduplicate(results)[:limit]

    @staticmethod
    def _collect(fetch, *args) -> list[SearchResult]:
        """One failing provider must not take down the whole answer."""
        try:
            return list(fetch(*args))
        except Exception as error:
            failure("web_research", error, getattr(fetch, "__name__", ""))
            return []

    @staticmethod
    def _deduplicate(results: list[SearchResult]) -> list[SearchResult]:
        seen: set[str] = set()
        unique: list[SearchResult] = []
        for item in results:
            if item.url not in seen:
                seen.add(item.url)
                unique.append(item)
        return unique

    def _get(self, url: str, params: dict):
        response = self.session.get(
            url, params=params, headers={"User-Agent": USER_AGENT}, timeout=self.timeout
        )
        response.raise_for_status()
        return response

    def _serpapi(self, query: str, limit: int, key: str) -> list[SearchResult]:
        response = self._get(
            "https://serpapi.com/search.json",
            {"engine": "google", "q": query, "api_key": key, "num": limit},
        )
        items = response.json().get("organic_results", [])
        return [
            SearchResult(str(item.get("title", "")), str(item.get("link", "")), str(item.get("snippet", "")))
            for item in items[:limit] if item.get("title") and item.get("link")
        ]

    def _instant_answer(self, query: str, limit: int) -> list[SearchResult]:
        """DuckDuckGo's documented Instant Answer API (no key required)."""
        payload = self._get(
            "https://api.duckduckgo.com/",
            {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
        ).json()
        results: list[SearchResult] = []
        abstract = str(payload.get("AbstractText") or "").strip()
        abstract_url = str(payload.get("AbstractURL") or "").strip()
        if abstract and abstract_url:
            heading = str(payload.get("Heading") or query).strip()
            source = str(payload.get("AbstractSource") or "DuckDuckGo").strip()
            results.append(SearchResult(f"{heading} ({source})", abstract_url, abstract))
        for topic in payload.get("RelatedTopics") or []:
            if len(results) >= limit:
                break
            text = str(topic.get("Text") or "").strip()
            url = str(topic.get("FirstURL") or "").strip()
            if text and url:
                results.append(SearchResult(text.split(" - ")[0][:120], url, text))
        return results

    def _wikipedia(self, query: str, limit: int) -> list[SearchResult]:
        """Wikipedia's public REST search API (no key required)."""
        pages = self._get(
            "https://en.wikipedia.org/w/rest.php/v1/search/page",
            {"q": query, "limit": max(1, limit)},
        ).json().get("pages", [])
        results: list[SearchResult] = []
        for page in pages[:limit]:
            title = str(page.get("title") or "").strip()
            if not title:
                continue
            summary = self._wikipedia_summary(title) or str(page.get("description") or "").strip()
            if not summary:
                continue
            slug = title.replace(" ", "_")
            results.append(SearchResult(f"{title} (Wikipedia)", f"https://en.wikipedia.org/wiki/{slug}", summary))
        return results

    def _wikipedia_summary(self, title: str) -> str:
        try:
            payload = self._get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}", {}
            ).json()
        except Exception:
            return ""
        return str(payload.get("extract") or "").strip()

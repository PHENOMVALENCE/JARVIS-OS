"""Small, dependency-light web search client for answer grounding."""

from __future__ import annotations

import html
import os
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse

import requests


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str

    def passage(self) -> str:
        return f"SOURCE: {self.title}\nURL: {self.url}\nSUMMARY: {self.snippet}".strip()


class _DuckParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results: list[SearchResult] = []
        self._url = ""
        self._title: list[str] = []
        self._snippet: list[str] = []
        self._capture = ""

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        classes = values.get("class", "").split()
        if tag == "a" and "result__a" in classes:
            self._flush()
            self._url = self._clean_url(values.get("href", ""))
            self._capture = "title"
        elif "result__snippet" in classes:
            self._capture = "snippet"

    def handle_endtag(self, tag):
        if tag in {"a", "div"}:
            self._capture = ""

    def handle_data(self, data):
        if self._capture == "title":
            self._title.append(data)
        elif self._capture == "snippet":
            self._snippet.append(data)

    def close(self):
        super().close()
        self._flush()

    def _flush(self):
        title = " ".join("".join(self._title).split())
        snippet = " ".join("".join(self._snippet).split())
        if self._url and title:
            self.results.append(SearchResult(html.unescape(title), self._url, html.unescape(snippet)))
        self._url = ""
        self._title = []
        self._snippet = []

    @staticmethod
    def _clean_url(value: str) -> str:
        parsed = urlparse(html.unescape(value))
        redirected = parse_qs(parsed.query).get("uddg")
        return unquote(redirected[0]) if redirected else value


class WebResearch:
    def __init__(self, session=requests, timeout: int = 12):
        self.session = session
        self.timeout = timeout

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        key = os.getenv("SERPAPI_API_KEY", "").strip()
        return self._serpapi(query, limit, key) if key else self._duckduckgo(query, limit)

    def _serpapi(self, query: str, limit: int, key: str) -> list[SearchResult]:
        response = self.session.get(
            "https://serpapi.com/search.json",
            params={"engine": "google", "q": query, "api_key": key, "num": limit},
            timeout=self.timeout,
        )
        response.raise_for_status()
        items = response.json().get("organic_results", [])
        return [
            SearchResult(str(item.get("title", "")), str(item.get("link", "")), str(item.get("snippet", "")))
            for item in items[:limit] if item.get("title") and item.get("link")
        ]

    def _duckduckgo(self, query: str, limit: int) -> list[SearchResult]:
        response = self.session.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 JARVIS/7.0"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        parser = _DuckParser()
        parser.feed(response.text)
        parser.close()
        return parser.results[:limit]

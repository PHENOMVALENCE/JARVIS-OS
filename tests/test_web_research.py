import unittest
from unittest.mock import Mock, patch

from jarvis_os.web_research import WebResearch


class WebResearchTests(unittest.TestCase):
    def test_parses_duckduckgo_results(self):
        response = Mock()
        response.text = """
        <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fguide">Example Guide</a>
        <div class="result__snippet">A useful current explanation.</div>
        """
        session = Mock()
        session.get.return_value = response
        with patch.dict("os.environ", {}, clear=True):
            results = WebResearch(session).search("example")
        self.assertEqual(results[0].title, "Example Guide")
        self.assertEqual(results[0].url, "https://example.com/guide")
        self.assertIn("useful current explanation", results[0].snippet)

    def test_uses_serpapi_when_configured(self):
        response = Mock()
        response.json.return_value = {"organic_results": [{"title": "Result", "link": "https://example.com", "snippet": "Text"}]}
        session = Mock()
        session.get.return_value = response
        with patch.dict("os.environ", {"SERPAPI_API_KEY": "secret"}, clear=True):
            results = WebResearch(session).search("topic")
        self.assertEqual(results[0].title, "Result")
        self.assertEqual(session.get.call_args.args[0], "https://serpapi.com/search.json")


if __name__ == "__main__":
    unittest.main()

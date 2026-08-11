import unittest
from unittest.mock import Mock, patch

from jarvis_os.web_research import WebResearch, topic_of


def _json_response(payload):
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class TopicExtractionTests(unittest.TestCase):
    def test_reduces_spoken_questions_to_a_lookup_subject(self):
        self.assertEqual(topic_of("what is the meaning of ai"), "artificial intelligence")
        self.assertEqual(topic_of("what is a black hole"), "black hole")
        self.assertEqual(topic_of("tell me about the moon"), "moon")
        self.assertEqual(topic_of("define entropy"), "entropy")
        self.assertEqual(topic_of("who is Isaac Newton"), "Isaac Newton")

    def test_does_not_eat_letters_from_the_subject(self):
        self.assertEqual(topic_of("what is artificial intelligence"), "artificial intelligence")
        self.assertEqual(topic_of("who is an architect"), "architect")

    def test_keeps_a_query_that_is_already_a_topic(self):
        self.assertEqual(topic_of("quantum computing"), "quantum computing")
        self.assertEqual(topic_of("  "), "")


class WebResearchTests(unittest.TestCase):
    def test_uses_serpapi_when_configured(self):
        session = Mock()
        session.get.return_value = _json_response(
            {"organic_results": [{"title": "Result", "link": "https://example.com", "snippet": "Text"}]}
        )
        with patch.dict("os.environ", {"SERPAPI_API_KEY": "secret"}, clear=True):
            results = WebResearch(session).search("topic")
        self.assertEqual(results[0].title, "Result")
        self.assertEqual(session.get.call_args.args[0], "https://serpapi.com/search.json")

    def test_falls_back_to_instant_answer_without_a_key(self):
        session = Mock()
        session.get.return_value = _json_response({
            "Heading": "Artificial intelligence",
            "AbstractSource": "Wikipedia",
            "AbstractText": "The capability of computational systems to perform tasks.",
            "AbstractURL": "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "RelatedTopics": [],
        })
        with patch.dict("os.environ", {}, clear=True):
            results = WebResearch(session).search("what is ai", limit=1)
        self.assertEqual(results[0].url, "https://en.wikipedia.org/wiki/Artificial_intelligence")
        self.assertIn("computational systems", results[0].snippet)
        self.assertIn("Wikipedia", results[0].title)

    def test_adds_wikipedia_results_when_instant_answer_is_thin(self):
        def respond(url, **_kwargs):
            if "api.duckduckgo.com" in url:
                return _json_response({"AbstractText": "", "AbstractURL": "", "RelatedTopics": []})
            if "rest.php/v1/search/page" in url:
                return _json_response({"pages": [{"title": "Quantum computing", "description": "Computing type"}]})
            return _json_response({"extract": "Quantum computing uses quantum states."})

        session = Mock()
        session.get.side_effect = respond
        with patch.dict("os.environ", {}, clear=True):
            results = WebResearch(session).search("quantum computing", limit=3)
        self.assertEqual(results[0].url, "https://en.wikipedia.org/wiki/Quantum_computing")
        self.assertIn("quantum states", results[0].snippet)

    def test_one_failing_provider_does_not_break_the_answer(self):
        def respond(url, **_kwargs):
            if "api.duckduckgo.com" in url:
                raise OSError("network down")
            if "rest.php/v1/search/page" in url:
                return _json_response({"pages": [{"title": "Mars", "description": "Fourth planet"}]})
            return _json_response({"extract": "Mars is the fourth planet from the Sun."})

        session = Mock()
        session.get.side_effect = respond
        with patch.dict("os.environ", {}, clear=True):
            results = WebResearch(session).search("mars", limit=2)
        self.assertEqual(len(results), 1)
        self.assertIn("fourth planet", results[0].snippet)

    def test_returns_nothing_for_an_empty_query(self):
        session = Mock()
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(WebResearch(session).search("   "), [])
        session.get.assert_not_called()

    def test_reports_whether_full_web_access_is_configured(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(WebResearch(Mock()).has_full_web_access)
        with patch.dict("os.environ", {"SERPAPI_API_KEY": "secret"}, clear=True):
            self.assertTrue(WebResearch(Mock()).has_full_web_access)


if __name__ == "__main__":
    unittest.main()

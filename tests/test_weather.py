import unittest
from unittest.mock import Mock

from jarvis_os.file_search import FileSearch
from jarvis_os.router import CommandRouter
from jarvis_os.weather import WeatherService, describe


def _json(payload):
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


GEOCODE = {"results": [{"name": "Dar es Salaam", "country": "Tanzania", "latitude": -6.8, "longitude": 39.3}]}


class WeatherServiceTests(unittest.TestCase):
    def _service(self, forecast_payload):
        session = Mock()
        session.get.side_effect = lambda url, **_k: _json(
            GEOCODE if "geocoding" in url else forecast_payload
        )
        return WeatherService(session)

    def test_describes_current_conditions_in_one_sentence(self):
        service = self._service({
            "current": {"temperature_2m": 23.7, "apparent_temperature": 26.8, "weather_code": 0},
            "daily": {"temperature_2m_max": [28.5], "temperature_2m_min": [20.9],
                      "precipitation_probability_max": [59]},
        })
        answer = service.current("Dar es Salaam")
        self.assertIn("24 degrees and clear in Dar es Salaam, Tanzania", answer)
        self.assertIn("feels like 27", answer)
        self.assertIn("21 to 28", answer)
        self.assertIn("59 percent chance of rain", answer)

    def test_omits_feels_like_when_it_matches_the_temperature(self):
        service = self._service({
            "current": {"temperature_2m": 20.0, "apparent_temperature": 20.4, "weather_code": 3},
            "daily": {"temperature_2m_max": [22.0], "temperature_2m_min": [15.0],
                      "precipitation_probability_max": [5]},
        })
        answer = service.current("Dar es Salaam")
        self.assertNotIn("feels like", answer)
        self.assertNotIn("chance of rain", answer)

    def test_returns_nothing_for_an_unknown_place(self):
        session = Mock()
        session.get.return_value = _json({"results": []})
        self.assertIsNone(WeatherService(session).current("Atlantis"))

    def test_translates_weather_codes(self):
        self.assertEqual(describe(0), "clear")
        self.assertEqual(describe(95), "a thunderstorm")
        self.assertEqual(describe(1234), "unsettled")


class WeatherRoutingTests(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()

    def test_routes_weather_questions_to_the_weather_provider(self):
        self.assertEqual(self.router.route("What is the weather today").action, "weather")
        command = self.router.route("What's the weather in Dar es Salaam")
        self.assertEqual(command.action, "weather")
        self.assertEqual(command.arguments["place"], "dar es salaam")

    def test_routes_multi_day_questions_to_the_forecast(self):
        self.assertEqual(self.router.route("Weather forecast for London").action, "forecast")
        self.assertEqual(self.router.route("Will it rain tomorrow").action, "forecast")

    def test_weather_wins_over_encyclopedic_lookup(self):
        # Wikipedia cannot answer this, so the weather provider should take it.
        self.assertEqual(self.router.route("Look up the weather in Dar es Salaam").action, "weather")

    def test_explicit_browser_search_still_wins(self):
        self.assertEqual(self.router.route("Search the internet for weather tomorrow").action, "web_search")
        self.assertEqual(self.router.route("Google weather in Paris").action, "web_search")

    def test_routes_screen_reading_locally(self):
        command = self.router.route("Read the screen")
        self.assertEqual(command.action, "read_screen")


class FileSearchTests(unittest.TestCase):
    def test_falls_back_to_walking_when_the_index_is_unavailable(self):
        search = FileSearch()
        search._from_index = lambda _query: []
        search._from_walk = lambda query: [f"walked:{query}"]
        self.assertEqual(search.search("budget"), ["walked:budget"])

    def test_prefers_the_index_when_it_returns_results(self):
        search = FileSearch()
        search._from_index = lambda _query: ["indexed"]
        search._from_walk = lambda _query: ["walked"]
        self.assertEqual(search.search("budget"), ["indexed"])

    def test_ignores_an_empty_query(self):
        self.assertEqual(FileSearch().search("  *  "), [])


if __name__ == "__main__":
    unittest.main()

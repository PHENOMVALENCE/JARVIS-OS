"""Weather from Open-Meteo, which is free and needs no API key.

Weather is the question people ask an assistant most, and it is exactly the
kind of fact a local model cannot know. Encyclopedic sources cannot answer it
either, so it gets a dedicated provider rather than a web search.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests


USER_AGENT = "JARVIS-OS/7.0 (personal desktop assistant)"

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# https://open-meteo.com/en/docs - WMO weather interpretation codes.
CONDITIONS = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "freezing drizzle", 57: "heavy freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "heavy freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "violent showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "a thunderstorm", 96: "a thunderstorm with hail", 99: "a severe thunderstorm with hail",
}


def describe(code: int) -> str:
    return CONDITIONS.get(int(code), "unsettled")


@dataclass(frozen=True)
class Place:
    name: str
    country: str
    latitude: float
    longitude: float

    @property
    def label(self) -> str:
        return f"{self.name}, {self.country}" if self.country else self.name


class WeatherService:
    def __init__(self, session=requests, timeout: int = 12):
        self.session = session
        self.timeout = timeout

    def _get(self, url: str, params: dict) -> dict:
        response = self.session.get(
            url, params=params, headers={"User-Agent": USER_AGENT}, timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def locate(self, place: str) -> Place | None:
        results = self._get(GEOCODE_URL, {"name": place, "count": 1}).get("results") or []
        if not results:
            return None
        found = results[0]
        return Place(
            str(found.get("name", place)), str(found.get("country", "")),
            float(found["latitude"]), float(found["longitude"]),
        )

    def current(self, place: str) -> str | None:
        """One spoken sentence about the weather now, plus today's range."""
        location = self.locate(place)
        if not location:
            return None
        payload = self._get(FORECAST_URL, {
            "latitude": location.latitude, "longitude": location.longitude,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto", "forecast_days": 1,
        })
        now = payload.get("current") or {}
        daily = payload.get("daily") or {}
        temperature = round(float(now.get("temperature_2m", 0)))
        feels = round(float(now.get("apparent_temperature", temperature)))
        sentence = f"It's {temperature} degrees and {describe(now.get('weather_code', -1))} in {location.label}"
        if abs(feels - temperature) >= 2:
            sentence += f", feels like {feels}"
        high, low = self._first(daily, "temperature_2m_max"), self._first(daily, "temperature_2m_min")
        if high is not None and low is not None:
            sentence += f". Today runs {round(low)} to {round(high)}"
        rain = self._first(daily, "precipitation_probability_max")
        if rain is not None and rain >= 30:
            sentence += f", with a {round(rain)} percent chance of rain"
        return sentence + "."

    def forecast(self, place: str, days: int = 3) -> str | None:
        location = self.locate(place)
        if not location:
            return None
        payload = self._get(FORECAST_URL, {
            "latitude": location.latitude, "longitude": location.longitude,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto", "forecast_days": max(1, min(7, days)),
        })
        daily = payload.get("daily") or {}
        dates = daily.get("time") or []
        if not dates:
            return None
        from datetime import date

        parts = []
        for index, day in enumerate(dates):
            label = "Today" if index == 0 else ("Tomorrow" if index == 1 else date.fromisoformat(day).strftime("%A"))
            parts.append(
                f"{label}, {describe(daily['weather_code'][index])}, "
                f"{round(daily['temperature_2m_min'][index])} to {round(daily['temperature_2m_max'][index])} degrees"
            )
        return f"Forecast for {location.label}. " + ". ".join(parts) + "."

    @staticmethod
    def _first(daily: dict, key: str):
        values = daily.get(key) or []
        return values[0] if values else None

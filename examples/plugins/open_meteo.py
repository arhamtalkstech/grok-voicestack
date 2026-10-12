"""Example code plugin: current weather from Open-Meteo (free, no API key).

Load it with PLUGINS_DIR=examples/plugins, then Integrations → Code plugins → Make available, and
attach `current_weather` to an agent on its Tools tab.
"""

import httpx

from voicestack.tools.plugins import voice_tool


@voice_tool
async def current_weather(city: str) -> str:
    """Get the current temperature, wind, and conditions for a city. Use when the caller asks about the weather."""
    async with httpx.AsyncClient(timeout=10) as client:
        geo = (await client.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1})).json()
        if not geo.get("results"):
            return f"No location found for {city}."
        place = geo["results"][0]
        weather = (
            await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={"latitude": place["latitude"], "longitude": place["longitude"], "current": "temperature_2m,wind_speed_10m,weather_code"},
            )
        ).json()["current"]
    return (
        f"{place['name']}, {place.get('country', '')}: {weather['temperature_2m']} degrees Celsius, "
        f"wind {weather['wind_speed_10m']} km/h, WMO weather code {weather['weather_code']}."
    )

"""
Current weather for an arbitrary point via the Open-Meteo forecast API
(free, key-less, CORS-enabled). Returns the raw readings plus a
normalized `condition` category (clear / clouds / fog / rain / snow /
storm) and a `is_day` flag, so a frontend can pick a matching background
video/animation without having to re-implement the WMO weather-code
mapping itself.
"""
import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes -> coarse condition category.
# https://open-meteo.com/en/docs (weather_code table)
_CONDITION_BY_CODE = {
    0: "clear",
    1: "clear", 2: "clouds", 3: "clouds",
    45: "fog", 48: "fog",
    51: "rain", 53: "rain", 55: "rain",
    56: "rain", 57: "rain",
    61: "rain", 63: "rain", 65: "rain",
    66: "rain", 67: "rain",
    71: "snow", 73: "snow", 75: "snow", 77: "snow",
    80: "rain", 81: "rain", 82: "rain",
    85: "snow", 86: "snow",
    95: "storm", 96: "storm", 99: "storm",
}

_LABEL_BY_CODE = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


def get_current_weather(lat: float, lon: float) -> dict:
    resp = requests.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": ",".join([
                "temperature_2m", "relative_humidity_2m", "apparent_temperature",
                "precipitation", "weather_code", "wind_speed_10m", "cloud_cover", "is_day",
            ]),
            "timezone": "auto",
        },
        timeout=10,
    )
    resp.raise_for_status()
    cur = resp.json()["current"]
    code = int(cur.get("weather_code", 0))
    return {
        "lat": lat,
        "lon": lon,
        "temperature": cur.get("temperature_2m"),
        "apparent_temperature": cur.get("apparent_temperature"),
        "humidity": cur.get("relative_humidity_2m"),
        "precipitation": cur.get("precipitation"),
        "wind_speed": cur.get("wind_speed_10m"),
        "cloud_cover": cur.get("cloud_cover"),
        "weather_code": code,
        "condition": _CONDITION_BY_CODE.get(code, "clouds"),
        "description": _LABEL_BY_CODE.get(code, "Unknown"),
        "is_day": bool(cur.get("is_day", 1)),
        "observed_at": cur.get("time"),
    }

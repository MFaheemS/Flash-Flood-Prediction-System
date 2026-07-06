"""
Fetch the latest weather at a location for live cloudburst prediction.

ERA5 (`fetch_era5.py`) is a *reanalysis* product with a several-day
publication lag, so it can't be used for "what's happening right now".
For live inference we instead use the Open-Meteo forecast API
(https://open-meteo.com), which is free, requires no API key, and
exposes the same variables our model was trained on (temperature,
humidity, dew point, pressure, cloud cover, wind speed, precipitation,
CAPE) for the last few hours plus a short-term forecast.
"""
import numpy as np
import pandas as pd
import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "pressure_msl",
    "cloud_cover",
    "wind_speed_10m",
    "precipitation",
]


def fetch_current_weather(lat: float, lon: float, past_hours: int = 4, forecast_hours: int = 1) -> pd.DataFrame:
    """
    Return an hourly dataframe for the last `past_hours` plus
    `forecast_hours` ahead at (lat, lon), with columns matching the
    model's feature names: temperature, humidity, dew_point, pressure,
    cloud_cover, wind_speed, rainfall, temp_dewpoint_spread,
    pressure_drop_3h.

    Note: CAPE is only available from Open-Meteo's forecast model, not
    its historical archive, so it can't be used as a training feature
    without a train/serve mismatch. `temp_dewpoint_spread` (smaller ==
    more saturated air == more convective potential) is used instead
    because it's computable identically from both historical and live
    data.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_VARS),
        "past_hours": past_hours,
        "forecast_hours": forecast_hours,
        "timezone": "UTC",
    }
    resp = requests.get(FORECAST_URL, params=params, timeout=30)
    resp.raise_for_status()
    hourly = resp.json()["hourly"]

    df = pd.DataFrame(
        {
            "time": pd.to_datetime(hourly["time"]),
            "temperature": hourly["temperature_2m"],
            "humidity": hourly["relative_humidity_2m"],
            "dew_point": hourly["dew_point_2m"],
            "pressure": hourly["pressure_msl"],
            "cloud_cover": hourly["cloud_cover"],
            "wind_speed": hourly["wind_speed_10m"],
            "rainfall": hourly["precipitation"],
        }
    )
    df["temp_dewpoint_spread"] = df["temperature"] - df["dew_point"]
    df["pressure_drop_3h"] = df["pressure"].diff(periods=min(3, len(df) - 1)).fillna(0.0)
    df["lat"] = lat
    df["lon"] = lon
    return df


def fetch_latest_row(lat: float, lon: float) -> pd.DataFrame:
    """Return a single-row dataframe for the most recent hour, ready for `predict()`."""
    df = fetch_current_weather(lat, lon)
    return df.tail(1).reset_index(drop=True)


if __name__ == "__main__":
    # Example: Islamabad
    row = fetch_latest_row(lat=33.6844, lon=73.0479)
    print(row)

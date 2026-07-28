"""
Multi-horizon flash-flood/cloudburst risk for a set of monitored
locations, built on top of the trained model in `src/models/predict.py`.

Horizons:
  - "hour"  : probability for the next hour (Open-Meteo forecast, hour 0)
  - "day"   : max hourly probability over the next 24h
  - "week"  : max hourly probability over the next 7 days
  - "month" : max of the 16-day forecast-based signal (Open-Meteo's
              forecast limit) and a seasonal climatology baseline for
              the rest of the 30-day window (see
              `historical.monthly_climatology_score`) — no weather
              model forecasts reliably past ~16 days, so the tail of
              the month falls back to "how often does this area flood
              in this calendar month, historically".
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import requests

from src.data.geo_reference import DISTRICT_TOWNS
from src.data.load_data import load_config
from src.data.terrain import attach_terrain, fetch_terrain_openmeteo, load_terrain_index
from src.data.soil import fetch_clay_pct
from src.data.soil_moisture import fetch_recent_soil_wetness
from src.data.urbanization import build_urbanization_proxy
from src.data.waterways import waterway_features
from src.features.historical import (
    historical_flood_freq,
    monthly_climatology_score,
)
from src.models.predict import predict

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

def _safe_float(value):
    """float() but NaN -> None, so the value survives JSON serialization."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(f) else f


_cache: dict[str, tuple[float, pd.DataFrame]] = {}
CACHE_TTL_SECONDS = 30 * 60


def _fetch_forecast_hourly(lat: float, lon: float, forecast_days: int = 16) -> pd.DataFrame:
    resp = requests.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(HOURLY_VARS),
            "forecast_days": forecast_days,
            "timezone": "UTC",
        },
        timeout=10,
    )
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
    df["pressure_drop_3h"] = df["pressure"].diff(periods=3).fillna(0.0)
    df["temp_dewpoint_spread"] = df["temperature"] - df["dew_point"]
    return df


def _attach_static_features(df: pd.DataFrame, lat: float, lon: float, config: dict) -> pd.DataFrame:
    df = df.copy()
    df["lat"] = lat
    df["lon"] = lon

    terrain_path = config["data"]["terrain_index_path"]
    point = pd.DataFrame({"lat": [lat], "lon": [lon]})
    try:
        terrain_df = load_terrain_index(terrain_path)
        match = ((terrain_df["lat"] - lat).abs() < 1e-6) & ((terrain_df["lon"] - lon).abs() < 1e-6)
        if not match.any():
            raise FileNotFoundError
        elevation = terrain_df.loc[match, "elevation"].iloc[0]
        slope = terrain_df.loc[match, "slope"].iloc[0]
    except (FileNotFoundError, IndexError):
        terrain_df = fetch_terrain_openmeteo(point, out_path=terrain_path + ".tmp")
        elevation = terrain_df["elevation"].iloc[0]
        slope = terrain_df["slope"].iloc[0]

    df["elevation"] = elevation
    df["slope"] = slope

    urban = build_urbanization_proxy(point)
    df["urbanization_index"] = urban["urbanization_index"].iloc[0]

    # lat/lon is constant across every hourly row of a single location's
    # forecast, so compute these once and broadcast rather than running
    # the (row-wise) dataset-attach helpers, which would needlessly repeat
    # the same expensive lookup ~384 times (once per forecast hour).
    df["historical_flood_freq"] = historical_flood_freq(lat, lon, config["data"]["events_path"])
    wf = waterway_features(lat, lon, config["data"]["waterways_path"])
    df["distance_to_waterway_km"] = wf["distance_to_waterway_km"]
    df["waterway_count_10km"] = wf["waterway_count_10km"]
    df["soil_clay_pct"] = fetch_clay_pct(lat, lon)
    wetness = fetch_recent_soil_wetness(lat, lon)
    df["soil_moisture_root"] = wetness["soil_moisture_root"]
    df["soil_moisture_surface"] = wetness["soil_moisture_surface"]
    return df


def _forecast_with_predictions(lat: float, lon: float, config: dict) -> pd.DataFrame:
    key = f"{lat:.4f},{lon:.4f}"
    now = time.time()
    if key in _cache and now - _cache[key][0] < CACHE_TTL_SECONDS:
        return _cache[key][1]

    df = _fetch_forecast_hourly(lat, lon)
    df = _attach_static_features(df, lat, lon, config)
    df = df.dropna(subset=["temperature", "humidity", "pressure", "pressure_drop_3h"]).reset_index(drop=True)
    df = predict(df)
    _cache[key] = (now, df)
    return df


def location_risk(name: str, lat: float, lon: float, config: dict) -> dict:
    df = _forecast_with_predictions(lat, lon, config)
    now = pd.Timestamp.now("UTC").tz_localize(None)

    next_hour = df[df["time"] >= now].head(1)
    hour_risk = float(next_hour["cloudburst_probability"].iloc[0]) if len(next_hour) else float(df["cloudburst_probability"].iloc[0])

    next_24h = df[(df["time"] >= now) & (df["time"] < now + pd.Timedelta(hours=24))]
    day_risk = float(next_24h["cloudburst_probability"].max()) if len(next_24h) else hour_risk

    next_7d = df[(df["time"] >= now) & (df["time"] < now + pd.Timedelta(days=7))]
    week_risk = float(next_7d["cloudburst_probability"].max()) if len(next_7d) else day_risk

    forecast_month_risk = float(df["cloudburst_probability"].max()) if len(df) else 0.0
    climatology = monthly_climatology_score(lat, lon, now.month, config["data"]["events_path"])
    month_risk = max(forecast_month_risk, climatology)

    peak_row = df.loc[df["cloudburst_probability"].idxmax()] if len(df) else None

    return {
        "name": name,
        "lat": lat,
        "lon": lon,
        "hour_risk": hour_risk,
        "day_risk": day_risk,
        "week_risk": week_risk,
        "month_risk": month_risk,
        "peak_time": peak_row["time"].isoformat() if peak_row is not None else None,
        "elevation": float(df["elevation"].iloc[0]) if len(df) else None,
        "urbanization_index": float(df["urbanization_index"].iloc[0]) if len(df) else None,
        "historical_flood_freq": float(df["historical_flood_freq"].iloc[0]) if len(df) else None,
        "distance_to_waterway_km": float(df["distance_to_waterway_km"].iloc[0]) if len(df) else None,
        "waterway_count_10km": int(df["waterway_count_10km"].iloc[0]) if len(df) else None,
        "soil_clay_pct": _safe_float(df["soil_clay_pct"].iloc[0]) if len(df) else None,
        "soil_moisture_root": _safe_float(df["soil_moisture_root"].iloc[0]) if len(df) else None,
        "soil_moisture_surface": _safe_float(df["soil_moisture_surface"].iloc[0]) if len(df) else None,
    }


def all_locations_risk(horizon: str = "week") -> list[dict]:
    config = load_config()
    key_map = {"hour": "hour_risk", "day": "day_risk", "week": "week_risk", "month": "month_risk"}
    sort_key = key_map.get(horizon, "week_risk")

    # Each location is an independent network call (weather forecast) plus
    # some local computation; run them concurrently instead of one at a
    # time, or a cold cache (e.g. right after a server restart) makes the
    # dashboard take 60-100+ seconds to load a single tab.
    results = []
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {
            executor.submit(location_risk, name, town["lat"], town["lon"], config): name
            for name, town in DISTRICT_TOWNS.items()
        }
        # Hard cap on total wait: a handful of slow/unresponsive upstream
        # API calls must not be able to stall the whole dashboard load
        # indefinitely. Whatever hasn't finished by the deadline is
        # dropped (still running in the background, just not waited on).
        try:
            for future in as_completed(futures, timeout=60):
                name = futures[future]
                try:
                    result = future.result(timeout=0)
                    # attach the district's province (known from the static
                    # watchlist) so the frontend can show it without a second
                    # lookup — location_risk itself is location-agnostic.
                    result["province"] = DISTRICT_TOWNS[name].get("province")
                    results.append(result)
                except Exception as exc:
                    print(f"Skipping {name}: {exc}")
        except TimeoutError:
            print(f"Timed out waiting for {len(futures) - len(results)} location(s); showing partial results")

    results.sort(key=lambda r: r[sort_key], reverse=True)
    return results


if __name__ == "__main__":
    for r in all_locations_risk("week")[:10]:
        print(r["name"], round(r["week_risk"], 3))

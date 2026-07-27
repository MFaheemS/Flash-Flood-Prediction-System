"""
Antecedent soil wetness from NASA POWER (https://power.larc.nasa.gov),
free, key-less REST API backed by MERRA-2 reanalysis. Unlike the static
soil_clay_pct (a fixed soil property from SoilGrids), this is
time-varying: how saturated the ground already was going into a given
day. Already-wet ground sheds a storm's rain as runoff far faster than
dry ground can absorb it -- a genuine, physically distinct flash-flood
driver from anything else in the pipeline.

Two soil layers are returned:
  - GWETROOT: root-zone wetness (0-1, deeper/slower-changing)
  - GWETTOP:  surface wetness (0-1, faster-changing)
"""
import time

import numpy as np
import pandas as pd
import requests

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
FILL_VALUE = -999.0


def fetch_soil_wetness(lat: float, lon: float, date: pd.Timestamp, retries: int = 3) -> dict:
    """Soil wetness for a specific historical date (training-time use)."""
    date_str = pd.Timestamp(date).strftime("%Y%m%d")
    for attempt in range(retries):
        try:
            resp = requests.get(
                POWER_URL,
                params={
                    "parameters": "GWETROOT,GWETTOP",
                    "community": "AG",
                    "longitude": lon,
                    "latitude": lat,
                    "start": date_str,
                    "end": date_str,
                    "format": "JSON",
                },
                timeout=15,
            )
            resp.raise_for_status()
            params = resp.json()["properties"]["parameter"]
            root = params["GWETROOT"].get(date_str, FILL_VALUE)
            top = params["GWETTOP"].get(date_str, FILL_VALUE)
            return {
                "soil_moisture_root": np.nan if root == FILL_VALUE else root,
                "soil_moisture_surface": np.nan if top == FILL_VALUE else top,
            }
        except (requests.RequestException, KeyError):
            time.sleep(1.0)
    return {"soil_moisture_root": np.nan, "soil_moisture_surface": np.nan}


def fetch_recent_soil_wetness(lat: float, lon: float, lookback_days: int = 10) -> dict:
    """
    Most recent available soil wetness (live/dashboard use). NASA POWER's
    MERRA-2 feed lags real-time by several days, so this queries the last
    `lookback_days` and returns the most recent non-missing value rather
    than assuming "today" is already published.
    """
    end = pd.Timestamp.now("UTC").tz_localize(None).normalize()
    start = end - pd.Timedelta(days=lookback_days)
    try:
        resp = requests.get(
            POWER_URL,
            params={
                "parameters": "GWETROOT,GWETTOP",
                "community": "AG",
                "longitude": lon,
                "latitude": lat,
                "start": start.strftime("%Y%m%d"),
                "end": end.strftime("%Y%m%d"),
                "format": "JSON",
            },
            timeout=15,
        )
        resp.raise_for_status()
        params = resp.json()["properties"]["parameter"]
        root_series = [v for v in params["GWETROOT"].values() if v != FILL_VALUE]
        top_series = [v for v in params["GWETTOP"].values() if v != FILL_VALUE]
        return {
            "soil_moisture_root": root_series[-1] if root_series else np.nan,
            "soil_moisture_surface": top_series[-1] if top_series else np.nan,
        }
    except requests.RequestException:
        return {"soil_moisture_root": np.nan, "soil_moisture_surface": np.nan}


def attach_soil_wetness(df: pd.DataFrame) -> pd.DataFrame:
    """Attach soil_moisture_root / soil_moisture_surface per (lat, lon, date) row."""
    cache = {}
    results = []
    for _, row in df.iterrows():
        key = (round(row["lat"], 4), round(row["lon"], 4), pd.Timestamp(row["date"]).strftime("%Y%m%d"))
        if key not in cache:
            cache[key] = fetch_soil_wetness(row["lat"], row["lon"], row["date"])
        results.append(cache[key])

    result_df = pd.DataFrame(results, index=df.index)
    df["soil_moisture_root"] = result_df["soil_moisture_root"]
    df["soil_moisture_surface"] = result_df["soil_moisture_surface"]
    return df

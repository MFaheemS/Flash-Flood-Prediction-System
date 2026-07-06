"""
LEGACY / OPTIONAL: requires a CDS account (see below). The dashboard and
default pipeline use `build_dataset_openmeteo.py` instead, which needs no
API key. Keep this around only if you specifically want ERA5 data pulled
directly from Copernicus rather than via Open-Meteo's archive.

Build data/raw/cloudburst_dataset.csv (the model's training table) from:

  - Positive examples: real historical cloudburst events in
    CLOUDPAK25_2010_2025_v3.csv (date, lat, lon, peak_rainfall_mm_per_hr).
  - Negative examples: randomly sampled date/location/hour combinations
    within the same region and years, assumed non-cloudburst.

For every event/sample, the corresponding ERA5 hourly grid point is
looked up (downloading the month's ERA5 file via `fetch_era5` first if
it isn't already cached in data/raw/era5/).

Requires a CDS API key at ~/.cdsapirc (see fetch_era5.py docstring).
This only needs to be run once (or re-run when new events are added);
it is a data-preparation script, not part of the training/inference
pipeline itself.
"""
import os
import random

import numpy as np
import pandas as pd
import xarray as xr

from src.data.fetch_era5 import fetch_era5
from src.data.load_data import load_config

EVENTS_PATH = "CLOUDPAK25_2010_2025_v3.csv"

# ERA5 single-levels short names -> our feature names
VAR_MAP = {
    "t2m": "temperature",
    "d2m": "dew_point",
    "sp": "pressure",
    "tcc": "cloud_cover",
    "cape": "cape",
    "tp": "rainfall",
}


def _era5_path(year: str, month: str, config: dict) -> str:
    region = config["region"]
    return os.path.join(config["data"]["era5_dir"], f"era5_{region['name']}_{year}_{month}.nc")


def _ensure_era5(year: str, month: str, config: dict) -> str:
    path = _era5_path(year, month, config)
    if not os.path.exists(path):
        fetch_era5(year=year, month=month, config=config)
    return path


def _extract_point(ds: xr.Dataset, lat: float, lon: float, time) -> dict:
    point = ds.sel(latitude=lat, longitude=lon, time=time, method="nearest")

    row = {}
    for era5_name, feature_name in VAR_MAP.items():
        if era5_name in point:
            value = float(point[era5_name].values)
            if era5_name == "sp":
                value = value / 100.0  # Pa -> hPa
            elif era5_name == "tp":
                value = value * 1000.0  # m -> mm
            elif era5_name in ("t2m", "d2m"):
                value = value - 273.15  # K -> C
            row[feature_name] = value

    u10 = float(point["u10"].values) if "u10" in point else np.nan
    v10 = float(point["v10"].values) if "v10" in point else np.nan
    row["wind_speed"] = float(np.sqrt(u10 ** 2 + v10 ** 2))

    # relative humidity approximated from temperature/dew point (Magnus formula)
    if "temperature" in row and "dew_point" in row:
        t, td = row["temperature"], row["dew_point"]
        row["humidity"] = 100 * np.exp((17.625 * td) / (243.04 + td)) / np.exp((17.625 * t) / (243.04 + t))

    # pressure 3h earlier, for pressure_drop_3h
    try:
        earlier = ds.sel(latitude=lat, longitude=lon, method="nearest").sel(
            time=pd.Timestamp(time) - pd.Timedelta(hours=3), method="nearest"
        )
        row["pressure_drop_3h"] = row.get("pressure", np.nan) - float(earlier["sp"].values) / 100.0
    except Exception:
        row["pressure_drop_3h"] = np.nan

    return row


def build_positive_rows(config: dict) -> pd.DataFrame:
    events = pd.read_csv(EVENTS_PATH)
    events["date"] = pd.to_datetime(events["date"])

    rows = []
    for _, ev in events.iterrows():
        year, month = f"{ev['date'].year}", f"{ev['date'].month:02d}"
        try:
            path = _ensure_era5(year, month, config)
            ds = xr.open_dataset(path)
            row = _extract_point(ds, ev["latitude"], ev["longitude"], ev["date"])
            ds.close()
        except Exception as exc:
            print(f"Skipping event {ev['event_id']}: {exc}")
            continue

        row["rainfall"] = ev["peak_rainfall_mm_per_hr"]  # trust the recorded ground truth over ERA5's tp
        row["lat"] = ev["latitude"]
        row["lon"] = ev["longitude"]
        row["cloudburst_occurred"] = 1
        rows.append(row)

    return pd.DataFrame(rows)


def build_negative_rows(config: dict, n_samples: int, events: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    region = config["region"]
    rng = random.Random(seed)
    event_dates = set(pd.to_datetime(events["date"]).dt.date)

    rows = []
    attempts = 0
    while len(rows) < n_samples and attempts < n_samples * 10:
        attempts += 1
        year = rng.choice(sorted(events["date"].str[:4].unique()) if "date" in events else ["2020"])
        month = f"{rng.randint(1, 12):02d}"
        lat = rng.uniform(region["lat_min"], region["lat_max"])
        lon = rng.uniform(region["lon_min"], region["lon_max"])

        try:
            path = _ensure_era5(year, month, config)
            ds = xr.open_dataset(path)
            day = rng.randint(1, 28)
            hour = rng.randint(0, 23)
            time = pd.Timestamp(year=int(year), month=int(month), day=day, hour=hour)
            if time.date() in event_dates:
                ds.close()
                continue
            row = _extract_point(ds, lat, lon, time)
            ds.close()
        except Exception as exc:
            print(f"Skipping negative sample: {exc}")
            continue

        row["lat"] = lat
        row["lon"] = lon
        row["cloudburst_occurred"] = 0
        rows.append(row)

    return pd.DataFrame(rows)


def build_dataset(negative_ratio: int = 3):
    """
    negative_ratio: how many negative (non-cloudburst) samples to
    generate per positive event, to control class balance.
    """
    config = load_config()
    events = pd.read_csv(EVENTS_PATH)

    positives = build_positive_rows(config)
    negatives = build_negative_rows(config, n_samples=len(positives) * negative_ratio, events=events)

    dataset = pd.concat([positives, negatives], ignore_index=True)
    dataset = dataset.dropna(subset=["temperature", "humidity", "pressure"])

    out_path = config["data"]["raw_path"]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    dataset.to_csv(out_path, index=False)
    print(f"Saved {len(dataset)} rows ({len(positives)} positive, {len(negatives)} negative) to {out_path}")
    return dataset


if __name__ == "__main__":
    build_dataset()

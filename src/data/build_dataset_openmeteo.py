"""
Build data/raw/cloudburst_dataset.csv (the model's training table) using
only free, key-less APIs — no CDS/ERA5 account needed:

  - Weather history: Open-Meteo Archive API (ERA5-backed reanalysis,
    https://archive-api.open-meteo.com), by lat/lon/date.
  - Positive examples: real historical cloudburst events from
    CLOUDPAK25_2010_2025_v3.csv (date, district, lat, lon,
    peak_rainfall_mm_per_hr).
  - Negative examples: random date/location samples within the same
    region/years, excluding event days.

Run once (or re-run when new events are added):
    python -m src.data.build_dataset_openmeteo
"""
import random
import time

import numpy as np
import pandas as pd
import requests

from src.data.load_data import load_config

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "pressure_msl",
    "cloud_cover",
    "wind_speed_10m",
    "precipitation",
]


def _fetch_day(lat: float, lon: float, date: pd.Timestamp, retries: int = 3) -> pd.DataFrame | None:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date.strftime("%Y-%m-%d"),
        "end_date": date.strftime("%Y-%m-%d"),
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "UTC",
    }
    for attempt in range(retries):
        try:
            resp = requests.get(ARCHIVE_URL, params=params, timeout=30)
            resp.raise_for_status()
            hourly = resp.json().get("hourly")
            if not hourly or all(v is None for v in hourly["temperature_2m"]):
                return None
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
            return df
        except requests.RequestException:
            time.sleep(1.5)
    return None


def _row_from_day(day_df: pd.DataFrame, peak_hour: int | None = None) -> dict | None:
    day_df = day_df.dropna(subset=["temperature", "humidity", "pressure"])
    if day_df.empty:
        return None
    if peak_hour is not None and peak_hour < len(day_df):
        idx = peak_hour
    else:
        # No known event hour: use the hour with the heaviest rainfall
        # (the atmosphere's most convective moment that day) as the
        # representative sample.
        idx = day_df["rainfall"].fillna(0).idxmax()
    row = day_df.loc[idx].to_dict()

    prior = idx - 3
    if prior in day_df.index:
        row["pressure_drop_3h"] = row["pressure"] - day_df.loc[prior, "pressure"]
    else:
        row["pressure_drop_3h"] = 0.0  # not enough prior hours that day: treat as "no known trend"
    row["temp_dewpoint_spread"] = row["temperature"] - row["dew_point"]
    return row


def build_positive_rows(config: dict) -> pd.DataFrame:
    events = pd.read_csv(config["data"]["events_path"])
    events["date"] = pd.to_datetime(events["date"])

    rows = []
    for _, ev in events.iterrows():
        day_df = _fetch_day(ev["latitude"], ev["longitude"], ev["date"])
        if day_df is None:
            print(f"Skipping event {ev['event_id']}: no weather data")
            continue
        row = _row_from_day(day_df)
        if row is None:
            continue
        # trust a recorded ground-truth rainfall rate over the reanalysis grid when we
        # have one (CLOUDPAK25); DFO events have no recorded rate, so keep the
        # reanalysis-derived value already in `row` from _row_from_day
        recorded_rainfall = ev.get("peak_rainfall_mm_per_hr")
        if pd.notna(recorded_rainfall):
            row["rainfall"] = recorded_rainfall
        row["lat"] = ev["latitude"]
        row["lon"] = ev["longitude"]
        row["district"] = ev["district"]
        row["date"] = ev["date"]
        row["cloudburst_occurred"] = 1
        rows.append(row)

    return pd.DataFrame(rows)


def build_negative_rows(config: dict, n_samples: int, events: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    region = config["region"]
    rng = random.Random(seed)
    event_dates = set(pd.to_datetime(events["date"]).dt.date)
    years = sorted(pd.to_datetime(events["date"]).dt.year.unique())

    rows = []
    attempts = 0
    while len(rows) < n_samples and attempts < n_samples * 8:
        attempts += 1
        year = rng.choice(years)
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        date = pd.Timestamp(year=int(year), month=month, day=day)
        if date.date() in event_dates:
            continue
        lat = rng.uniform(region["lat_min"], region["lat_max"])
        lon = rng.uniform(region["lon_min"], region["lon_max"])

        day_df = _fetch_day(lat, lon, date)
        if day_df is None:
            continue
        row = _row_from_day(day_df)
        if row is None:
            continue
        # A negative sample shouldn't itself look like a cloudburst.
        if row["rainfall"] and row["rainfall"] >= config["data"]["precipitation_threshold_mm_per_hr"]:
            continue

        row["lat"] = lat
        row["lon"] = lon
        row["district"] = None
        row["date"] = date
        row["cloudburst_occurred"] = 0
        rows.append(row)
        if len(rows) % 25 == 0:
            print(f"  negatives: {len(rows)}/{n_samples}")

    return pd.DataFrame(rows)


def build_dataset(negative_ratio: int = 3):
    """
    negative_ratio: how many negative (non-cloudburst) samples to
    generate per positive event, to control class balance.
    """
    config = load_config()
    events = pd.read_csv(config["data"]["events_path"])

    print(f"Fetching weather for {len(events)} historical events...")
    positives = build_positive_rows(config)
    print(f"Got {len(positives)} positive rows. Sampling negatives...")
    negatives = build_negative_rows(config, n_samples=len(positives) * negative_ratio, events=events)

    dataset = pd.concat([positives, negatives], ignore_index=True)
    dataset = dataset.drop(columns=["time"], errors="ignore")
    dataset = dataset.dropna(subset=["temperature", "humidity", "pressure"])

    out_path = config["data"]["raw_path"]
    dataset.to_csv(out_path, index=False)
    print(f"Saved {len(dataset)} rows ({len(positives)} positive, {len(negatives)} negative) to {out_path}")
    return dataset


if __name__ == "__main__":
    build_dataset()

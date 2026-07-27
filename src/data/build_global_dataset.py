"""
Build a global rain-driven-flood training table from the 600-event
sample in global_events.py, same approach as build_dataset_openmeteo.py
(Open-Meteo Archive API for historical weather, no key needed, works
anywhere in the world -- not just Pakistan's bounding box).

Negatives are built by jittering (+/- a few degrees) around real event
locations rather than sampling uniformly across the whole globe, so they
land on/near populated land rather than mid-ocean or empty desert --
keeping the classification problem meaningfully similar in spirit to how
the Pakistan negatives were built (same country/region, different
date/exact point).

Run:
    python -m src.data.build_global_dataset
"""
import random

import numpy as np
import pandas as pd

from src.data.build_dataset_openmeteo import _fetch_day, _row_from_day

EVENTS_PATH = "data/raw/global_flood_events.csv"
OUT_PATH = "data/raw/global_flood_dataset.csv"
PRECIP_THRESHOLD = 30  # mm/hr, same definition as the Pakistan dataset


def build_positive_rows(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, ev in events.iterrows():
        day_df = _fetch_day(ev["lat"], ev["lon"], ev["date"])
        if day_df is None:
            print(f"Skipping event {ev['event_id']}: no weather data")
            continue
        row = _row_from_day(day_df)
        if row is None:
            continue
        row["lat"] = ev["lat"]
        row["lon"] = ev["lon"]
        row["country"] = ev["country"]
        row["date"] = ev["date"]
        row["cloudburst_occurred"] = 1
        rows.append(row)
    return pd.DataFrame(rows)


def build_negative_rows(events: pd.DataFrame, n_samples: int, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    event_dates = set(pd.to_datetime(events["date"]).dt.date)
    years = sorted(pd.to_datetime(events["date"]).dt.year.unique())

    rows = []
    attempts = 0
    while len(rows) < n_samples and attempts < n_samples * 8:
        attempts += 1
        anchor = events.sample(1, random_state=rng.randint(0, 10_000)).iloc[0]
        lat = anchor["lat"] + rng.uniform(-2.0, 2.0)
        lon = anchor["lon"] + rng.uniform(-2.0, 2.0)
        year = rng.choice(years)
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        date = pd.Timestamp(year=int(year), month=month, day=day)
        if date.date() in event_dates:
            continue

        day_df = _fetch_day(lat, lon, date)
        if day_df is None:
            continue
        row = _row_from_day(day_df)
        if row is None:
            continue
        if row["rainfall"] and row["rainfall"] >= PRECIP_THRESHOLD:
            continue

        row["lat"] = lat
        row["lon"] = lon
        row["country"] = None
        row["date"] = date
        row["cloudburst_occurred"] = 0
        rows.append(row)
        if len(rows) % 100 == 0:
            print(f"  negatives: {len(rows)}/{n_samples}")

    return pd.DataFrame(rows)


def build_dataset(negative_ratio: int = 3):
    events = pd.read_csv(EVENTS_PATH)
    events["date"] = pd.to_datetime(events["date"])

    print(f"Fetching weather for {len(events)} global events...")
    positives = build_positive_rows(events)
    print(f"Got {len(positives)} positive rows. Sampling negatives...")
    negatives = build_negative_rows(events, n_samples=len(positives) * negative_ratio)

    dataset = pd.concat([positives, negatives], ignore_index=True)
    dataset = dataset.drop(columns=["time"], errors="ignore")
    dataset = dataset.dropna(subset=["temperature", "humidity", "pressure"])

    dataset.to_csv(OUT_PATH, index=False)
    print(f"Saved {len(dataset)} rows ({len(positives)} positive, {len(negatives)} negative) to {OUT_PATH}")
    return dataset


if __name__ == "__main__":
    build_dataset()

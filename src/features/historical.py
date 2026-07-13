"""
Two features that stand in for data we don't have free API access to:

- historical_flood_freq: real official per-district drainage/flood-control
  infrastructure ratings aren't published as an open dataset, so this uses
  the district's own historical cloudburst track record (from
  CLOUDPAK25_2010_2025_v3.csv) as a proxy for "how vulnerable is this
  place, historically" — inverse-distance-weighted so it also gives a
  sensible (smaller) value for points between known districts.
Real drainage geometry (distance to nearest mapped river/stream/canal,
and channel density) now comes from `src/data/waterways.py`, built on a
manually-downloaded HOTOSM waterways dataset — see that module's
docstring. The synthetic slope*urbanization drainage proxy that used to
live here has been replaced by it.

`historical_flood_freq` is a pure function of (lat, lon) plus fixed reference tables, so they
are guaranteed to compute identically at training time and at live
single-point inference time.
"""
import numpy as np
import pandas as pd

from src.data.geo_reference import DISTRICT_TOWNS

_EVENT_COUNTS = None


def _event_counts(events_path: str) -> dict:
    global _EVENT_COUNTS
    if _EVENT_COUNTS is None:
        events = pd.read_csv(events_path)
        _EVENT_COUNTS = events["district"].value_counts().to_dict()
    return _EVENT_COUNTS


def historical_flood_freq(lat: float, lon: float, events_path: str) -> float:
    counts = _event_counts(events_path)
    town_lats, town_lons, weights = [], [], []
    for district, town in DISTRICT_TOWNS.items():
        town_lats.append(town["lat"])
        town_lons.append(town["lon"])
        weights.append(counts.get(district, 0))

    town_lats = np.array(town_lats)
    town_lons = np.array(town_lons)
    weights = np.array(weights, dtype=float)

    dist_km = np.sqrt(
        ((town_lats - lat) * 111.32) ** 2
        + ((town_lons - lon) * 111.32 * np.cos(np.radians(lat))) ** 2
    )
    dist_km = np.maximum(dist_km, 1.0)
    score = float(np.sum(weights / dist_km ** 2))
    return float(np.log1p(score))


def attach_historical_flood_freq(df: pd.DataFrame, events_path: str) -> pd.DataFrame:
    df["historical_flood_freq"] = df.apply(
        lambda row: historical_flood_freq(row["lat"], row["lon"], events_path), axis=1
    )
    return df


def monthly_climatology_score(lat: float, lon: float, month: int, events_path: str) -> float:
    """
    Share (0-1) of this area's historical cloudburst events that happened
    in calendar `month`, distance-weighted the same way as
    `historical_flood_freq`. Used as a long-range (>16 day forecast
    horizon) seasonal baseline risk, since no weather model forecasts
    that far out — e.g. this will be high for a monsoon-belt district in
    July/August and near zero in December.
    """
    events = pd.read_csv(events_path)
    events["date"] = pd.to_datetime(events["date"])
    counts_by_month = events[events["date"].dt.month == month]["district"].value_counts().to_dict()
    total_counts = events["district"].value_counts().to_dict()

    town_lats, town_lons, month_w, total_w = [], [], [], []
    for district, town in DISTRICT_TOWNS.items():
        town_lats.append(town["lat"])
        town_lons.append(town["lon"])
        month_w.append(counts_by_month.get(district, 0))
        total_w.append(total_counts.get(district, 0))

    town_lats = np.array(town_lats)
    town_lons = np.array(town_lons)
    dist_km = np.sqrt(
        ((town_lats - lat) * 111.32) ** 2
        + ((town_lons - lon) * 111.32 * np.cos(np.radians(lat))) ** 2
    )
    dist_km = np.maximum(dist_km, 1.0)
    weights = 1.0 / dist_km ** 2

    month_score = float(np.sum(np.array(month_w) * weights))
    total_score = float(np.sum(np.array(total_w) * weights))
    if total_score <= 0:
        return 0.0
    return month_score / total_score

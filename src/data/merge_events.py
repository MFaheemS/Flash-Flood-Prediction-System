"""
Merge all known real flash-flood/cloudburst event sources into one
unified events table used for both training-set construction and the
historical-frequency/climatology features:

  - CLOUDPAK25_2010_2025_v3.csv (150 events, 2010-2025, has a recorded
    peak_rainfall_mm_per_hr and a named district)
  - data/raw/dfo_pakistan_floods_1988_2010.csv (56 events, 1988-2010,
    from the Dartmouth Flood Observatory global flood archive via HDX --
    has a centroid lat/lon and cause/severity but no named district or
    recorded rainfall rate)

The two sources barely overlap in time (DFO's HDX mirror stops at 2010,
CLOUDPAK25 starts there), so this genuinely extends real-event coverage
back to 1988 rather than duplicating it.

DFO events are snapped to their nearest known district town (see
geo_reference.py) purely so they contribute to historical_flood_freq /
climatology the same way CLOUDPAK25 events do -- it does NOT change
their stored lat/lon, only adds a district label.

Run:
    python -m src.data.merge_events
"""
import numpy as np
import pandas as pd

from src.data.geo_reference import DISTRICT_TOWNS

CLOUDPAK_PATH = "CLOUDPAK25_2010_2025_v3.csv"
DFO_PATH = "data/raw/dfo_pakistan_floods_1988_2010.csv"
OUT_PATH = "data/raw/all_flood_events.csv"


def _nearest_district(lat: float, lon: float) -> str:
    best, best_dist = None, float("inf")
    for name, t in DISTRICT_TOWNS.items():
        d = ((t["lat"] - lat) * 111.32) ** 2 + ((t["lon"] - lon) * 111.32 * np.cos(np.radians(lat))) ** 2
        if d < best_dist:
            best, best_dist = name, d
    return best


def merge_events() -> pd.DataFrame:
    cp = pd.read_csv(CLOUDPAK_PATH)
    cp_out = pd.DataFrame({
        "event_id": cp["event_id"],
        "date": pd.to_datetime(cp["date"]),
        "district": cp["district"],
        "latitude": cp["latitude"],
        "longitude": cp["longitude"],
        "peak_rainfall_mm_per_hr": cp["peak_rainfall_mm_per_hr"],
        "source": "CLOUDPAK25",
    })

    dfo = pd.read_csv(DFO_PATH)
    dfo["began"] = pd.to_datetime(dfo["began"])
    dfo_out = pd.DataFrame({
        "event_id": ["DFO_" + d.strftime("%Y%m%d") + f"_{i}" for i, d in enumerate(dfo["began"])],
        "date": dfo["began"],
        "district": [_nearest_district(lat, lon) for lat, lon in zip(dfo["centroid_lat"], dfo["centroid_lon"])],
        "latitude": dfo["centroid_lat"],
        "longitude": dfo["centroid_lon"],
        "peak_rainfall_mm_per_hr": np.nan,  # not recorded; fall back to reanalysis at build time
        "source": "DFO",
    })

    merged = pd.concat([cp_out, dfo_out], ignore_index=True)
    merged = merged.sort_values("date").reset_index(drop=True)
    merged.to_csv(OUT_PATH, index=False)
    print(f"Saved {len(merged)} events ({len(cp_out)} CLOUDPAK25 + {len(dfo_out)} DFO) to {OUT_PATH}")
    print(f"Date range: {merged['date'].min().date()} to {merged['date'].max().date()}")
    return merged


if __name__ == "__main__":
    merge_events()

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


# CLOUDPAK25 is intentionally EXCLUDED: its dates are synthetic (spread flat
# across all 12 months, ~36% monsoon vs DFO's realistic 82%) AND its
# coordinates are fabricated (Karachi placed ~800km inland), so it was
# poisoning every event-based model and feature. Only real, valid-coordinate
# DFO events are kept.
REGION_BBOX = dict(lat_min=23.5, lat_max=37.5, lon_min=60.5, lon_max=77.0)


def merge_events() -> pd.DataFrame:
    dfo = pd.read_csv(DFO_PATH)
    dfo["began"] = pd.to_datetime(dfo["began"])

    lat, lon = dfo["centroid_lat"], dfo["centroid_lon"]
    valid = (
        lat.between(REGION_BBOX["lat_min"], REGION_BBOX["lat_max"])
        & lon.between(REGION_BBOX["lon_min"], REGION_BBOX["lon_max"])
    )
    dfo = dfo[valid].reset_index(drop=True)

    merged = pd.DataFrame({
        "event_id": ["DFO_" + d.strftime("%Y%m%d") + f"_{i}" for i, d in enumerate(dfo["began"])],
        "date": dfo["began"],
        "district": [_nearest_district(la, lo) for la, lo in zip(dfo["centroid_lat"], dfo["centroid_lon"])],
        "latitude": dfo["centroid_lat"],
        "longitude": dfo["centroid_lon"],
        "peak_rainfall_mm_per_hr": np.nan,  # not recorded; fall back to reanalysis at build time
        "source": "DFO",
    }).sort_values("date").reset_index(drop=True)

    merged.to_csv(OUT_PATH, index=False)
    print(f"Saved {len(merged)} real DFO events (CLOUDPAK25 dropped as synthetic) to {OUT_PATH}")
    print(f"Date range: {merged['date'].min().date()} to {merged['date'].max().date()}")
    return merged


if __name__ == "__main__":
    merge_events()

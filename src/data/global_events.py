"""
Build a global, rain-driven flood event list from the Dartmouth Flood
Observatory global archive (same source as the Pakistan-only extract in
merge_events.py, but unfiltered by country here) -- 4,029 events
worldwide, 1985-2010, via the HDX mirror:
https://data.humdata.org/dataset/global-active-archive-of-large-flood-events-dfo

Filters to rain-driven causes (excludes snowmelt-only, dam/levee break,
ice jam -- not flash-flood-relevant) and takes a stratified random sample
across countries so the training set isn't dominated by whichever
country the archive happens to have the most records for.

Run:
    python -m src.data.global_events
"""
import numpy as np
import pandas as pd
import shapefile

SHP_PATH = r"C:\Users\M.Faheem\AppData\Local\Temp\dfo_extract\wlf_nhr_fl_dfomasterlist_20190418.shp"
OUT_PATH = "data/raw/global_flood_events.csv"

RAIN_CAUSES = {
    "heavy rain", "torrential rain", "brief torrential rain", "monsoonal rain",
    "monsoon rain", "monsoon rains", "tropical cyclone", "extra-tropical cyclone",
    "rain and snowmelt",
}

SAMPLE_SIZE = 600
RANDOM_STATE = 42


def load_all_events() -> pd.DataFrame:
    sf = shapefile.Reader(SHP_PATH)
    recs = [r.as_dict() for r in sf.records()]
    df = pd.DataFrame(recs)
    df = df.rename(columns={
        "Country__c": "country", "Began": "date", "Main_cause": "cause",
        "Severity__": "severity", "Magnitude": "magnitude", "Dead": "dead",
        "Centroid_X": "lon", "Centroid_Y": "lat", "Detailed_L": "location",
    })
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "lat", "lon", "country"])
    df = df[df["country"].str.strip() != ""]
    df["cause_norm"] = df["cause"].str.strip().str.lower()
    return df


def build_global_event_sample(sample_size: int = SAMPLE_SIZE) -> pd.DataFrame:
    df = load_all_events()
    rain_df = df[df["cause_norm"].isin(RAIN_CAUSES)].copy()
    print(f"{len(df)} total global events, {len(rain_df)} rain-driven")

    # Stratified by country: cap any single country's share so e.g. the US
    # (335 records) can't dominate a 600-event sample.
    max_per_country = max(3, sample_size // rain_df["country"].nunique() * 3)
    parts = [
        group.sample(min(len(group), max_per_country), random_state=RANDOM_STATE)
        for _, group in rain_df.groupby("country")
    ]
    capped = pd.concat(parts, ignore_index=True)
    sample = capped.sample(min(sample_size, len(capped)), random_state=RANDOM_STATE).reset_index(drop=True)

    sample["event_id"] = ["GLOBAL_" + d.strftime("%Y%m%d") + f"_{i}" for i, d in enumerate(sample["date"])]
    out = sample[["event_id", "date", "country", "lat", "lon", "cause", "severity", "magnitude", "dead", "location"]]
    out.to_csv(OUT_PATH, index=False)
    print(f"Saved {len(out)} events from {out['country'].nunique()} countries to {OUT_PATH}")
    print(out["country"].value_counts().head(15))
    return out


if __name__ == "__main__":
    build_global_event_sample()

"""
Build a monthly region-panel flood dataset from the Google Earth Engine
exports in Datasets/ (user-provided, one folder per Pakistani region):

  Flood.csv  - monthly flood label ("Yes" = a flood occurred that month)
  Pre.csv  / pre1.csv   - daily precipitation   (2011-2021 / 2000-2010)
  Temp.csv / temp1.csv  - daily LST day temp    (MODIS LST_Day_1km)
  Ndsi.csv / ndsi1.csv  - daily snow cover index (NDSI, -1..1)
  Veg.csv  / veg1.csv   - ~16-day vegetation index (NDVI, scaled x10000)

These are REAL satellite/ground observations with REAL labels and, crucially,
naturally-matched negatives (the same region in non-flood months) -- unlike
the synthetic random negatives used elsewhere in this project. Snow cover
(NDSI) and vegetation (NDVI) are new physical factors not present in the
other models, both directly relevant to flash floods (snowmelt pulses;
vegetation buffering runoff).

Output: data/raw/satellite_flood_dataset.csv, one row per region-month with
aggregated features + a binary `flood` label.

Run:
    python -m src.data.build_satellite_dataset
"""
import os

import numpy as np
import pandas as pd

DATASETS_DIR = "Datasets"
REGIONS = ["Balochistan", "Federal", "Gilgit", "Kpk", "Punjab", "Sindh"]
OUT_PATH = "data/raw/satellite_flood_dataset.csv"

# Regions mix full names, 3-letter abbreviations, and a "Janruary" typo, so
# map by the first three letters (handles Jan/January/Janruary, Jul/July, ...).
_MONTH_PREFIX = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def month_to_num(name) -> "int | float":
    key = str(name).strip().lower()[:3]
    return _MONTH_PREFIX.get(key, np.nan)


def _read_daily(region: str, base: str, alt: str, value_col: str, ndvi: bool = False) -> pd.DataFrame:
    """Concatenate the two GEE exports (2000-2010 `alt` + 2011-2021 `base`)
    for one variable into a single daily series with a datetime index."""
    frames = []
    for fname in (alt, base):
        path = os.path.join(DATASETS_DIR, region, fname)
        if not os.path.exists(path):
            continue
        d = pd.read_csv(path)
        d = d.rename(columns={d.columns[0]: "date", value_col: "value"})
        d["date"] = pd.to_datetime(d["date"], format="mixed", errors="coerce")
        if ndvi:
            d["value"] = d["value"].astype(str).str.replace(",", "", regex=False)
        d["value"] = pd.to_numeric(d["value"], errors="coerce")
        if ndvi:
            d["value"] = d["value"] / 10000.0  # MODIS NDVI scale factor
        frames.append(d[["date", "value"]].dropna(subset=["date"]))
    if not frames:
        return pd.DataFrame(columns=["date", "value"])
    out = pd.concat(frames, ignore_index=True).drop_duplicates("date").sort_values("date")
    return out


def _monthly_agg(daily: pd.DataFrame, aggs: dict) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    daily = daily.copy()
    daily["year"] = daily["date"].dt.year
    daily["month"] = daily["date"].dt.month
    g = daily.groupby(["year", "month"])["value"].agg(list(aggs.values()))
    g.columns = list(aggs.keys())
    return g.reset_index()


def build_region(region: str) -> pd.DataFrame:
    pre = _monthly_agg(_read_daily(region, "Pre.csv", "pre1.csv", "precipitation"),
                        {"precip_total": "sum", "precip_max": "max", "precip_days": lambda s: (s > 1).sum()})
    temp = _monthly_agg(_read_daily(region, "Temp.csv", "temp1.csv", "LST_Day_1km"),
                        {"temp_mean": "mean", "temp_max": "max"})
    ndsi = _monthly_agg(_read_daily(region, "Ndsi.csv", "ndsi1.csv", "NDSI"),
                        {"snow_mean": "mean", "snow_max": "max"})
    ndvi = _monthly_agg(_read_daily(region, "Veg.csv", "veg1.csv", "NDVI", ndvi=True),
                        {"veg_mean": "mean"})

    df = pre
    for other in (temp, ndsi, ndvi):
        if not other.empty:
            df = df.merge(other, on=["year", "month"], how="outer")
    df["region"] = region

    # labels
    flood = pd.read_csv(os.path.join(DATASETS_DIR, region, "Flood.csv"))
    flood["month"] = flood["Months"].map(month_to_num)
    flood["flood"] = flood["Flood"].astype(str).str.strip().str.lower().eq("yes").astype(int)
    flood = flood.rename(columns={"Years": "year"})[["year", "month", "flood"]]

    df = df.merge(flood, on=["year", "month"], how="inner")
    return df


def build_dataset() -> pd.DataFrame:
    frames = [build_region(r) for r in REGIONS]
    df = pd.concat(frames, ignore_index=True)

    # antecedent precipitation: previous month's total (already-wet ground)
    df = df.sort_values(["region", "year", "month"]).reset_index(drop=True)
    df["precip_prev_month"] = df.groupby("region")["precip_total"].shift(1)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    pos = int(df["flood"].sum())
    print(f"Saved {len(df)} region-months ({pos} floods, {len(df)-pos} non-floods) to {OUT_PATH}")
    print(f"Regions: {df['region'].nunique()} | years: {int(df['year'].min())}-{int(df['year'].max())}")
    print("Flood rate by region:")
    print(df.groupby("region")["flood"].mean().round(3).to_string())
    return df


if __name__ == "__main__":
    build_dataset()

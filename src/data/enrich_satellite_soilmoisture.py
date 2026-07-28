"""
Add ERA5-Land soil moisture to the satellite monthly flood dataset, fetched
from the Open-Meteo archive API (https://archive-api.open-meteo.com) -- free,
no API key, ERA5-Land backed, available back to 1940. This is the
"ERA5-Land soil moisture via GEE" recommendation, obtained without needing a
Google Earth Engine account.

For each of the 6 regions we query daily soil moisture at a representative
centroid for the full 2000-2021 span (one request per region covers the whole
range), aggregate to monthly means for two depths, and add:
  soil_moist_surface   (0-7cm mean, m3/m3)   -- fast-responding topsoil
  soil_moist_root      (7-28cm mean, m3/m3)  -- root-zone storage
  soil_moist_prev_month(surface, previous month) -- antecedent saturation

Region-centroid soil moisture is an approximation of the region-averaged GEE
series already in the dataset, but consistent with how those region series
were produced, and physically the antecedent-wetness signal is broad-scale.

Run (after build_satellite_dataset):
    python -m src.data.enrich_satellite_soilmoisture
"""
import time

import pandas as pd
import requests

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DATASET_PATH = "data/raw/satellite_flood_dataset.csv"

# Representative centroids for each region's flood-relevant area.
REGION_CENTROIDS = {
    "Balochistan": (29.0, 66.5),
    "Federal": (33.68, 73.05),
    "Gilgit": (35.9, 74.3),
    "Kpk": (34.4, 71.8),
    "Punjab": (31.0, 72.3),
    "Sindh": (26.5, 68.3),
}

START, END = "2000-01-01", "2021-12-31"


def _fetch_region_monthly(lat: float, lon: float, retries: int = 4) -> pd.DataFrame:
    for attempt in range(retries):
        try:
            resp = requests.get(
                ARCHIVE_URL,
                params={
                    "latitude": lat, "longitude": lon,
                    "start_date": START, "end_date": END,
                    "daily": "soil_moisture_0_to_7cm_mean,soil_moisture_7_to_28cm_mean",
                    "timezone": "UTC",
                },
                timeout=60,
            )
            if resp.status_code == 429:
                time.sleep(min(30, 5 * 2 ** attempt))
                continue
            resp.raise_for_status()
            d = resp.json()["daily"]
            df = pd.DataFrame({
                "date": pd.to_datetime(d["time"]),
                "soil_moist_surface": d["soil_moisture_0_to_7cm_mean"],
                "soil_moist_root": d["soil_moisture_7_to_28cm_mean"],
            })
            df["year"] = df["date"].dt.year
            df["month"] = df["date"].dt.month
            g = df.groupby(["year", "month"])[["soil_moist_surface", "soil_moist_root"]].mean().reset_index()
            return g
        except requests.RequestException:
            time.sleep(min(30, 5 * 2 ** attempt))
    raise RuntimeError(f"soil moisture fetch failed for ({lat},{lon})")


def enrich():
    df = pd.read_csv(DATASET_PATH)
    parts = []
    for region, (lat, lon) in REGION_CENTROIDS.items():
        print(f"Fetching ERA5-Land soil moisture for {region} ({lat},{lon})...")
        g = _fetch_region_monthly(lat, lon)
        g["region"] = region
        parts.append(g)
        time.sleep(1.0)

    sm = pd.concat(parts, ignore_index=True)
    df = df.merge(sm, on=["region", "year", "month"], how="left")

    df = df.sort_values(["region", "year", "month"]).reset_index(drop=True)
    df["soil_moist_prev_month"] = df.groupby("region")["soil_moist_surface"].shift(1)

    df.to_csv(DATASET_PATH, index=False)
    print(f"Saved enriched dataset ({len(df)} rows, {len(df.columns)} cols) to {DATASET_PATH}")
    print(df[["soil_moist_surface", "soil_moist_root", "soil_moist_prev_month"]].describe().round(3).to_string())
    return df


if __name__ == "__main__":
    enrich()

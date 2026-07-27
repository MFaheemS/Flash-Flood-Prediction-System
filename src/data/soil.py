"""
Soil texture (% clay) from ISRIC SoilGrids (https://rest.isric.org),
free, key-less REST API. Clay-heavy soils drain poorly and shed rainfall
as surface runoff rather than absorbing it -- a genuine physical flash-
flood factor, distinct from the terrain/drainage-geometry features
already in the pipeline.
"""
import time

import numpy as np
import pandas as pd
import requests

SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"


def fetch_clay_pct(lat: float, lon: float, retries: int = 3) -> float:
    for attempt in range(retries):
        try:
            resp = requests.get(
                SOILGRIDS_URL,
                params={"lon": lon, "lat": lat, "property": "clay", "depth": "0-5cm", "value": "mean"},
                timeout=15,
            )
            resp.raise_for_status()
            layers = resp.json()["properties"]["layers"]
            mean_gkg = layers[0]["depths"][0]["values"]["mean"]
            if mean_gkg is None:
                return np.nan
            return mean_gkg / 10.0  # g/kg -> %
        except (requests.RequestException, KeyError, IndexError):
            time.sleep(1.5)
    return np.nan


def attach_soil_clay_pct(df: pd.DataFrame) -> pd.DataFrame:
    unique_points = df[["lat", "lon"]].drop_duplicates()
    cache = {}
    for _, row in unique_points.iterrows():
        key = (round(row["lat"], 4), round(row["lon"], 4))
        cache[key] = fetch_clay_pct(row["lat"], row["lon"])

    df["soil_clay_pct"] = df.apply(
        lambda r: cache[(round(r["lat"], 4), round(r["lon"], 4))], axis=1
    )
    return df

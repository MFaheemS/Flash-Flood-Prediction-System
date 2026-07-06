"""
End-to-end live cloudburst prediction for a single location: fetch the
latest weather from Open-Meteo, attach terrain (elevation/slope) and
urbanization index, run the trained model, and attach a SHAP-based
explanation.

Usage:
    python -m src.models.predict_live --lat 33.6844 --lon 73.0479
"""
import argparse
import os

import pandas as pd

from src.data.fetch_live_weather import fetch_latest_row
from src.data.load_data import load_config
from src.data.terrain import attach_terrain, fetch_terrain_openmeteo, load_terrain_index
from src.data.urbanization import build_urbanization_proxy
from src.features.historical import attach_drainage_risk_index, attach_historical_flood_freq
from src.models.predict import explain, predict


def _attach_terrain_for_point(row: pd.DataFrame, config: dict) -> pd.DataFrame:
    terrain_path = config["data"]["terrain_index_path"]
    if os.path.exists(terrain_path):
        terrain_df = load_terrain_index(terrain_path)
        # If this exact point isn't in the cache, fall back to fetching it.
        exists = ((terrain_df["lat"] - row["lat"].iloc[0]).abs() < 1e-6) & (
            (terrain_df["lon"] - row["lon"].iloc[0]).abs() < 1e-6
        )
        if exists.any():
            return attach_terrain(row, terrain_df)
    # No cached terrain for this point yet: fetch just this one point on the fly.
    points = row[["lat", "lon"]]
    terrain_df = fetch_terrain_openmeteo(points, out_path=terrain_path + ".tmp")
    return attach_terrain(row, terrain_df)


def attach_derived_features(row: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Attach terrain, urbanization, historical-vulnerability and drainage-risk features."""
    row = _attach_terrain_for_point(row, config)
    urban = build_urbanization_proxy(row[["lat", "lon"]])
    row["urbanization_index"] = urban["urbanization_index"].values
    row = attach_historical_flood_freq(row, config["data"]["events_path"])
    row = attach_drainage_risk_index(row)
    return row


def predict_live(lat: float, lon: float) -> pd.DataFrame:
    config = load_config()
    row = fetch_latest_row(lat, lon)
    row = attach_derived_features(row, config)
    row = predict(row)
    row = explain(row)
    return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    args = parser.parse_args()

    result = predict_live(args.lat, args.lon)
    print(result[["lat", "lon", "cloudburst_probability", "cloudburst_prediction", "risk_explanation"]])

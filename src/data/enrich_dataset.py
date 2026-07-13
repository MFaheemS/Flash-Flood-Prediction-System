"""
Attach terrain (elevation/slope), urbanization, historical-vulnerability,
and drainage-risk features to data/raw/cloudburst_dataset.csv in place,
after `build_dataset_openmeteo.py` has produced the base weather columns.

Run once after build_dataset_openmeteo:
    python -m src.data.enrich_dataset
"""
import pandas as pd

from src.data.load_data import load_config
from src.data.terrain import attach_terrain, fetch_terrain_openmeteo
from src.data.urbanization import build_urbanization_proxy
from src.data.waterways import attach_waterway_features
from src.features.historical import attach_historical_flood_freq


def enrich():
    config = load_config()
    raw_path = config["data"]["raw_path"]
    df = pd.read_csv(raw_path)

    unique_points = df[["lat", "lon"]].drop_duplicates().reset_index(drop=True)
    print(f"Fetching terrain for {len(unique_points)} unique points...")
    terrain_df = fetch_terrain_openmeteo(unique_points, out_path=config["data"]["terrain_index_path"])
    df = attach_terrain(df, terrain_df)

    print("Computing urbanization proxy...")
    urban_df = build_urbanization_proxy(unique_points)
    urban_df.to_csv(config["data"]["urbanization_path"], index=False)
    df = df.merge(urban_df, on=["lat", "lon"], how="left")

    print("Computing historical flood frequency...")
    df = attach_historical_flood_freq(df, config["data"]["events_path"])

    print("Computing waterway distance/density...")
    df = attach_waterway_features(df, config["data"]["waterways_path"])

    df.to_csv(raw_path, index=False)
    print(f"Saved enriched dataset ({len(df)} rows, {len(df.columns)} columns) to {raw_path}")
    return df


if __name__ == "__main__":
    enrich()

"""
Attach terrain (elevation/slope) and soil (clay %, antecedent wetness) to
data/raw/global_flood_dataset.csv, after build_global_dataset.py has
produced the base weather columns.

Deliberately does NOT attach urbanization_index, waterway
distance/density, or historical_flood_freq -- those are Pakistan-specific
proxies (a hardcoded list of Pakistani towns, a Pakistan-only HOTOSM
waterways file, a Pakistan-only event archive) with no global equivalent
already wired up. The global model is intentionally scoped to
weather + terrain + soil, so its factor rankings are actually comparable
apples-to-apples with what's physically available everywhere, not
diluted by features that only exist for one country.

Run:
    python -m src.data.enrich_global_dataset
"""
import pandas as pd

from src.data.load_data import load_config
from src.data.soil import attach_soil_clay_pct
from src.data.soil_moisture import attach_soil_wetness
from src.data.terrain import attach_terrain, fetch_terrain_openmeteo


def enrich():
    config = load_config()
    raw_path = config["global_flood"]["raw_path"]
    df = pd.read_csv(raw_path)

    unique_points = df[["lat", "lon"]].drop_duplicates().reset_index(drop=True)
    print(f"Fetching terrain for {len(unique_points)} unique points...")
    terrain_df = fetch_terrain_openmeteo(unique_points, out_path="data/raw/global_terrain_index.csv")
    df = attach_terrain(df, terrain_df)

    print("Fetching soil clay % (ISRIC SoilGrids)...")
    df = attach_soil_clay_pct(df)

    print(f"Fetching antecedent soil wetness (NASA POWER) for {len(df)} dated rows...")
    df = attach_soil_wetness(df)

    df.to_csv(raw_path, index=False)
    print(f"Saved enriched dataset ({len(df)} rows, {len(df.columns)} columns) to {raw_path}")
    return df


if __name__ == "__main__":
    enrich()

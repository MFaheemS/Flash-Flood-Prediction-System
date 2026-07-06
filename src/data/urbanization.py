"""
Load an urbanization index (e.g. from GHSL built-up area, WorldPop
population density, or VIIRS nighttime lights, exported to a CSV of
lat, lon, urbanization_index) and join it onto ERA5 grid points by
nearest coordinate.
"""
import numpy as np
import pandas as pd

from src.data.geo_reference import DISTRICT_TOWNS


def build_urbanization_proxy(points: pd.DataFrame) -> pd.DataFrame:
    """
    Gravity-model proxy for urbanization, used in place of GHSL/WorldPop/
    VIIRS (which need a Google Earth Engine account to export). Each
    point's index is the population of every known town divided by
    squared distance, summed over all towns, then normalized to 0-1.
    Points close to a big city score high; remote rural points score low.
    """
    town_lats = np.array([t["lat"] for t in DISTRICT_TOWNS.values()])
    town_lons = np.array([t["lon"] for t in DISTRICT_TOWNS.values()])
    town_pop = np.array([t["population"] for t in DISTRICT_TOWNS.values()], dtype=float)

    def score(lat, lon):
        dist_km = np.sqrt(
            ((town_lats - lat) * 111.32) ** 2
            + ((town_lons - lon) * 111.32 * np.cos(np.radians(lat))) ** 2
        )
        dist_km = np.maximum(dist_km, 1.0)  # avoid div-by-zero when exactly on a town
        return float(np.sum(town_pop / dist_km ** 2))

    # log1p only (no min-max scaling): min-max would depend on whatever
    # batch of points happens to be passed in, which would silently
    # change the meaning of this feature between training and live
    # single-point inference. XGBoost doesn't need features on a 0-1
    # scale, so a fixed, batch-independent transform is used instead.
    raw = points.apply(lambda row: score(row["lat"], row["lon"]), axis=1)
    out = points[["lat", "lon"]].copy()
    out["urbanization_index"] = np.log1p(raw).values
    return out


def load_urbanization_index(path: str) -> pd.DataFrame:
    return pd.read_csv(path)  # expects columns: lat, lon, urbanization_index


def attach_urbanization(weather_df: pd.DataFrame, urban_df: pd.DataFrame) -> pd.DataFrame:
    """Nearest-neighbor join of urbanization_index onto each weather row's lat/lon."""
    urban_coords = urban_df[["lat", "lon"]].to_numpy()

    def nearest_index(lat, lon):
        dists = np.sqrt((urban_coords[:, 0] - lat) ** 2 + (urban_coords[:, 1] - lon) ** 2)
        return urban_df.iloc[dists.argmin()]["urbanization_index"]

    weather_df["urbanization_index"] = weather_df.apply(
        lambda row: nearest_index(row["lat"], row["lon"]), axis=1
    )
    return weather_df

"""
Real drainage-relevant geometry: rivers, streams, canals, and drains for
Pakistan from HumanitarianOSM (HOTOSM), downloaded manually as a GeoJSON
of LineStrings (see config.yaml: data.waterways_path).

Replaces the earlier synthetic `drainage_risk_index` (slope * urbanization
guess) with two measured features:

  - distance_to_waterway_km: distance from a point to the nearest mapped
    waterway of any kind. Flash floods concentrate along drainage lines,
    so proximity to a river/stream/canal is a direct physical risk factor
    (as opposed to a proxy).
  - waterway_count_10km: how many separate waterway segments exist within
    10km, a rough density measure. Left un-signed deliberately (more
    channels could mean either "well-drained" or "flood-prone lowland
    criss-crossed by channels") — the model learns which direction it
    points in from the training data rather than that being hand-coded.

Coordinates are treated as degrees and converted to a local flat km grid
(scaling longitude by cos(latitude)) before any distance calculation,
since the whole dataset is confined to Pakistan's ~14 degree extent, where
that approximation is accurate to well under 1%.
"""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd
from shapely.geometry import shape
from shapely.strtree import STRtree

KM_PER_DEG_LAT = 111.32


def _to_local_km(lon, lat, lat0: float):
    """Scale (lon, lat) degrees to an approximate flat km grid centered near lat0."""
    return lon * KM_PER_DEG_LAT * np.cos(np.radians(lat0)), lat * KM_PER_DEG_LAT


@lru_cache(maxsize=1)
def _load_index(path: str):
    with open(path, encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    geoms = []
    for feat in data["features"]:
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            geoms.append(shape(geom))
        except Exception:
            continue

    tree = STRtree(geoms)
    return tree, geoms


def _nearest_and_count(lat: float, lon: float, path: str, radius_km: float = 10.0):
    tree, geoms = _load_index(path)

    x, y = _to_local_km(lon, lat, lat)
    from shapely.geometry import Point
    from shapely.ops import transform as shp_transform

    point_km = Point(x, y)

    def to_km(geom):
        return shp_transform(lambda lons, lats: (
            np.array(lons) * KM_PER_DEG_LAT * np.cos(np.radians(lat)),
            np.array(lats) * KM_PER_DEG_LAT,
        ), geom)

    # Narrow candidates with the tree in degree-space first (buffer generous
    # enough to not miss anything within radius_km in km-space), then do
    # exact km-space distance on the shortlist only (fast: full dataset is
    # ~35k lines, but only a handful fall in any query envelope).
    deg_radius = (radius_km / KM_PER_DEG_LAT) * 1.5
    from shapely.geometry import Point as DegPoint

    deg_point = DegPoint(lon, lat)
    candidate_idx = tree.query(deg_point.buffer(deg_radius))

    if len(candidate_idx) == 0:
        # nothing nearby in the generous buffer: fall back to a global
        # nearest-geometry query (rare, e.g. remote areas)
        nearest_idx = tree.nearest(deg_point)
        nearest_km = to_km(geoms[nearest_idx]).distance(point_km)
        return float(nearest_km), 0

    dists = [to_km(geoms[i]).distance(point_km) for i in candidate_idx]
    nearest_km = min(dists)
    count_within = sum(1 for d in dists if d <= radius_km)
    return float(nearest_km), int(count_within)


def waterway_features(lat: float, lon: float, waterways_path: str, radius_km: float = 10.0) -> dict:
    nearest_km, count = _nearest_and_count(lat, lon, waterways_path, radius_km)
    return {"distance_to_waterway_km": nearest_km, "waterway_count_10km": count}


def attach_waterway_features(df: pd.DataFrame, waterways_path: str, radius_km: float = 10.0) -> pd.DataFrame:
    feats = df.apply(
        lambda row: waterway_features(row["lat"], row["lon"], waterways_path, radius_km),
        axis=1,
        result_type="expand",
    )
    df["distance_to_waterway_km"] = feats["distance_to_waterway_km"]
    df["waterway_count_10km"] = feats["waterway_count_10km"]
    return df

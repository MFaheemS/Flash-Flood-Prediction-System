"""
Load terrain data (elevation + slope), exported to a CSV of
lat, lon, elevation, slope, and join it onto ERA5 grid points by
nearest coordinate.

Two ways to build the CSV:
- `fetch_terrain_from_api` — no download needed, queries the free
  Open-Elevation API (https://open-elevation.com) per point and
  estimates slope from small lat/lon offset samples. Good default
  when you can't get an SRTM/DEM file locally.
- `build_terrain_index_from_dem` — samples a local DEM GeoTIFF
  directly (requires rasterio), if you do have one.

Cloudbursts are strongly orographic: moist air forced upward over
mountain slopes condenses rapidly, so elevation and slope are
high-value features alongside CAPE and humidity.
"""
import time

import numpy as np
import pandas as pd
import requests


def load_terrain_index(path: str) -> pd.DataFrame:
    return pd.read_csv(path)  # expects columns: lat, lon, elevation, slope


def attach_terrain(weather_df: pd.DataFrame, terrain_df: pd.DataFrame) -> pd.DataFrame:
    """Nearest-neighbor join of elevation/slope onto each weather row's lat/lon."""
    terrain_coords = terrain_df[["lat", "lon"]].to_numpy()

    def nearest_row(lat, lon):
        dists = np.sqrt((terrain_coords[:, 0] - lat) ** 2 + (terrain_coords[:, 1] - lon) ** 2)
        return terrain_df.iloc[dists.argmin()]

    nearest = weather_df.apply(lambda row: nearest_row(row["lat"], row["lon"]), axis=1)
    weather_df["elevation"] = nearest["elevation"].values
    weather_df["slope"] = nearest["slope"].values
    return weather_df


def _query_elevations(lats, lons, api_url: str, retries: int = 3, pause: float = 1.0):
    locations = [{"latitude": lat, "longitude": lon} for lat, lon in zip(lats, lons)]
    last_exc = None
    for attempt in range(retries):
        try:
            resp = requests.post(api_url, json={"locations": locations}, timeout=30)
            resp.raise_for_status()
            return [r["elevation"] for r in resp.json()["results"]]
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(pause)
    raise last_exc


def fetch_terrain_from_api(
    points: pd.DataFrame,
    out_path: str,
    api_url: str = "https://api.open-elevation.com/api/v1/lookup",
    offset_deg: float = 0.01,
    batch_size: int = 100,
) -> pd.DataFrame:
    """
    Build the terrain index CSV with no local DEM file needed: queries
    elevation for each lat/lon in `points` via the free Open-Elevation
    API, and approximates local slope (degrees) by also sampling four
    neighboring points offset by `offset_deg` (~1.1km at 0.01 degrees)
    and computing the elevation gradient across them.

    The public Open-Elevation instance is free but can be slow or rate
    limited for large point sets; requests are batched and retried.
    """
    lats = points["lat"].to_numpy()
    lons = points["lon"].to_numpy()
    n = len(points)

    all_lats, all_lons = [], []
    for lat, lon in zip(lats, lons):
        all_lats += [lat, lat + offset_deg, lat - offset_deg, lat, lat]
        all_lons += [lon, lon, lon, lon + offset_deg, lon - offset_deg]

    elevations = []
    for i in range(0, len(all_lats), batch_size):
        chunk = _query_elevations(all_lats[i:i + batch_size], all_lons[i:i + batch_size], api_url)
        elevations.extend(chunk)
        if i + batch_size < len(all_lats):
            time.sleep(1.0)  # be polite to the free public instance

    elevations = np.array(elevations, dtype=float).reshape(n, 5)
    center, north, south, east, west = (elevations[:, j] for j in range(5))

    meters_per_deg_lat = 111_320
    meters_per_deg_lon = meters_per_deg_lat * np.cos(np.radians(lats))
    dz_ns = (north - south) / (2 * offset_deg * meters_per_deg_lat)
    dz_ew = (east - west) / (2 * offset_deg * meters_per_deg_lon)
    slope_deg = np.degrees(np.arctan(np.sqrt(dz_ns ** 2 + dz_ew ** 2)))

    terrain_df = pd.DataFrame({"lat": lats, "lon": lons, "elevation": center, "slope": slope_deg})
    terrain_df.to_csv(out_path, index=False)
    print(f"Saved {out_path}")
    return terrain_df


def fetch_terrain_openmeteo(
    points: pd.DataFrame,
    out_path: str,
    offset_deg: float = 0.01,
    batch_size: int = 50,
) -> pd.DataFrame:
    """
    Same idea as `fetch_terrain_from_api` but backed by Open-Meteo's
    elevation endpoint (https://api.open-meteo.com/v1/elevation), which
    is more reliably available than the public Open-Elevation instance
    and needs no API key.
    """
    api_url = "https://api.open-meteo.com/v1/elevation"
    lats = points["lat"].to_numpy()
    lons = points["lon"].to_numpy()
    n = len(points)

    all_lats, all_lons = [], []
    for lat, lon in zip(lats, lons):
        all_lats += [lat, lat + offset_deg, lat - offset_deg, lat, lat]
        all_lons += [lon, lon, lon, lon + offset_deg, lon - offset_deg]

    elevations = []
    for i in range(0, len(all_lats), batch_size):
        lat_chunk = all_lats[i:i + batch_size]
        lon_chunk = all_lons[i:i + batch_size]
        last_exc = None
        for attempt in range(2):
            try:
                resp = requests.get(
                    api_url,
                    params={
                        "latitude": ",".join(f"{v:.5f}" for v in lat_chunk),
                        "longitude": ",".join(f"{v:.5f}" for v in lon_chunk),
                    },
                    timeout=8,
                )
                resp.raise_for_status()
                elevations.extend(resp.json()["elevation"])
                break
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(1.0)
        else:
            raise RuntimeError(f"Open-Meteo elevation API failed after retries: {last_exc}")
        if i + batch_size < len(all_lats):
            time.sleep(0.5)

    elevations = np.array(elevations, dtype=float).reshape(n, 5)
    center, north, south, east, west = (elevations[:, j] for j in range(5))

    meters_per_deg_lat = 111_320
    meters_per_deg_lon = meters_per_deg_lat * np.cos(np.radians(lats))
    dz_ns = (north - south) / (2 * offset_deg * meters_per_deg_lat)
    dz_ew = (east - west) / (2 * offset_deg * meters_per_deg_lon)
    slope_deg = np.degrees(np.arctan(np.sqrt(dz_ns ** 2 + dz_ew ** 2)))

    terrain_df = pd.DataFrame({"lat": lats, "lon": lons, "elevation": center, "slope": slope_deg})
    terrain_df.to_csv(out_path, index=False)
    print(f"Saved {out_path}")
    return terrain_df


def build_terrain_index_from_dem(dem_path: str, points: pd.DataFrame, out_path: str) -> pd.DataFrame:
    """
    Sample elevation from a DEM GeoTIFF at the given lat/lon points and
    compute local slope (degrees) from the DEM gradient, then save a
    lat, lon, elevation, slope CSV for use with `load_terrain_index`.

    `points` must have lat/lon columns (e.g. the distinct station/grid
    coordinates from your ERA5 data). Requires rasterio.
    """
    import rasterio
    from rasterio.transform import rowcol

    with rasterio.open(dem_path) as src:
        band = src.read(1).astype(float)
        transform = src.transform
        px_size_x = transform.a
        px_size_y = -transform.e

        dzdx, dzdy = np.gradient(band, px_size_x, px_size_y)
        slope_deg = np.degrees(np.arctan(np.sqrt(dzdx ** 2 + dzdy ** 2)))

        rows = []
        for _, pt in points.iterrows():
            row, col = rowcol(transform, pt["lon"], pt["lat"])
            if 0 <= row < band.shape[0] and 0 <= col < band.shape[1]:
                rows.append(
                    {
                        "lat": pt["lat"],
                        "lon": pt["lon"],
                        "elevation": float(band[row, col]),
                        "slope": float(slope_deg[row, col]),
                    }
                )

    terrain_df = pd.DataFrame(rows)
    terrain_df.to_csv(out_path, index=False)
    print(f"Saved {out_path}")
    return terrain_df

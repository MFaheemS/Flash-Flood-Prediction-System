"""
Download ERA5 hourly reanalysis data for Pakistan from the Copernicus
Climate Data Store (CDS).

Requires a free CDS API key: register at
https://cds.climate.copernicus.eu, then create a file at
~/.cdsapirc with:

    url: https://cds.climate.copernicus.eu/api
    key: <your-uid>:<your-api-key>
"""
import os
import cdsapi

from src.data.load_data import load_config

VARIABLES = [
    "total_precipitation",
    "2m_temperature",
    "2m_dewpoint_temperature",
    "surface_pressure",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "total_cloud_cover",
    "convective_available_potential_energy",
]


def fetch_era5(year: str, month: str, config: dict):
    region = config["region"]
    out_dir = config["data"]["era5_dir"]
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"era5_{region['name']}_{year}_{month}.nc")

    client = cdsapi.Client()
    client.retrieve(
        "reanalysis-era5-single-levels",
        {
            "product_type": "reanalysis",
            "format": "netcdf",
            "variable": VARIABLES,
            "year": year,
            "month": month,
            "day": [f"{d:02d}" for d in range(1, 32)],
            "time": [f"{h:02d}:00" for h in range(24)],
            "area": [region["lat_max"], region["lon_min"], region["lat_min"], region["lon_max"]],
        },
        out_path,
    )
    print(f"Saved {out_path}")


if __name__ == "__main__":
    config = load_config()
    # Example: pull one monsoon month to start with
    fetch_era5(year="2022", month="07", config=config)

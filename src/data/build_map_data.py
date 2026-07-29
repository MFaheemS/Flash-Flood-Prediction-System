"""
Build the data file for the animated district map (frontend /explore page):
join the public-domain Pakistan district geometry (geoBoundaries) to our
district monthly satellite panel, and emit a single JSON with:

  - geojson       : simplified district polygons, each tagged with `d` (our
                    district key) + name/province
  - months        : list of "YYYY-MM" frame labels (2000-01 .. 2021-12)
  - factors       : per-district monthly series for the animated layers
                    (rain, peak rain, snow, vegetation, temperature, flood)
  - static        : per-district static layers (deforestation trend +
                    an urbanization gravity proxy computed from the polygon
                    centroid & town populations)
  - ranges        : [min, max] per factor for colour scaling

Output: Lovable frontend/public/pak_map.json

Run:
    python -m src.data.build_map_data
"""
import json
import os
import re

import numpy as np
import pandas as pd
from shapely.geometry import shape

from src.data.geo_reference import DISTRICT_TOWNS

GEOJSON_IN = "data/raw/pak_districts.geojson"
DATASET = "data/raw/district_flood_dataset.csv"
OUT = "Lovable frontend/public/pak_map.json"

# our GAUL district name -> geoBoundaries shapeName (spelling variants)
ALIASES = {
    "Batagram District": "Battagram",
    "Bolan District": "Kachhi",
    "D. I. Khan District": "Dera Ismail Khan",
    "Islamabad District": "Islamabad Capital Territory",
    "Jaffarabad District": "Jafarabad",
    "Killa Abdullah District": "Qilla Abdullah",
    "Killa Saifullah District": "Qilla Saifullah",
    "Malakand Protected Area": "Malakand",
    "Mirpur Khas District": "Mirpurkhas",
    "Sheikhupura District": "Sheikhpura",
    "Umer Kot District": "Umerkot",
    "T.A.Adj.Lakki Marwat District": "Lakki Marwat",
    "Karachi Central District": "Karachi",
    "Karachi East District": "Karachi",
    "Karachi South District": "Karachi",
    "Karachi West District": "Karachi",
    "Malir District": "Karachi",
}

FACTORS = {
    "rain": "precip_total",
    "peak_rain": "precip_max",
    "snow": "snow_mean",
    "veg": "veg_mean",
    "temp": "temp_mean",
    "flood": "flood",
}


def _norm(name: str) -> str:
    return re.sub(r"\s+(district|agency|distt|protected area).*$", "", name.strip().lower()).strip()


def _round_coords(geom, nd=3):
    """Round GeoJSON coordinates to nd decimals to shrink the file."""
    def r(x):
        if isinstance(x, (list, tuple)):
            if x and isinstance(x[0], (int, float)):
                return [round(float(x[0]), nd), round(float(x[1]), nd)]
            return [r(i) for i in x]
        return x
    return r(geom)


def build():
    gj = json.load(open(GEOJSON_IN, encoding="utf-8"))
    df = pd.read_csv(DATASET)

    months = [f"{y}-{m:02d}" for y in range(2000, 2022) for m in range(1, 13)]
    month_index = {ym: i for i, ym in enumerate(months)}
    df["ym"] = df["year"].astype(str) + "-" + df["month"].map(lambda m: f"{int(m):02d}")

    # our district -> geoBoundaries shapeName (via alias or normalized match)
    geo_by_norm = {_norm(f["properties"]["shapeName"]): f["properties"]["shapeName"] for f in gj["features"]}
    our_to_geo = {}
    for d in df["district"].unique():
        if d in ALIASES:
            our_to_geo[d] = ALIASES[d]
        elif _norm(d) in geo_by_norm:
            our_to_geo[d] = geo_by_norm[_norm(d)]

    # build monthly series per our-district
    series = {}
    static = {}
    for d, g in df.groupby("district"):
        if d not in our_to_geo:
            continue
        g = g.set_index("ym")
        s = {}
        for fk, col in FACTORS.items():
            arr = [None] * len(months)
            for ym, val in g[col].items():
                if ym in month_index and pd.notna(val):
                    arr[month_index[ym]] = round(float(val), 2)
            s[fk] = arr
        series[d] = s
        vt = g["veg_trend"].iloc[0]
        static[d] = {"deforestation": round(float(-vt) * 1000, 2) if pd.notna(vt) else None}

    # urbanization gravity proxy from polygon centroid + town populations
    town_lat = np.array([t["lat"] for t in DISTRICT_TOWNS.values()])
    town_lon = np.array([t["lon"] for t in DISTRICT_TOWNS.values()])
    town_pop = np.array([t["population"] for t in DISTRICT_TOWNS.values()], dtype=float)

    # assemble output features (one per geo polygon that maps to our data)
    geo_to_our = {}
    for d, gname in our_to_geo.items():
        geo_to_our.setdefault(gname, []).append(d)

    out_features = []
    for f in gj["features"]:
        gname = f["properties"]["shapeName"]
        ours = geo_to_our.get(gname)
        if not ours:
            continue
        primary = ours[0]  # Karachi sub-districts collapse to one polygon
        geom = shape(f["geometry"])
        c = geom.centroid
        dist = np.sqrt(((town_lat - c.y) * 111.32) ** 2 + ((town_lon - c.x) * 111.32 * np.cos(np.radians(c.y))) ** 2)
        urban = float(np.log1p(np.sum(town_pop / np.maximum(dist, 1.0) ** 2)))
        static[primary]["urbanization"] = round(urban, 2)

        out_features.append({
            "type": "Feature",
            "properties": {
                "d": primary,
                "name": gname,
                "province": df.loc[df["district"] == primary, "province"].iloc[0]
                if (df["district"] == primary).any() else None,
            },
            "geometry": {"type": f["geometry"]["type"], "coordinates": _round_coords(f["geometry"]["coordinates"])},
        })

    # per-factor colour ranges (2nd/98th pct so outliers don't wash out the scale)
    ranges = {}
    for fk in FACTORS:
        vals = [v for d in series for v in series[d][fk] if v is not None]
        if fk == "flood":
            ranges[fk] = [0, 1]
        elif vals:
            ranges[fk] = [round(float(np.percentile(vals, 2)), 2), round(float(np.percentile(vals, 98)), 2)]
    def_vals = [static[d]["deforestation"] for d in static if static[d].get("deforestation") is not None]
    urb_vals = [static[d].get("urbanization") for d in static if static[d].get("urbanization") is not None]
    ranges["deforestation"] = [round(min(def_vals), 2), round(max(def_vals), 2)]
    ranges["urbanization"] = [round(min(urb_vals), 2), round(max(urb_vals), 2)]

    out = {
        "months": months,
        "factors": series,
        "static": static,
        "ranges": ranges,
        "geojson": {"type": "FeatureCollection", "features": out_features},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    size_mb = os.path.getsize(OUT) / 1e6
    print(f"Saved {OUT} ({size_mb:.1f} MB) — {len(out_features)} districts, {len(months)} months")
    print(f"Matched {len(series)}/{df['district'].nunique()} of our districts to geometry")
    print("ranges:", ranges)


if __name__ == "__main__":
    build()

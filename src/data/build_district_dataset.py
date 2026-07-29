"""
Build a district-month flood panel from the Google Earth Engine monthly
exports in sf/ (PKm_*.csv: one value per district per month for all 119
Pakistan districts, 2000-2021).

LABELS come from the user's real, hand-curated province flood records
(Datasets/<Province>/Flood.csv -- monsoon-concentrated, correctly dated),
NOT from CLOUDPAK25 (whose dates are synthetic/uniform-across-months and
were poisoning earlier models). A real province flood-month is
disaggregated to districts by tagging the districts in that province whose
peak rainfall that month was anomalously high for that district (>= its own
historical 75th percentile) -- i.e. the districts that actually caught the
storm, not the whole province.

Output: data/raw/district_flood_dataset.csv

Run:
    python -m src.data.build_district_dataset
"""
import os

import numpy as np
import pandas as pd

SF_DIR = "sf"
DATASETS_DIR = "Datasets"
DISTRICT_PROVINCE_PATH = "sf/PK_district_province.csv"
OUT_PATH = "data/raw/district_flood_dataset.csv"

FILES = {
    "PKm_PreTotal.csv": "precip_total",
    "PKm_PreMax.csv": "precip_max",
    "PKm_Temp.csv": "temp_mean",
    "PKm_Ndsi.csv": "snow_mean",
    "PKm_Veg.csv": "veg_mean",
}

# Our province Flood.csv folder name -> GAUL ADM1_NAME(s). Gilgit-Baltistan
# is absent from GAUL 2015, so the Gilgit province labels can't be placed on
# any GAUL district and are dropped. KPK maps to both the old "North-West
# Frontier" name and the separately-coded tribal areas.
PROVINCE_TO_GAUL = {
    "Balochistan": ["Balochistan"],
    "Federal": ["Islamabad"],
    "Kpk": ["North-West Frontier", "Federally Administered Tribal Areas"],
    "Punjab": ["Punjab"],
    "Sindh": ["Sindh"],
    # "Gilgit": not representable in GAUL 2015
}

MONTH_PREFIX = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
RAIN_ANOMALY_PCTL = 0.85  # a district "caught the storm" if its monthly peak rain is in its own top ~15%


def load_features() -> pd.DataFrame:
    df = None
    for fname, col in FILES.items():
        d = pd.read_csv(os.path.join(SF_DIR, fname)).rename(columns={"value": col})[["ym", "district", col]]
        df = d if df is None else df.merge(d, on=["ym", "district"], how="outer")
    df["year"] = df["ym"].str.slice(0, 4).astype(int)
    df["month"] = df["ym"].str.slice(5, 7).astype(int)
    prov = pd.read_csv(DISTRICT_PROVINCE_PATH)
    df = df.merge(prov, on="district", how="left")
    return df


def real_province_floods() -> set:
    """Set of (gaul_adm1, year, month) from the curated province Flood.csv files."""
    floods = set()
    for folder, gaul_names in PROVINCE_TO_GAUL.items():
        path = os.path.join(DATASETS_DIR, folder, "Flood.csv")
        if not os.path.exists(path):
            continue
        f = pd.read_csv(path)
        f["m"] = f["Months"].astype(str).str.strip().str.lower().str[:3].map(MONTH_PREFIX)
        yes = f[f["Flood"].astype(str).str.strip().str.lower().eq("yes")]
        for _, r in yes.iterrows():
            for g in gaul_names:
                floods.add((g, int(r["Years"]), int(r["m"])))
    return floods


def build_dataset() -> pd.DataFrame:
    df = load_features()
    floods = real_province_floods()

    # per-district rainfall anomaly threshold (its own 75th pct peak-rain)
    thresh = df.groupby("district")["precip_max"].transform(lambda s: s.quantile(RAIN_ANOMALY_PCTL))

    province_flooded = [
        (p, y, m) in floods for p, y, m in zip(df["province"], df["year"], df["month"])
    ]
    df["flood"] = (np.array(province_flooded) & (df["precip_max"] >= thresh)).astype(int)

    df = df.sort_values(["district", "year", "month"]).reset_index(drop=True)
    df["precip_prev_month"] = df.groupby("district")["precip_total"].shift(1)

    # HUMAN-FACTOR feature: deforestation / urban expansion, measured as the
    # long-term trend in vegetation (NDVI) 2000-2021 per district. A negative
    # slope means the district lost vegetation over two decades (deforestation
    # or urban sprawl), which reduces infiltration and raises runoff/flood risk.
    def _veg_trend(g: pd.DataFrame) -> float:
        annual = g.groupby("year")["veg_mean"].mean().dropna()
        if len(annual) < 3:
            return np.nan
        return float(np.polyfit(annual.index.values, annual.values, 1)[0])

    trends = df.groupby("district", group_keys=False).apply(_veg_trend)
    df["veg_trend"] = df["district"].map(trends)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    pos = int(df["flood"].sum())
    print(f"Saved {len(df)} district-months ({pos} floods, {len(df)-pos} non-floods) to {OUT_PATH}")
    print(f"Districts: {df['district'].nunique()} | flood rate: {df['flood'].mean():.4f} "
          f"| flooded districts: {df.loc[df['flood']==1,'district'].nunique()}")
    print("Flood-months by calendar month (should be monsoon-heavy):")
    print(df[df['flood'] == 1]['month'].value_counts().sort_index().to_dict())
    return df


if __name__ == "__main__":
    build_dataset()

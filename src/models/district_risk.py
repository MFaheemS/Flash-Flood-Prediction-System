"""
Live flood-risk scoring driven by the DISTRICT SATELLITE MODEL (the
project's strongest, cleanest model: cross-validated AUC ~0.93, trained on
real curated flood labels -- see train_district_model.py), instead of the
thin event-based cloudburst model.

The district model is monthly, so we feed it:
  - precip_total / precip_max : from the LIVE Open-Meteo forecast, accumulated
    over each horizon window (24h / 3d / 7d / 16d). Shorter window => less
    accumulated rain => lower risk, which is the correct direction.
  - snow_mean / veg_mean / temp_mean / precip_prev_month : each district's REAL
    historical climatology for the current calendar month (from the GEE
    satellite panel), since snow cover and vegetation aren't in a weather
    forecast.
  - month : current month (captures monsoon seasonality, the model's #1 driver).

Districts in Gilgit-Baltistan aren't in the GAUL boundary set the satellite
panel uses, so they fall back to a forecast-rainfall-only heuristic.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import joblib
import numpy as np
import pandas as pd

from src.data.geo_reference import DISTRICT_TOWNS
from src.data.load_data import load_config
from src.models.risk_engine import _fetch_forecast_hourly

# Monitored town -> GAUL district name used by the satellite panel.
TOWN_TO_GAUL = {
    "Karachi": "Karachi South District",
    "Turbat": "Kech District",
    "Chaman": "Killa Abdullah District",
    "DG Khan": "Dera Ghazi Khan District",
}
# Gilgit-Baltistan towns absent from GAUL -> forecast-only fallback.
NO_CLIMATOLOGY = {"Skardu", "Gilgit", "Hunza", "Ghizer", "Ghanche"}

# horizon id -> forecast window length in hours
HORIZON_HOURS = {"hour": 24, "day": 72, "week": 168, "month": 384}

_climatology: dict | None = None
_model = None


def _load():
    global _climatology, _model
    if _model is not None:
        return
    config = load_config()
    dc = config["district_flood"]
    # prefer the calibrated model for live scoring (raw XGB reads high)
    cal_path = dc["model"]["save_path"].replace(".pkl", "_calibrated.pkl")
    import os
    _model = joblib.load(cal_path if os.path.exists(cal_path) else dc["model"]["save_path"])
    df = pd.read_csv(dc["raw_path"])
    # per (district, month) mean of the non-forecast features
    clim = df.groupby(["district", "month"]).agg(
        snow_mean=("snow_mean", "mean"),
        veg_mean=("veg_mean", "mean"),
        veg_trend=("veg_trend", "mean"),  # deforestation indicator (static per district)
        temp_mean=("temp_mean", "mean"),
        precip_prev_month=("precip_total", "mean"),
    )
    _climatology = clim.to_dict("index")


def _gaul_name(town: str) -> str | None:
    if town in NO_CLIMATOLOGY:
        return None
    if town in TOWN_TO_GAUL:
        return TOWN_TO_GAUL[town]
    return f"{town} District"


def _daily_precip(hourly: pd.DataFrame) -> pd.DataFrame:
    d = hourly[["time", "rainfall"]].copy()
    d["date"] = d["time"].dt.date
    return d.groupby("date")["rainfall"].sum().reset_index()


FEATURES = ["precip_total", "precip_max", "precip_prev_month", "temp_mean", "snow_mean", "veg_mean", "veg_trend", "month"]


def district_risk(town: str, lat: float, lon: float) -> dict:
    _load()
    month = pd.Timestamp.now("UTC").month
    gaul = _gaul_name(town)
    clim = _climatology.get((gaul, month)) if gaul else None

    hourly = _fetch_forecast_hourly(lat, lon)
    daily = _daily_precip(hourly)
    now = pd.Timestamp.now("UTC").tz_localize(None)

    risks = {}
    factors: dict = {}
    for hid, hours in HORIZON_HOURS.items():
        cutoff = now + pd.Timedelta(hours=hours)
        window = hourly[hourly["time"] < cutoff]
        wdaily = daily[pd.to_datetime(daily["date"]) < cutoff]
        precip_total = float(window["rainfall"].sum())
        precip_max = float(wdaily["rainfall"].max()) if len(wdaily) else 0.0

        if clim is not None:
            row = pd.DataFrame([{
                "precip_total": precip_total,
                "precip_max": precip_max,
                "precip_prev_month": clim["precip_prev_month"],
                "temp_mean": float(window["temperature"].mean()) if len(window) else clim["temp_mean"],
                "snow_mean": clim["snow_mean"],
                "veg_mean": clim["veg_mean"],
                "veg_trend": clim["veg_trend"],
                "month": month,
            }])
            risk = float(_model.predict_proba(row[FEATURES])[:, 1][0])
        else:
            # Gilgit-Baltistan fallback (no satellite climatology): a
            # deliberately conservative forecast-rainfall heuristic, scaled so
            # these UNVALIDATED scores don't spuriously outrank model-scored
            # districts. Transparent via the "model" field in the response.
            risk = float(1 - np.exp(-precip_max / 80.0))
        risks[f"{hid}_risk"] = risk
        if hid == "month":  # keep the full-window feature values for display
            factors = {
                "forecast_precip_total_mm": round(precip_total, 1),
                "forecast_precip_max_mm": round(precip_max, 1),
                "forecast_temp_mean_c": round(float(window["temperature"].mean()), 1) if len(window) else None,
            }

    peak_idx = daily["rainfall"].idxmax() if len(daily) else None
    return {
        "name": town,
        "lat": lat,
        "lon": lon,
        "province": DISTRICT_TOWNS.get(town, {}).get("province"),
        "hour_risk": risks["hour_risk"],
        "day_risk": risks["day_risk"],
        "week_risk": risks["week_risk"],
        "month_risk": risks["month_risk"],
        "peak_time": str(daily.loc[peak_idx, "date"]) if peak_idx is not None else None,
        "gaul_district": gaul,
        "model": "district_satellite" if clim is not None else "forecast_fallback",
        # what the district model actually uses: live forecast rain + this
        # district's historical climatology for the current month (None for
        # the Gilgit-Baltistan forecast-only fallback)
        "forecast_precip_total_mm": factors.get("forecast_precip_total_mm"),
        "forecast_precip_max_mm": factors.get("forecast_precip_max_mm"),
        "forecast_temp_mean_c": factors.get("forecast_temp_mean_c"),
        "snow_climatology": round(float(clim["snow_mean"]), 3) if clim is not None else None,
        "veg_climatology": round(float(clim["veg_mean"]), 3) if clim is not None else None,
        # deforestation / urban expansion: 20-yr NDVI trend (negative = losing vegetation)
        "veg_trend": round(float(clim["veg_trend"]) * 1000, 2) if clim is not None and clim["veg_trend"] == clim["veg_trend"] else None,
        "precip_prev_month_mm": round(float(clim["precip_prev_month"]), 1) if clim is not None else None,
        "month": int(month),
    }


def all_district_risk(horizon: str = "week") -> list[dict]:
    key = {"hour": "hour_risk", "day": "day_risk", "week": "week_risk", "month": "month_risk"}.get(horizon, "week_risk")
    results = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = {ex.submit(district_risk, name, t["lat"], t["lon"]): name for name, t in DISTRICT_TOWNS.items()}
        try:
            for fut in as_completed(futures, timeout=90):
                try:
                    results.append(fut.result(timeout=0))
                except Exception as exc:
                    print(f"Skipping {futures[fut]}: {exc}")
        except TimeoutError:
            print("Timed out waiting for some districts; showing partial results")
    results.sort(key=lambda r: r[key], reverse=True)
    return results


if __name__ == "__main__":
    for r in all_district_risk("week")[:12]:
        print(f"{r['name']:12s} week={r['week_risk']:.3f} month={r['month_risk']:.3f} [{r['model']}]")

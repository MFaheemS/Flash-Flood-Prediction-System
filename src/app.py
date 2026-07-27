"""
Flash Flood Risk API + dashboard.

Run:
    uvicorn src.app:app --reload --port 8000

Then open http://127.0.0.1:8000 for the built-in dashboard, or point a
separate frontend (e.g. a Lovable-built React app) at this API. CORS is
open (see below) so a browser frontend on any origin can call it.

Architecture note: risk for all monitored districts is computed in a
background thread on a timer, not inside the HTTP request path. Computing
it live (37 locations, each needing its own weather-forecast API call)
inside a request handler made page loads slow and, worse, occasionally
hang far longer than the same work takes standalone -- nesting a second
thread pool inside Starlette's request-handling worker turned out to be
an unreliable combination on this stack. Precomputing sidesteps it:
requests always return instantly from the last computed snapshot.
"""
import logging
import os
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from src.analysis.factor_impact import compute_factor_impact
from src.data.current_weather import get_current_weather
from src.data.geo_reference import DISTRICT_TOWNS
from src.data.load_data import load_config
from src.models.risk_engine import all_locations_risk, location_risk

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="Flash Flood Risk API")

# Open CORS: this API serves only public, non-sensitive model output and
# is meant to be called from a separately-hosted frontend. No auth, no
# user data, so a wildcard origin is appropriate here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
REFRESH_SECONDS = 10 * 60

_snapshot: dict = {"locations": [], "computed_at": None, "error": None}
_snapshot_lock = threading.Lock()

HORIZON_KEYS = {"hour": "hour_risk", "day": "day_risk", "week": "week_risk", "month": "month_risk"}
DATASETS = {"cloudburst", "flood_factors", "global_flood"}


# --------------------------------------------------------------------------- #
# Background district-risk refresh
# --------------------------------------------------------------------------- #
def _refresh_loop():
    while True:
        try:
            logger.info("Refreshing district risk snapshot...")
            t0 = time.time()
            locations = all_locations_risk("week")  # base sort; API re-sorts per horizon
            with _snapshot_lock:
                _snapshot["locations"] = locations
                _snapshot["computed_at"] = time.time()
                _snapshot["error"] = None
            logger.info(f"Snapshot refreshed: {len(locations)} districts in {time.time() - t0:.1f}s")
        except Exception as exc:
            logger.exception("Snapshot refresh failed")
            with _snapshot_lock:
                _snapshot["error"] = str(exc)
        time.sleep(REFRESH_SECONDS)


@app.on_event("startup")
def start_background_refresh():
    threading.Thread(target=_refresh_loop, daemon=True).start()


# --------------------------------------------------------------------------- #
# Pages (built-in dashboard; a Lovable frontend can ignore these)
# --------------------------------------------------------------------------- #
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/factors")
def factors_page():
    return FileResponse(os.path.join(STATIC_DIR, "factors.html"))


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@app.get("/api/meta")
def api_meta():
    """App metadata: available horizons, datasets, monitored district count,
    data sources, and when the risk snapshot was last computed. Drives an
    About/methodology page and lets a frontend enumerate options."""
    with _snapshot_lock:
        computed_at = _snapshot["computed_at"]
        district_count = len(_snapshot["locations"])
    return {
        "name": "Flash Flood Risk",
        "horizons": [
            {"id": "hour", "label": "Next hour"},
            {"id": "day", "label": "Next 24 hours"},
            {"id": "week", "label": "Next 7 days"},
            {"id": "month", "label": "Next 30 days"},
        ],
        "factor_datasets": [
            {"id": "cloudburst", "label": "Pakistan model (weather + terrain + soil)"},
            {"id": "global_flood", "label": "Global model (600 events, ~400 countries)"},
            {"id": "flood_factors", "label": "Human/infrastructure factors (Kaggle)"},
        ],
        "monitored_districts": district_count or len(DISTRICT_TOWNS),
        "risk_computed_at": computed_at,
        "data_sources": [
            "Open-Meteo (live + archive weather, elevation) — no key",
            "ISRIC SoilGrids (soil clay %)",
            "NASA POWER (antecedent soil moisture)",
            "HOTOSM (Pakistan waterways)",
            "Dartmouth Flood Observatory (historical events, global)",
            "CLOUDPAK25 (Pakistan cloudburst events 2010-2025)",
            "Kaggle Flood Prediction Dataset (infrastructure factors)",
        ],
        "notes": "Prototype. Trust the ranking between locations more than the absolute percentage.",
    }


@app.get("/api/districts")
def api_districts():
    """The static watchlist of monitored districts (name, coordinates,
    province, population) — useful for dropdowns and map markers."""
    return {
        "districts": [
            {"name": name, "lat": t["lat"], "lon": t["lon"],
             "province": t.get("province"), "population": t.get("population")}
            for name, t in DISTRICT_TOWNS.items()
        ]
    }


@app.get("/api/risk")
def api_risk(horizon: str = "week"):
    if horizon not in HORIZON_KEYS:
        raise HTTPException(400, "horizon must be one of: hour, day, week, month")

    with _snapshot_lock:
        locations = list(_snapshot["locations"])
        computed_at = _snapshot["computed_at"]
        error = _snapshot["error"]

    if not locations:
        if error:
            raise HTTPException(503, f"Risk data not available yet: {error}")
        raise HTTPException(503, "Risk data is still being computed for the first time — try again shortly.")

    locations.sort(key=lambda r: r[HORIZON_KEYS[horizon]], reverse=True)
    return {"horizon": horizon, "locations": locations, "computed_at": computed_at}


@app.get("/api/risk/point")
def api_risk_point(lat: float, lon: float, name: str = "custom"):
    """Risk for an arbitrary lat/lon (e.g. the user's current location or a
    dropped map pin), across all four horizons, with the underlying
    terrain/soil/drainage feature values."""
    config = load_config()
    try:
        return location_risk(name, lat, lon, config)
    except FileNotFoundError as exc:
        raise HTTPException(503, f"Model not trained yet: {exc}")


@app.get("/api/weather/current")
def api_weather_current(lat: float, lon: float):
    """Current weather at a point + a normalized `condition` category
    (clear/clouds/fog/rain/snow/storm) and `is_day` flag — drives a
    weather-reactive background video/animation on the frontend."""
    try:
        return get_current_weather(lat, lon)
    except Exception as exc:  # upstream API hiccup shouldn't 500 the whole app
        raise HTTPException(502, f"Weather upstream error: {exc}")


_factor_cache: dict = {}


@app.get("/api/factors")
def api_factors(dataset: str = "cloudburst"):
    """SHAP-based factor-impact ranking for a given trained model."""
    if dataset not in DATASETS:
        raise HTTPException(400, f"dataset must be one of: {', '.join(sorted(DATASETS))}")
    if dataset in _factor_cache:
        return _factor_cache[dataset]
    try:
        result, label = compute_factor_impact(dataset)
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc))
    payload = {"dataset": dataset, "label": label, "factors": result.to_dict(orient="records")}
    _factor_cache[dataset] = payload
    return payload

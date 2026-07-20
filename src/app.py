"""
Flash flood / cloudburst risk dashboard.

Run:
    uvicorn src.app:app --reload --port 8000

Then open http://127.0.0.1:8000

Risk for all monitored districts is computed in a background thread on a
timer, not inside the HTTP request path. Computing it live (37 locations,
each needing its own weather-forecast API call) inside a request handler
made page loads slow and, worse, occasionally hang far longer than the
same work takes standalone -- nesting a second thread pool inside
Starlette's own request-handling worker thread turned out to be an
unreliable combination on this stack. Precomputing sidesteps it entirely:
requests always return instantly from the last computed snapshot.
"""
import logging
import os
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from src.analysis.factor_impact import compute_factor_impact
from src.data.load_data import load_config
from src.models.risk_engine import all_locations_risk, location_risk

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="Pakistan Cloudburst / Flash Flood Risk Dashboard")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
REFRESH_SECONDS = 10 * 60

_snapshot: dict = {"locations": [], "computed_at": None, "error": None}
_snapshot_lock = threading.Lock()


def _refresh_loop():
    while True:
        try:
            logger.info("Refreshing district risk snapshot...")
            t0 = time.time()
            locations = all_locations_risk("week")  # base sort order; API re-sorts per horizon
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
    thread = threading.Thread(target=_refresh_loop, daemon=True)
    thread.start()


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/risk")
def api_risk(horizon: str = "week"):
    if horizon not in {"hour", "day", "week", "month"}:
        raise HTTPException(400, "horizon must be one of: hour, day, week, month")

    key_map = {"hour": "hour_risk", "day": "day_risk", "week": "week_risk", "month": "month_risk"}
    with _snapshot_lock:
        locations = list(_snapshot["locations"])
        computed_at = _snapshot["computed_at"]
        error = _snapshot["error"]

    if not locations:
        if error:
            raise HTTPException(503, f"Risk data not available yet: {error}")
        raise HTTPException(503, "Risk data is still being computed for the first time — try again shortly.")

    locations.sort(key=lambda r: r[key_map[horizon]], reverse=True)
    return {"horizon": horizon, "locations": locations, "computed_at": computed_at}


@app.get("/api/risk/point")
def api_risk_point(lat: float, lon: float, name: str = "custom"):
    config = load_config()
    try:
        return location_risk(name, lat, lon, config)
    except FileNotFoundError as exc:
        raise HTTPException(503, f"Model not trained yet: {exc}")


@app.get("/factors")
def factors_page():
    return FileResponse(os.path.join(STATIC_DIR, "factors.html"))


_factor_cache: dict = {}


@app.get("/api/factors")
def api_factors(dataset: str = "cloudburst"):
    if dataset not in {"cloudburst", "flood_factors"}:
        raise HTTPException(400, "dataset must be one of: cloudburst, flood_factors")
    if dataset in _factor_cache:
        return _factor_cache[dataset]
    try:
        result, label = compute_factor_impact(dataset)
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc))
    payload = {"dataset": dataset, "label": label, "factors": result.to_dict(orient="records")}
    _factor_cache[dataset] = payload
    return payload

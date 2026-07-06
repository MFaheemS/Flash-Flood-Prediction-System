"""
Flash flood / cloudburst risk dashboard.

Run:
    uvicorn src.app:app --reload --port 8000

Then open http://127.0.0.1:8000
"""
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from src.models.risk_engine import all_locations_risk, location_risk
from src.data.load_data import load_config

app = FastAPI(title="Pakistan Cloudburst / Flash Flood Risk Dashboard")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/risk")
def api_risk(horizon: str = "week"):
    if horizon not in {"hour", "day", "week", "month"}:
        raise HTTPException(400, "horizon must be one of: hour, day, week, month")
    try:
        return {"horizon": horizon, "locations": all_locations_risk(horizon)}
    except FileNotFoundError as exc:
        raise HTTPException(503, f"Model not trained yet: {exc}")


@app.get("/api/risk/point")
def api_risk_point(lat: float, lon: float, name: str = "custom"):
    config = load_config()
    try:
        return location_risk(name, lat, lon, config)
    except FileNotFoundError as exc:
        raise HTTPException(503, f"Model not trained yet: {exc}")

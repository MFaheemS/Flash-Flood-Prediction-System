# Cloudburst / Flash Flood Risk — Pakistan

A working dashboard that ranks Pakistani districts by flash-flood/cloudburst
risk over four horizons (next hour, next 24h, next 7 days, next 30 days),
using live/forecast weather, terrain, urbanization, and each district's
historical cloudburst track record.

## Run it

```
venv\Scripts\activate
uvicorn src.app:app --reload --port 8000
```

Open http://127.0.0.1:8000 — pick a horizon tab to see districts ranked by
risk, with the forecast time of peak risk, elevation, and historical
vulnerability score for each.

A model is already trained and committed to run this out of the box
(`models/cloudburst_model.pkl`); you don't need to run the pipeline below
unless you want to retrain it (e.g. after adding more historical events).

## How it works

**Data pipeline** (all free, key-less APIs — no account/registration needed):

1. `src/data/build_dataset_openmeteo.py` — builds the training table.
   Positive rows: the 150 real historical events in
   `CLOUDPAK25_2010_2025_v3.csv` (date/district/lat/lon/peak rainfall).
   Negative rows: 450 randomly sampled date+location combinations.
   Weather at each point/date comes from the
   [Open-Meteo Historical Weather (Archive) API](https://open-meteo.com/en/docs/historical-weather-api)
   — free, no key, backed by ERA5 reanalysis.
2. `src/data/enrich_dataset.py` — attaches:
   - **Terrain** (elevation + slope): Open-Meteo's elevation API, with
     slope estimated from 4 neighboring-point samples. Cloudbursts are
     strongly orographic (moist air forced up mountain slopes), so this
     is a high-value feature.
   - **Urbanization index**: no free equivalent to GHSL/WorldPop/VIIRS
     (those need a Google Earth Engine account), so this is a
     gravity-model proxy — population of ~35 known cities/towns
     (`src/data/geo_reference.py`) divided by squared distance, summed.
   - **Historical flood frequency**: distance-weighted count of past
     cloudburst events near that point, from the same events CSV — used
     as a proxy for **drainage/flood-resistance infrastructure**, since
     no open dataset of Pakistani municipal drainage systems exists. A
     place that has flooded from cloudbursts repeatedly is, empirically,
     a place whose drainage can't handle them.
   - **Drainage risk index**: a terrain+urbanization proxy (flatter +
     more built-up = slower natural runoff).
3. `src/models/train_model.py` — trains an XGBoost classifier
   (`models/cloudburst_model.pkl`).

**Live serving** (`src/models/risk_engine.py`, used by the dashboard):

- Fetches a 16-day hourly forecast per monitored district from Open-Meteo
  (the same weather variables used in training, computed identically).
- **Hour / day / week** risk = max predicted probability across that
  forecast window.
- **Month** risk = max(forecast-based signal for the 16 days that are
  actually forecastable, seasonal climatology for that district/month
  from historical events) — no weather model forecasts reliably past
  ~16 days, so the tail of the 30-day window falls back to "how often
  has this area flooded in this calendar month, historically."
- `src/models/predict.py:explain` attaches a SHAP-based explanation
  (top contributing features per prediction) for single-point lookups.

**Monitored locations**: 37 districts/cities across Pakistan
(`src/data/geo_reference.py:DISTRICT_TOWNS`), covering every district in
the historical events dataset plus a few major population centers.

## Project structure

```
CLOUDPAK25_2010_2025_v3.csv   150 real historical cloudburst events (source data)
config.yaml                    paths, feature list, hyperparameters
data/
  raw/                         built training table + terrain/urbanization caches
  processed/                   (unused currently)
src/
  data/                        fetching, geo reference data, dataset building
  features/                    preprocessing, historical/drainage proxies
  models/                      training, prediction, SHAP explanation, risk engine
  app.py                       FastAPI dashboard
static/index.html              dashboard frontend (vanilla JS, no build step)
models/cloudburst_model.pkl    trained model (committed so the app runs out of the box)
```

## Retraining / rebuilding data

```
python -m src.data.build_dataset_openmeteo   # ~15-20 min (600 sequential API calls)
python -m src.data.enrich_dataset            # ~1 min
python -m src.models.train_model
```

## Known limitations (be aware of these)

- **150 historical events** is a small training set. The model separates
  train/test almost perfectly, but that's substantially because
  `rainfall` (mm in the representative hour) is close to the label's own
  definition (an hour above a rainfall threshold = a cloudburst). Treat
  the other features (pressure drop, humidity, terrain, historical
  frequency) as the model's *real* predictive signal for hours where the
  actual future rainfall amount is still uncertain — which is exactly
  the situation a live forecast is in.
- **Urbanization and drainage-risk are proxies**, not real infrastructure
  data (see above). They're good enough for a working demo and to bias
  risk toward flood-prone flat/urban terrain, but not a substitute for
  actual WASA/municipal drainage-capacity records.
- Open-Meteo's forecast is only reliable ~16 days out; the "month"
  horizon beyond that is climatological, not a real forecast.

## What you need to do manually

1. **Nothing to get it running** — the trained model, terrain cache, and
   urbanization data are already built and committed; `uvicorn src.app:app`
   just works.
2. **If you want materially better accuracy**, the single highest-value
   thing you could add yourself is more/better historical event data —
   extend `CLOUDPAK25_2010_2025_v3.csv` with more verified past
   cloudburst/flash-flood events (more rows = less overfitting risk) or
   swap the urbanization/drainage proxies for real data if you can get
   an account for GHSL/WorldPop (Google Earth Engine) or a real
   municipal drainage-infrastructure dataset for your area of interest.
3. **If you want to deploy this publicly** (not just run locally), you'd
   need to host it yourself (e.g. a small VM or PaaS) — I haven't
   provisioned any hosting/domain, since that involves an account and
   possibly billing that only you can authorize.

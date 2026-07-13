# Pakistan Cloudburst / Flash Flood Risk — Architecture & Design

This document explains the project end to end: what it does, where every
piece of data comes from, how the model is trained, how live predictions
are served, and the specific decisions made around overfitting and class
imbalance. It assumes no prior context — everything referenced here is a
real file in this repository.

---

## 1. What the system does

A web dashboard that ranks Pakistan's flood-prone districts by cloudburst
/ flash-flood risk across four time horizons:

- **Next hour**
- **Next 24 hours**
- **Next 7 days**
- **Next 30 days**

For each district it shows a risk badge (LOW/MODERATE/HIGH), a
probability, the forecast time of peak risk, and supporting context
(elevation, historical flood frequency). It is a decision-support
prototype, not a certified early-warning system — see §9 for explicit
limitations.

---

## 2. High-level architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          OFFLINE (once)                          │
│                                                                     │
│  CLOUDPAK25_2010_2025_v3.csv  (150 real historical events)        │
│              │                                                     │
│              ▼                                                     │
│  build_dataset_openmeteo.py  ──►  data/raw/cloudburst_dataset.csv │
│              │                        (600 rows, 20 columns)      │
│              ▼                                                     │
│  enrich_dataset.py  (terrain, urbanization, history, waterways)   │
│              │                                                     │
│              ▼                                                     │
│  train_model.py  ──►  models/cloudburst_model.pkl  (XGBoost)      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                            LIVE (per request)                     │
│                                                                     │
│  Browser  ──►  FastAPI (src/app.py)  ──►  risk_engine.py           │
│                                              │                     │
│                    ┌─────────────────────────┼─────────────────┐  │
│                    ▼                         ▼                 ▼  │
│           Open-Meteo Forecast API   terrain/urbanization/   trained│
│           (16-day hourly weather)   waterways/history        model │
│                    │                         │                 │  │
│                    └───────────► feature row ◄─────────────────┘  │
│                                       │                             │
│                                       ▼                             │
│                          cloudburst_probability per hour             │
│                                       │                             │
│                          rolled up into hour/day/week/month risk    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Does it use a database?

**No.** Everything is flat files — CSV, GeoJSON, and a pickled model. No
Postgres/SQLite/etc. This is a deliberate simplicity choice: the dataset
is small (600 training rows, ~37 monitored districts), so a database
would add operational overhead without a real benefit at this scale.

| File | Format | Role |
|---|---|---|
| `CLOUDPAK25_2010_2025_v3.csv` | CSV | 150 real historical cloudburst events — the only ground-truth labels in the whole project |
| `data/raw/cloudburst_dataset.csv` | CSV | The 600-row engineered training table |
| `data/raw/hotosm_pak_waterways_lines_geojson.geojson` | GeoJSON | 34,876 real river/stream/canal/drain line geometries (OpenStreetMap, via HOTOSM) — manually downloaded, this is the one dataset not fetched by code |
| `data/raw/terrain_index.csv` | CSV | Cached elevation/slope per queried point (avoids re-hitting the elevation API) |
| `models/cloudburst_model.pkl` | joblib pickle | The trained XGBoost classifier |
| `config.yaml` | YAML | Single source of truth for file paths, the feature list, and model hyperparameters |
| `src/data/geo_reference.py` | Python dict | Hand-curated real coordinates + population for ~37 Pakistani districts/towns |

Live weather forecasts are fetched over HTTP at request time and kept
only in an **in-memory dictionary** (`risk_engine.py`'s `_cache`) for 30
minutes — never written to disk. Restarting the server clears it.

---

## 4. Where every input comes from

### 4.1 Historical events — `CLOUDPAK25_2010_2025_v3.csv`
150 real cloudburst/flash-flood events in Pakistan, 2010–2025. Columns:
`event_id, date, province, district, latitude, longitude,
peak_rainfall_mm_per_hr, duration_min, area_km2, deaths, injuries,
notes`. This is the **only real ground truth** the model learns from —
everything else is either derived from it or fetched to describe the
conditions around it.

### 4.2 Historical weather — Open-Meteo Archive API
`https://archive-api.open-meteo.com/v1/archive` — free, no API key, no
account. It's backed by ERA5 reanalysis data (the same underlying
science as the paid Copernicus CDS service this project originally
targeted, but exposed as a simple REST API with no registration). Used
to answer: "what was the weather at this exact lat/lon on this exact
historical date?"

### 4.3 Live/forecast weather — Open-Meteo Forecast API
`https://api.open-meteo.com/v1/forecast` — same provider, live/forecast
endpoint. Returns up to 16 days of hourly forecast per location. Used at
serving time for the dashboard.

### 4.4 Elevation — Open-Meteo Elevation API
`https://api.open-meteo.com/v1/elevation` — free, no key. Returns
elevation for a batch of lat/lon points. Slope is derived by also
sampling four points offset by ~0.01° north/south/east/west and computing
the elevation gradient (`src/data/terrain.py::fetch_terrain_openmeteo`).

### 4.5 Urbanization — hand-built gravity-model proxy
There is no free, key-less API for real built-up-area/population-density
data (GHSL, WorldPop, and VIIRS nightlights all require a Google Earth
Engine account or paid export). Instead, `src/data/geo_reference.py`
hardcodes real coordinates + approximate population for ~37 Pakistani
towns/districts, and `src/data/urbanization.py::build_urbanization_proxy`
computes, for any point:

```
urbanization_index = log1p( Σ over all known towns of population_i / distance_i² )
```

Points near a big city score high; remote rural points score low. This
is a physically reasonable stand-in (paved, dense cities drain stormwater
differently than farmland) but it is **not measured data** — see §9.

### 4.6 Drainage geometry — HOTOSM waterways (the one manual download)
`data/raw/hotosm_pak_waterways_lines_geojson.geojson` — 34,876 real
LineString features tagged `waterway=river|stream|canal|drain|...`,
downloaded from HumanitarianOSM's Pakistan export and placed in the repo
by hand. `src/data/waterways.py` builds a Shapely `STRtree` spatial index
over these once (cached for the process lifetime via `functools.lru_cache`)
and answers two questions for any point:
- `distance_to_waterway_km` — distance to the nearest mapped channel
- `waterway_count_10km` — how many separate channels exist within 10km

This replaced an earlier synthetic `drainage_risk_index` (a guess derived
from slope × urbanization) once real waterway geometry became available.

### 4.7 Historical vulnerability — derived from §4.1
`src/features/historical.py::historical_flood_freq` computes, for any
point, an inverse-distance-weighted sum of how many recorded events
happened near each known district, log-transformed. A point near Badin
(which has recorded multiple events) scores higher than a point near a
district with none.

---

## 5. Building the training dataset, step by step

### Step 1 — `src/data/build_dataset_openmeteo.py`
```
python -m src.data.build_dataset_openmeteo
```
- **Positive rows (150):** for each historical event, fetch that
  calendar day's hourly weather at the event's exact lat/lon from the
  Archive API. Pick the hour with the heaviest rainfall that day as the
  representative sample (the event record itself doesn't include a
  time-of-day, only a date). Compute `pressure_drop_3h` (pressure now
  minus pressure 3 hours earlier — a classic storm-approach signal) and
  `temp_dewpoint_spread`. Overwrite the fetched rainfall value with the
  event record's own `peak_rainfall_mm_per_hr` (trust the recorded
  ground truth over the reanalysis grid estimate). Label `cloudburst_occurred = 1`.
- **Negative rows (450, a fixed 3:1 ratio):** randomly sample
  (year, month, day, lat, lon) combinations within Pakistan's bounding
  box and the same 2010–2025 range, skipping any date that coincides
  with a real event. Fetch that day's weather the same way. If the
  sampled day's rainfall happens to exceed the cloudburst threshold
  anyway (30mm/hr, `config.yaml: data.precipitation_threshold_mm_per_hr`),
  discard and resample — a negative example shouldn't accidentally look
  like a positive one.
- Rows with missing weather data (a small fraction of archive queries)
  are dropped.
- Result: `data/raw/cloudburst_dataset.csv`, 600 rows.

### Step 2 — `src/data/enrich_dataset.py`
```
python -m src.data.enrich_dataset
```
For every unique (lat, lon) pair in the dataset:
1. Fetch/cache elevation + slope (§4.4) → `elevation`, `slope`
2. Compute the urbanization proxy (§4.5) → `urbanization_index`
3. Compute historical flood frequency (§4.7) → `historical_flood_freq`
4. Compute waterway distance/density (§4.6) → `distance_to_waterway_km`, `waterway_count_10km`

Writes back into the same `data/raw/cloudburst_dataset.csv`, now 20
columns wide.

### Step 3 — `src/models/train_model.py`
```
python -m src.models.train_model
```
- Loads config, loads the enriched CSV
- `clean_data`: drops NaNs and duplicate rows
- `split_features_target`: selects the 14 configured numeric features (§6) and the label
- 80/20 train/test split, **stratified by label** (`train_test_split_data`, `stratify=y`) — ensures both splits keep the same ~25% positive rate
- Fits `XGBClassifier(**config["model"]["params"])`
- Prints a classification report + ROC-AUC on the held-out test set
- Saves the fitted model to `models/cloudburst_model.pkl` via `joblib.dump`

---

## 6. The feature set (final, `config.yaml: features.numeric`)

| Feature | Category | Source |
|---|---|---|
| `temperature` | Atmosphere | Weather API |
| `humidity` | Atmosphere | Weather API |
| `dew_point` | Atmosphere | Weather API |
| `temp_dewpoint_spread` | Atmosphere (derived) | `temperature - dew_point`; small spread = air near saturation |
| `pressure` | Atmosphere | Weather API |
| `pressure_drop_3h` | Atmosphere (derived) | Pressure now minus pressure 3h ago — storm-approach signal |
| `cloud_cover` | Atmosphere | Weather API |
| `wind_speed` | Atmosphere | Weather API |
| `elevation` | Terrain | Elevation API |
| `slope` | Terrain | Elevation API, gradient over 4 offset points |
| `distance_to_waterway_km` | Drainage | HOTOSM waterways, nearest-neighbor |
| `waterway_count_10km` | Drainage | HOTOSM waterways, density within 10km |
| `urbanization_index` | Human context | Gravity-model proxy over known towns |
| `historical_flood_freq` | Human context | Inverse-distance-weighted historical event count |

**Deliberately excluded:** `rainfall`, even though it exists as a column
in the dataset. See §7.1 — including it causes label leakage.

---

## 7. Overfitting: what went wrong and how it was diagnosed and fixed

Two distinct overfitting problems surfaced during development. Both were
caught not by the headline metric (which looked *great* in both broken
states) but by inspecting **feature importances** and **live prediction
spread across districts** — a model that's actually learning general
patterns should use more than one feature, and should output different
risk levels for genuinely different places.

### 7.1 Label leakage via the `rainfall` feature

The cloudburst label itself is *defined* as "an hour where rainfall
exceeded 30mm/hr" (`config.yaml: data.precipitation_threshold_mm_per_hr`).
When `rainfall` was included as a model input, `model.feature_importances_`
showed:

```
rainfall                  1.0000
temperature               0.0000
humidity                  0.0000
... (every other feature) 0.0000
```

The model wasn't learning meteorology — it was just checking the answer
key. Train/test separation looked perfect, which was the tell that
something was wrong, not a sign of quality. In production this is
useless: a live forecast cannot reliably predict an *exact future rainfall
amount* for a specific hour, which is the very quantity being predicted.

**Fix:** removed `rainfall` from `config.yaml: features.numeric` entirely.
The column still exists in the dataset (used only to build the label
during dataset construction) but is never fed to the model.

### 7.2 Excess model capacity + a wrong imbalance weight

After removing `rainfall`, an early retrain used:
```yaml
n_estimators: 300
max_depth: 6
scale_pos_weight: 10   # arbitrary guess, not the real class ratio
```
This produced a second, subtler overfitting problem: live dashboard
predictions came back **nearly identical (~0.9+) for almost every
district**, regardless of real differences in current forecast
conditions or terrain. A 600-row dataset with 14 features and depth-6
trees has enough capacity to memorize noise in the training set rather
than generalize, and `scale_pos_weight=10` (versus the actual 3:1 class
ratio) over-corrected, biasing the model toward predicting "positive"
almost everywhere.

**Fix — reduced model capacity and corrected the imbalance weight:**

| Parameter | Before | After | Reasoning |
|---|---|---|---|
| `n_estimators` | 300 | 150 | Fewer trees = less opportunity to fit noise |
| `max_depth` | 6 | 3 | Shallower trees = simpler decision boundaries, standard first lever against overfitting on small tabular data |
| `scale_pos_weight` | 10 | 3 | Matches the *actual* 450:150 negative:positive ratio in the training set, instead of an arbitrary stronger correction |
| `subsample` | (unset, =1.0) | 0.8 | Each tree trained on a random 80% of rows — classic bagging-style regularization |
| `colsample_bytree` | (unset, =1.0) | 0.8 | Each tree trained on a random 80% of columns — decorrelates trees, reduces variance |
| `reg_lambda` | (unset, =1.0 default) | 2.0 | Stronger L2 penalty on leaf weights, shrinks extreme predictions |

**Result:** ROC-AUC on held-out test data went from a fake 1.0 (with
`rainfall` included) to a real, modest **~0.65**. That's the honest
signal available from 150 historical events. Live predictions now
genuinely differentiate: low-lying, waterway-adjacent Sindh/Punjab
districts (Badin, Larkana, Sargodha) consistently rank higher than
high-altitude Gilgit-Baltistan towns (Skardu, Hunza, Ghanche) — which
matches real-world flood geography, and is the kind of qualitative sanity
check that matters more than the raw AUC number at this data scale.

---

## 8. Class imbalance handling

Real cloudbursts are rare events, so any historical dataset built from
them will be imbalanced by nature. This project handles it in two
layers:

1. **Controlled negative sampling ratio.** `build_dataset_openmeteo.py`'s
   `build_dataset(negative_ratio=3)` generates exactly 3 negative samples
   per positive event — not "whatever happens to be available," but a
   deliberately chosen, moderate imbalance (450:150) that's severe enough
   to reflect reality but not so extreme that the model has almost
   nothing positive to learn from.
2. **`scale_pos_weight` matched to the real ratio.** XGBoost's built-in
   class-weighting parameter is set to `3`, i.e. exactly the negative:positive
   ratio in the training data — not tuned arbitrarily. This tells the
   loss function to weight a missed positive example 3× as costly as a
   missed negative one during training, compensating for positives being
   3× rarer, without over-correcting (see §7.2 for what happens when this
   is set too high).
3. **Stratified train/test split** (`train_test_split_data`,
   `stratify=y`) ensures the 80/20 split preserves the same ~25% positive
   rate in both halves, so the reported test metrics aren't distorted by
   an accidentally easier or harder test set.

---

## 9. Serving live predictions — `src/models/risk_engine.py`

For a given (lat, lon):

1. **`_fetch_forecast_hourly`** — calls the Forecast API for 16 days of
   hourly weather (384 rows), computes `pressure_drop_3h` and
   `temp_dewpoint_spread` the same way as training.
2. **`_attach_static_features`** — attaches elevation/slope, urbanization
   index, historical flood frequency, and waterway distance/count. These
   are constant for a given location, so they're computed **once** and
   broadcast across all 384 hourly rows (see the perf note in §10 — this
   used to be a real bug).
3. **`predict()`** (`src/models/predict.py`) — loads the trained model,
   runs it on all 384 rows, attaches `cloudburst_probability` per hour.
4. **`location_risk`** rolls the 384 hourly probabilities up into:
   - `hour_risk` = the very next forecast hour's probability
   - `day_risk` = max probability over the next 24 hours
   - `week_risk` = max probability over the next 7 days
   - `month_risk` = `max(forecast-based max over all 16 days, monthly_climatology_score)`
     — since no weather forecast is trustworthy 30 days out, the tail of
     the month falls back to "how often does this specific area flood in
     this specific calendar month, historically" (`historical.py::monthly_climatology_score`),
     so a monsoon-belt district in July still shows meaningful risk even
     past the 16-day forecast horizon, while December shows near-zero.
5. **`all_locations_risk`** runs the above for all ~37 known
   districts/towns **concurrently** (`ThreadPoolExecutor(max_workers=12)`,
   since each is an independent network-bound call), sorts by whichever
   horizon the dashboard is currently viewing, and returns the ranked
   list. Results per-location are cached in-memory for 30 minutes
   (`_cache` in `risk_engine.py`), so repeated tab switches or refreshes
   within that window are near-instant.

`src/app.py` (FastAPI) exposes this as `GET /api/risk?horizon=hour|day|week|month`
and `GET /api/risk/point?lat=&lon=` for an arbitrary custom coordinate,
plus serves `static/index.html` (a single dependency-free HTML/JS page
that fetches from the API and renders a sortable table) at `/`.

---

## 10. Performance note (a real bug that was found and fixed)

Early versions of `_attach_static_features` called the *dataset-oriented*
helper functions (`attach_historical_flood_freq`, `attach_waterway_features`)
which are written to loop row-by-row over a dataframe — correct for
training data where every row genuinely has a different lat/lon, but
wrong for a single location's forecast, where all 384 hourly rows share
the *same* lat/lon. This meant the (relatively expensive) waterway
nearest-neighbor search and historical-frequency lookup were being
recomputed 384 times per location instead of once, turning a single
dashboard load into a 3+ minute hang. Fixed by computing both once as
scalars and broadcasting them across the dataframe — cut per-location
time from ~12s to ~2-3s, and a full 37-district cold-cache dashboard load
from "effectively never finishes" to ~30-40 seconds (then near-instant
for 30 minutes via the cache).

---

## 11. Explainability — `src/models/predict.py::explain`

Separately from the dashboard's ranked list, `explain()` uses SHAP
(`TreeExplainer` on the trained XGBoost model) to attach a per-row
human-readable explanation, e.g.:

```
humidity=93 increased risk; pressure_drop_3h=4.2 increased risk; elevation=1600 decreased risk
```

This is not called on every dashboard load (it's more expensive than a
plain prediction) but is available for a detail view or CLI inspection
of any specific prediction.

---

## 12. Known limitations, stated plainly

- **150 historical events is a small label set** for 14 features. Treat
  the model's output as a *relative ranking* between districts, not a
  calibrated, trustworthy probability.
- **`urbanization_index` is a proxy**, not measured built-up-area or
  population-density data — no free API for the real thing exists for
  Pakistan without a Google Earth Engine account.
- **No real municipal drainage-infrastructure data exists publicly** for
  Pakistan (pump capacity, sewer condition, engineered flood defenses).
  The waterway distance/density features are real *geometry* but are a
  proxy for drainage *capacity*, not the capacity itself.
- **Absolute risk percentages run somewhat high** across the board,
  especially in monsoon months, due to the small/imbalanced training set
  — the ranking between districts is more reliable than the exact number.
- **Free public weather APIs occasionally return transient errors**
  (observed 503s from Open-Meteo under heavy testing); affected districts
  are silently skipped for that refresh cycle rather than crashing the
  whole dashboard, and typically succeed on the next refresh.

---

## 13. Running it yourself

```bash
# one-time setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# rebuild the training dataset from scratch (only needed if you want to
# regenerate data/raw/cloudburst_dataset.csv; a version is already committed)
python -m src.data.build_dataset_openmeteo
python -m src.data.enrich_dataset

# train
python -m src.models.train_model

# serve the dashboard
uvicorn src.app:app --reload --port 8000
# open http://127.0.0.1:8000
```

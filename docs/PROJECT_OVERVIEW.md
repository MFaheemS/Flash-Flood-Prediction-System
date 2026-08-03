# FloodWatch — Project Overview

A plain-language account of the whole system: what it does, how it works end
to end, the datasets and why they're good, how the models are trained, the
extra features, and what we found. No code or UI/design detail.

---

## 1. What it does

FloodWatch estimates and explains **flash-flood risk for every district in
Pakistan**. It has two jobs:

1. **Live risk** — for each monitored district it produces a calibrated risk
   score across four horizons (next 24 hours, 3 days, 7 days, 16 days), updated
   continuously from live weather forecasts.
2. **Explanation & analysis** — it shows *why* risk is what it is (which
   factors matter), lets you explore 20 years of Pakistan's climate month by
   month, and quantifies how flood risk has changed over time.

It is free to run, needs no login, and uses only public data sources.

---

## 2. How it works, end to end

The system is a pipeline of five stages.

**Stage 1 — Collect real observations.**
For 119 Pakistani districts we gather monthly satellite measurements from
2000–2021: rainfall, land-surface temperature, snow cover, and vegetation
greenness. Separately we collect real flood records (which places flooded, in
which months) and the country's river/canal network.

**Stage 2 — Turn observations into a labelled training table.**
Each district-month becomes a row of features (how much rain, how intense the
peak day, how much snow, how green, what season). We then attach the truth
label — did a flood occur there that month — from real flood records.

**Stage 3 — Train a model.**
A gradient-boosted machine-learning model learns the relationship between the
features and flooding. It's probability-calibrated so its outputs read like
real probabilities rather than inflated scores, and it's validated with
cross-validation so the reported accuracy is honest.

**Stage 4 — Score live risk.**
For a live forecast we can't use past satellite data, so instead we feed the
model the **16-day rainfall forecast** for each district (total and peak-day
rain, accumulated over each horizon) combined with that district's **historical
climate normals** for the current month (its typical snow, vegetation and
seasonality). The model returns a calibrated flood probability per horizon.

**Stage 5 — Serve and explain.**
The live scores drive a ranked dashboard and map. The trained model is also run
through an explainability method (SHAP) to show which factors drive risk, and
the 20-year satellite record powers an animated time-lapse map.

---

## 3. The datasets — and why they're good

Data quality is the heart of this project. We were deliberate about using
**real, observation-based sources** and rejecting fabricated ones.

### Satellite observations (the model's backbone)
- **CHIRPS rainfall** (daily, 0.05°): a rainfall product purpose-built and
  widely validated for data-sparse regions like South Asia, blending satellite
  and station data. *Why it's good:* it gives consistent, gap-free daily
  rainfall back to 1981 across the whole country — Pakistan's ground-station
  network is too sparse to do this alone.
- **MODIS** (NASA, daily/16-day): land-surface temperature, **snow cover
  (NDSI)**, and **vegetation (NDVI)**. *Why it's good:* two decades of
  consistent, physically-meaningful measurements at the same resolution every
  month — and it uniquely captures **snow-melt** and **vegetation change**,
  which are real flood drivers no weather feed provides.

All satellite data was aggregated per district per month via Google Earth
Engine (free), giving a clean 119-district × 264-month panel.

### Flood labels (the ground truth)
- **Curated province flood records (2000–2021):** which provinces flooded in
  which months, hand-verified. *Why it's good:* these are **real, correctly
  dated** events — 82%+ fall in the monsoon season, matching reality.
- **Dartmouth Flood Observatory (DFO):** an independent global archive of real
  flood events with dates and locations, used to corroborate and extend the
  record.

### Supporting layers
- **HumanitarianOSM waterways:** the real river/canal network (rivers, canals) —
  flash floods concentrate along these, so they add genuine spatial context.
- **geoBoundaries district shapes** (public domain) for mapping.
- **Open-Meteo forecasts** (free, no key) for the live 16-day rainfall used at
  serving time — backed by the same ERA5 science as paid services.

### Why we *rejected* a dataset (important)
A popular existing Pakistan cloudburst dataset ("CLOUDPAK25") was found to be
**synthetic**: its event dates were spread uniformly across all 12 months
(implausible January/February "cloudbursts"; only ~36% in monsoon vs the real
82%), and its coordinates were fabricated (e.g. Karachi placed hundreds of km
inland). It had been quietly degrading every model that used it. **We removed
it entirely** and rebuilt on verified data only. This is the single biggest
reason our results are trustworthy — the labels are real.

---

## 4. Model training

- **Target:** did a district flood in a given month (yes/no).
- **Features:** monthly rainfall total, peak-day rainfall, previous month's
  rain (antecedent wetness), temperature, snow cover, vegetation, season
  (month), and a human-factor deforestation signal (20-year vegetation trend).
- **Label construction:** real flood records are province-resolution, so a
  flooded province-month is **disaggregated to the districts that actually
  caught the storm** — those whose peak rainfall that month was in their own
  top ~15%. This turns coarse but real labels into district-level ones without
  inventing data.
- **Algorithm:** XGBoost gradient-boosted trees, with class weighting for the
  rarity of floods, plus subsampling and regularization to prevent overfitting.
- **Honest evaluation:** because floods are rare, we report **5-fold stratified
  cross-validated** ROC-AUC and PR-AUC rather than a single lucky split. The
  district model reaches **ROC-AUC ≈ 0.95**.
- **Calibration:** a separate calibrated model is used for the live dashboard,
  so predicted probabilities match real event frequencies (the raw model reads
  systematically high — calibration fixes the "everything looks high" problem).
- **Two model scopes:** a **district model** (119 districts, the flagship) and a
  coarser **province model** (ROC-AUC ≈ 0.83) used as a cross-check.

---

## 5. Extra features

- **Live risk dashboard & map** — every district ranked by risk across four
  horizons, refreshed continuously; drill into any district for its numbers and
  the factors behind them.
- **Searchable district list** — all districts with details, one click to a
  district's page.
- **Factor analysis (SHAP)** — for each model, a ranked chart of what drives
  risk and in which direction, so the model is transparent, not a black box.
- **Time-lapse "Explore" map** — an animated month-by-month choropleth of
  Pakistan, 2000–2021, for rainfall, snow, vegetation, temperature and floods,
  with the live river network overlaid; play/pause, speed control, province
  filter, and a side-by-side compare mode.
- **Human-factor modelling** — deforestation (measured from 20-year vegetation
  decline) is an explicit model feature; urbanization is included as a proxy.
- **Location check** — get risk for any point, including your current location.

---

## 6. Findings

1. **Rainfall and monsoon timing dominate.** The strongest drivers, in order,
   are the season (monsoon timing), total monthly rainfall, and peak-day
   rainfall intensity — the physically expected result for flash floods.
2. **Snow-melt and vegetation matter and are unique to satellite data.** Snow
   cover (a snow-melt proxy) and vegetation are meaningful secondary drivers
   that no purely weather-based model captures.
3. **Human land use has a real, measurable effect.** Deforestation — districts
   losing vegetation over 20 years — measurably **increases** flood risk (the
   correct physical direction: less vegetation → faster runoff). Karachi shows
   the steepest vegetation decline, consistent with dense urbanization.
4. **Flood risk has increased over 2000–2021.** Across every rainfall metric the
   trend is upward: total rainfall +~18%, **extreme-rain months +~20%**, and
   observed flood events +~14% (second decade vs first) — consistent with
   monsoon intensification. (Caveat: 22 years is a short window and event
   records are noisy.)
5. **Major floods are genuinely basin-wide; ordinary ones are local.** The 2010
   super-floods correctly light up almost the whole Indus basin, while typical
   months are focal — a distinction our tightened labelling now reflects.
6. **Data quality was decisive.** Once the synthetic CLOUDPAK25 data was
   removed and models were rebuilt on real curated records, cross-validated
   accuracy rose sharply (district model to ≈0.95) and the factor rankings
   became physically sensible — the clearest evidence that the real datasets
   are the right ones.

---

## 7. Honest limitations

- Flood labels are province-resolution disaggregated to districts, so
  individual-district labels are approximate.
- The pool of real, precisely-located flood events is small.
- 22 years is short for a definitive climate trend.
- Per-district soil moisture isn't available at monthly resolution (only
  region-level), so soil is not used in the district model.
- **This is a decision-support prototype, not an official warning** — trust the
  *ranking* between districts more than the exact percentage.

---

## 8. System configuration for deployment

The system runs as **two independent services** that talk over HTTPS: a Python
**backend** (the model + API) and a JavaScript **frontend** (the web app). This
separation is what lets each be hosted on the free tier best suited to it.

### Hardware / resource requirements
- **Backend:** modest — it runs comfortably on a **1 vCPU / 512 MB–1 GB RAM**
  container (the free tier of a container host). Peak memory is when the
  factor-analysis (SHAP) endpoint runs; everything else is light. No GPU is
  needed at any point — training and inference are CPU-only gradient-boosted
  trees.
- **Frontend:** none of its own — it's static assets + a small edge worker
  served from a CDN, so it scales for free.
- **Storage:** the backend image ships ~8 MB of model + data artifacts; the
  frontend ships ~30 MB (mostly the compressed background videos).

### Software / environment
- **Backend:** Python 3.11; key libraries `fastapi`, `uvicorn`, `xgboost`,
  `scikit-learn`, `shap`, `pandas`, `numpy`, `shapely`, `requests`, `pyyaml`.
  A slim `requirements-deploy.txt` is used for deployment (the full
  `requirements.txt` also contains training/notebook-only libraries such as
  TensorFlow and rasterio that the live service does **not** need and that would
  bloat the image).
- **Frontend:** Node 18+ with the app's own lockfile; builds to a Cloudflare
  Worker bundle.
- **External services at runtime:** only **Open-Meteo** (free, key-less) for
  live forecasts and current weather. No API keys or secrets are required
  anywhere, which is a deliberate design choice — nothing to leak, nothing to
  pay for.

### Infrastructure (what it's deployed on)
- **Backend →** a free container host. Because most now require a payment card
  even for $0 usage, the supported target is a **Hugging Face *Gradio* Space**
  (free, no card): a thin wrapper (`deploy/hf/app.py`) mounts the FastAPI app
  under one server so the whole API runs inside the Space. A `Dockerfile` and
  `render.yaml` are also provided for Docker hosts (Render/Koyeb/Fly) if a card
  is available.
- **Frontend →** **Cloudflare** (free, no card, unlimited bandwidth), served
  globally from the edge.
- **Keep-alive →** a GitHub Actions cron (`.github/workflows/keepalive.yml`)
  pings the backend so a sleeping free tier stays warm.

### Configuration changes needed before deployment
1. **Point the frontend at the backend:** set the build-time environment
   variable **`VITE_API_BASE_URL`** to the deployed backend's HTTPS URL. It is
   baked in at build time, so the frontend must be rebuilt if the URL changes.
2. **CORS:** already open on the backend (it serves only public, non-sensitive
   model output), so a browser frontend on any origin can call it — no change
   needed.
3. **HTTPS on both sides:** a browser served over HTTPS cannot call an
   `http://` backend, so the backend must be on its HTTPS host URL (all the free
   hosts provide this automatically).
4. **Port:** the backend honours a `$PORT`/`GRADIO_SERVER_PORT` env var and
   defaults to 7860 (the Hugging Face convention), so it runs on the target host
   without edits.
5. **Keep-alive (optional):** set a repository variable `BACKEND_URL` to enable
   the ping workflow.

Full click-by-click steps are in `docs/DEPLOY.md`.

---

## 9. Pipeline creation and design decisions

The project is built as a set of **small, single-purpose pipelines**, each a
step that can be run and checked independently. This modularity is what made it
possible to catch and fix data-quality problems mid-project rather than shipping
them silently.

### The pipelines
1. **Historical data assembly** — pull the satellite panel (rainfall,
   temperature, snow, vegetation) per district-month from Google Earth Engine,
   and assemble the real flood records.
2. **Label construction** — turn coarse but real province-level flood records
   into district-level labels by disaggregating each flooded province-month to
   the districts that actually caught the storm.
3. **Feature engineering** — derive the model inputs (rainfall total/intensity,
   antecedent wetness, seasonality, and the deforestation trend).
4. **Model training & evaluation** — train the gradient-boosted classifier with
   cross-validation and produce a probability-calibrated version for live use.
5. **Live scoring** — at request time, feed the 16-day forecast plus each
   district's climate normals into the model to produce calibrated risk.
6. **Explainability** — run SHAP over each trained model to rank the factors.
7. **Map/visualisation build** — package the geometry + monthly satellite series
   into a single compact file for the animated time-lapse.

### Why each major decision was made (correctness / reliability / effectiveness)
- **Two-model split (satellite panel for learning, forecast for serving).**
  A live system can't use past satellite imagery, and a forecast can't provide
  snow/vegetation history. Learning on the rich satellite record and then
  serving with *forecast rainfall + climate normals* keeps the model trained on
  real signal while still working in real time. This is what makes the live
  scores both grounded and current.
- **Probability calibration for the live model.** The raw model reads
  systematically high (the classic "everything looks risky" failure). A
  calibrated model brings predicted probabilities in line with real event
  frequencies, so the numbers are trustworthy and comparable — essential for a
  ranking tool.
- **Cross-validation, not a single split.** Floods are rare, so one train/test
  split is noisy and easy to over-read. Stratified 5-fold cross-validation gives
  an honest accuracy estimate (district model ≈ 0.95), which is the correct way
  to claim reliability on imbalanced data.
- **Disaggregating real labels instead of inventing data.** Rather than fabricate
  district flood dates, we spread *real* province flood-months to the
  highest-rainfall districts — using observed rainfall as the physical
  disaggregator. Tightening this threshold made the model sharper (0.93 → 0.95)
  and the flood map more focal, demonstrating the choice was sound.
- **Rejecting synthetic data (CLOUDPAK25).** The single most important design
  decision: after detecting that a popular dataset had fabricated dates and
  coordinates, we removed it entirely and rebuilt on verified records.
  Accuracy rose and factor rankings became physically sensible — direct evidence
  that the pipeline's correctness depends on data integrity, not just algorithms.
- **Precomputed, cached live snapshot.** Scoring all districts live inside each
  request was slow and occasionally unstable; a background thread computes the
  snapshot on a timer and requests serve instantly from it. This makes the API
  fast and predictable.
- **Free, key-less data sources only.** Every runtime dependency is free and
  needs no credentials, which makes the system cheap to run, easy to deploy, and
  free of secret-management risk.

---

## 10. Project details and final outputs

### Objective
Build a system that both **predicts** flash-flood risk for Pakistan's districts
and **explains** it — grounded in real, verifiable data and honest about its
limits.

### Final outputs
- A **live web app** (FloodWatch) with: a ranked district risk dashboard across
  four horizons; an interactive risk map and searchable district list; a
  transparent SHAP-based factor analysis; and an animated 2000–2021 time-lapse
  map of rainfall, snow, vegetation and floods with the river network overlaid.
- A **calibrated district model** (cross-validated accuracy ≈ 0.95) driving the
  live scores, plus a province-level cross-check model.
- A set of **findings** (Section 6): rainfall and monsoon timing dominate;
  snow-melt and vegetation matter; deforestation measurably raises risk; and
  flash-flood risk has increased ~14–20% over two decades.
- **Deployment-ready packaging**: containerised backend, edge-hosted frontend,
  and full deploy docs — all on free, card-free hosting.

### Deviations from the original plan
- **Data source pivot.** The project began around a Pakistan cloudburst dataset
  and a paid ERA5/CDS pipeline. Both were replaced: the cloudburst dataset was
  found to be synthetic and dropped, and ERA5 access was swapped for free,
  key-less APIs (Open-Meteo) and Google Earth Engine satellite exports.
- **Resolution pivot.** The plan implied event-level, point predictions; the
  reality of the available *real* labels pushed the design to a **monthly,
  district-level** model — a more honest match to the data actually on hand.
- **Live-model rethink.** The original live model leaned on the (synthetic)
  event data and read unrealistically high everywhere; it was replaced by the
  forecast-plus-climatology district model with calibration.

### Challenges encountered (and how they were handled)
- **Fabricated data (biggest challenge).** Detecting and removing the synthetic
  dataset — verified by its implausible month distribution and wrong coordinates
  — and rebuilding on real records.
- **Coarse ground truth.** Flood records exist at province, not district,
  resolution; solved with the rainfall-based disaggregation rather than inventing
  labels.
- **Access-gated data.** Several richer sources (nighttime lights, per-district
  soil moisture, some satellite products) required accounts/credentials; the
  design deliberately stuck to free, key-less sources and noted where a proxy was
  used instead.
- **Free-tier deployment friction.** Container hosts increasingly require a
  payment card; solved by wrapping the backend to run inside a free,
  no-card Hugging Face Gradio Space.
- **Over-broad flood visualisation.** Whole provinces lighting up as "flooded";
  addressed by tightening the label threshold so ordinary events show as focal
  hotspots while genuine basin-wide floods (2010) still show wide.

### Final result
A working, deployed-ready, fully free system that turns two decades of real
satellite and flood data into a live, explainable, honest flash-flood risk tool
for Pakistan — with the data-integrity decisions, not just the modelling, as the
foundation of its trustworthiness.

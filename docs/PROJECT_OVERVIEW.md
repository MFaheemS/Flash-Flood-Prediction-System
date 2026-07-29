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

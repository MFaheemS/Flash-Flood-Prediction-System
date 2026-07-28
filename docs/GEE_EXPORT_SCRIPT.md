# Fetching MODIS/GPM daily-district data (Google Earth Engine)

This is the one recommended source I **cannot fetch for you** — Google Earth
Engine requires your authenticated Google account (the same one you used to
export the `Datasets/` folder). Everything else (weather, elevation, soil
clay, soil moisture) I already fetch automatically via no-auth APIs.

Below is a ready-to-run script that produces the same kind of daily CSVs you
already have (`Pre.csv`, `Temp.csv`, `Ndsi.csv`, `Veg.csv`), but per **district**
instead of per province — so this satellite approach (currently the
best-performing model, AUC ≈ 0.83) can drive the live per-district dashboard.

## How to run

1. Go to https://code.earthengine.google.com (sign in with your GEE account).
2. Paste the script below into the editor.
3. Edit the `DISTRICT` and `YEAR_START`/`YEAR_END` at the top if you want.
4. Click **Run**, then open the **Tasks** tab and click **Run** on each export.
5. The CSVs land in your Google Drive under a `flood_gee` folder.
6. Drop them into a new `Datasets/<District>/` folder here and tell me — I'll
   wire them into the pipeline (same parser as your existing province data).

## The script (paste into the GEE Code Editor) — ALL districts, MONTHLY

Produces 5 CSVs (`PKm_PreTotal / PKm_PreMax / PKm_Temp / PKm_Ndsi / PKm_Veg`),
each a long table with columns `ym, district, value` (ym = "YYYY-MM") covering
every Pakistan district for every month 2000-2021.

Why monthly + reprojected: reducing raw MODIS *daily* images over 119 polygons
throws `Image.reduceRegions: Can't transform` (native-projection edge pixels).
Compositing to a monthly image and forcing an EPSG:4326 grid fixes it, and it's
~30x lighter (264 months vs ~8000 days), so it finishes quickly.

```javascript
var YEAR_START = 2000, YEAR_END = 2021;
var FOLDER = 'flood_gee';
var SCALE  = 1000;

var districts = ee.FeatureCollection('FAO/GAUL/2015/level2')
                  .filter(ee.Filter.eq('ADM0_NAME', 'Pakistan'));
print('district count:', districts.size());   // ~119

var nMonths = (YEAR_END - YEAR_START + 1) * 12;
var months = ee.List.sequence(0, nMonths - 1).map(function (k) {
  return ee.Date.fromYMD(YEAR_START, 1, 1).advance(k, 'month');
});

// monthlyImageFn(monthStart, monthEnd) -> one image for that month.
function reduceMonthly(monthlyImageFn, filename) {
  var feats = ee.FeatureCollection(months.map(function (m) {
    m = ee.Date(m);
    var img = ee.Image(monthlyImageFn(m, m.advance(1, 'month')))
                .reproject('EPSG:4326', null, SCALE);   // clean grid -> no transform error
    var ym = m.format('YYYY-MM');
    var stats = img.reduceRegions({
      collection: districts, reducer: ee.Reducer.mean(), scale: SCALE,
    });
    return stats.map(function (f) {
      return ee.Feature(null, { ym: ym, district: f.get('ADM2_NAME'), value: f.get('mean') });
    });
  })).flatten();

  Export.table.toDrive({
    collection: ee.FeatureCollection(feats).filter(ee.Filter.notNull(['value'])),
    description: 'PKm_' + filename, folder: FOLDER, fileFormat: 'CSV',
    selectors: ['ym', 'district', 'value'],
  });
}

// Precipitation: CHIRPS daily -> monthly total & monthly peak-day ----------
var chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY').select('precipitation');
reduceMonthly(function (a, b) { return chirps.filterDate(a, b).sum().rename('x'); }, 'PreTotal');
reduceMonthly(function (a, b) { return chirps.filterDate(a, b).max().rename('x'); }, 'PreMax');

// Temperature: MODIS LST day -> monthly mean (Celsius) ---------------------
var lst = ee.ImageCollection('MODIS/061/MOD11A1').select('LST_Day_1km');
reduceMonthly(function (a, b) {
  return lst.filterDate(a, b).mean().multiply(0.02).subtract(273.15).rename('x');
}, 'Temp');

// Snow cover: MODIS NDSI -> monthly mean (0-1) -----------------------------
var ndsi = ee.ImageCollection('MODIS/061/MOD10A1').select('NDSI_Snow_Cover');
reduceMonthly(function (a, b) {
  return ndsi.filterDate(a, b).mean().multiply(0.01).rename('x');
}, 'Ndsi');

// Vegetation: MODIS NDVI -> monthly mean (0-1) -----------------------------
var ndvi = ee.ImageCollection('MODIS/061/MOD13A2').select('NDVI');
reduceMonthly(function (a, b) {
  return ndvi.filterDate(a, b).mean().multiply(0.0001).rename('x');
}, 'Veg');

print('Cancel any old tasks, then Open Tasks and Run all 5 (PKm_*) exports.');
```

## Notes
- **Flood labels:** this script exports the *features*. For labels you still
  need a `Flood.csv` (month/year/flood) per district — the same format you
  already provided. If you have district-level flood dates, drop them in the
  same shape and I'll align them.
- **NDVI** already comes scaled ×10000 (values like 3743) — the parser here
  handles that, matching your existing `Veg.csv`.
- **Soil moisture** does NOT need GEE — I fetch ERA5-Land soil moisture
  automatically via Open-Meteo (`src/data/enrich_satellite_soilmoisture.py`).
- If you'd rather do all districts at once, replace the single-district filter
  with a loop over `adm2.aggregate_array('ADM2_NAME')` — ask me and I'll adapt
  the script.
```

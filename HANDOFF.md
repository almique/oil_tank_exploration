# Handoff: getting oil_tank_exploration to a working, free-data pipeline

_Status as of 2026-11-08. Pipeline runs end to end on Cushing NAIP 2010-2023; first backtest vs EIA utilization: r=0.88, mean abs error 0.055 (see "Results")._

## TL;DR

1. **The current backend cannot measure fill levels.** It runs shadow analysis on Sentinel-2 (10 m) /
   Landsat-HLS (30 m) imagery. A floating roof moves ~15 m from full to empty, which at 10 m is ~1.5 px.
   Fill needs sub-metre optical imagery or high-resolution SAR.
2. **The shadow code measures the wrong shadow** (see "Bugs" below), so even with good imagery it would
   return wrong numbers.
3. **A free (no-cost) path exists**, but it is not global:
   - Sub-metre free optical: **NAIP** (US only, 0.3–1 m, every ~2 years).
   - Sub-metre free radar: **Umbra Open Data** (40–55 collects each over Rotterdam, Antwerp, Jebel Ali,
     Singapore ports; CC BY 4.0).
   - Global free radar: **Sentinel-1** (every 6–12 days), accuracy for fill is **unproven**.
   - Free ground truth: **EIA weekly Cushing stocks** (no API key).
4. **Config:** `.env` files are untracked; copy `backend/.env.example` and `frontend/.env.example`
   to `.env` and fill in locally. Never commit `.env`.

## Will this cover every tank in the world?

No free source does.

| Need | Free and global? | Notes |
|---|---|---|
| Tank **locations** | Mostly | OSM is global but patchy. Tanks >= ~30 m can be detected on Sentinel-2 anywhere. Small tanks are missed. |
| Tank **fill level** | No | Free sub-metre only in the US (NAIP) and the handful of Umbra Open Data ports. Elsewhere only Sentinel-1, which is unvalidated. |

## Verified free data sources (all checked working in this session)

| Purpose | Source | Access | Checked result for Cushing |
|---|---|---|---|
| Ground truth | EIA `W_EPC0_SAX_YCUOK_MBBL` | `https://www.eia.gov/dnav/pet/hist_xls/W_EPC0_SAX_YCUOK_MBBLw.xls` (no key) | 1,180 weekly values, 2004-04-09 to 2026-10-30 |
| Tank locations | OSM Overpass `man_made=storage_tank` | anonymous | 404 tanks in bbox (35.90,-96.85,36.02,-96.68); median diameter 60 m |
| Tank locations (US, better) | Robinson et al. 2024, *Scientific Data*, 130k+ US tanks with diameters | figshare download | not yet downloaded |
| Tank locations (China) | Chen et al., ESSD 2024, 14,461 tanks | download | not yet downloaded |
| Sub-metre optical (US) | NAIP on Microsoft Planetary Computer STAC, collection `naip` | anonymous, signed URLs | 2010, 2013, 2015, 2017 (1.0 m); 2019, 2021 (0.6 m); **2023 (0.3 m)** |
| Sub-metre SAR (ports) | Umbra Open Data, `s3://umbra-open-data-catalog/sar-data/tasks/` | anonymous S3 | Rotterdam 54, Antwerp 53, Jebel Ali 52, Singapore 42, Houston 2 collects |
| Sub-metre SAR (misc) | Capella Open Data on AWS | anonymous S3 / STAC | coverage of tank farms not checked |
| Moderate SAR (global) | Sentinel-1 RTC on Planetary Computer, `sentinel-1-rtc` | anonymous | 87 scenes over Cushing 2023–2025, all relative orbit 34 ascending |
| Other weekly ground truth | Fujairah (FEDCom/Platts), ARA (Insights Global), Singapore (Enterprise Singapore) | public weekly releases | not wired up |

Visual check: NAIP 2019/2021/2023 chips at Cushing clearly show floating roofs with an inner shadow
crescent (sample render was produced locally; regenerate with the code below).

Unverified prior art worth knowing:
- A public GitHub PR (Talyvor/talyvor-lens #992) reports Sentinel-1 GRD at Cushing **failed** to beat
  a mean baseline vs EIA. Treat Sentinel-1 GRD/RTC as a long shot.
- The method that does work on SAR uses the floating-roof double-bounce position in range
  (DLR / IEEE JSTARS 2021, TerraSAR-X; patent US10672139). On free data that implies Sentinel-1 **SLC**
  (better range resolution), which is heavy to process, or Umbra Open Data where it exists.
- Kayrros says floating-roof tanks hold ~93% of Cushing capacity, so floating-roof-only measurement is
  a reasonable proxy there.

## Method (what `pipeline/shadow.py` implements)

Along the shadow direction:
- outer shadow length `L_out = H / tan(sun_elev)` (shell casts on the ground)
- inner shadow length `L_in = depth / tan(sun_elev)` (rim casts onto the floating roof)
- **`fill = 1 - L_in / L_out`**

Sun elevation and shell height cancel, so NAIP's missing acquisition time doesn't matter. Lengths are the
median over 11 chords parallel to the shadow direction. Shadow direction is a per-image consensus from
the dark mass just outside each tank.

Site-level estimate: weight each tank by `diameter^2 * L_out` (proportional to capacity in one image) and
compare the weighted fleet fill with EIA stocks for the image date.

## Results (2026-11-08)

Cushing, 7 NAIP years, floating-roof tanks only, capacity-weighted fleet fill vs EIA utilization
(weekly stocks / Cushing tank working capacity from EIA's discontinued storage capacity report):

| Image date | GSD | Fleet fill | EIA utilization |
|---|---|---|---|
| 2010-05-04 | 1.0 m | 0.86 | 0.76 (capacity extrapolated from 2011-03) |
| 2013-06-11 | 1.0 m | 0.83 | 0.74 |
| 2015-06-23 | 1.0 m | 0.79 | 0.78 |
| 2017-05-07 / 05-08 | 1.0 m | 0.75 / 0.86 | 0.86 |
| 2019-08-12 | 0.6 m | 0.57 | 0.58 |
| 2021-05-06 | 0.6 m | 0.50 | 0.60 |
| 2023-06-15 | 0.3 m | 0.51 | 0.54 |

r = +0.88, mean |error| = 0.055, constant-mean baseline 0.108. No calibration applied.
Compare with **utilization**, not raw barrels: Cushing capacity grew 58 to 98 M bbl over the period, so
raw stocks vs fill gives r = 0.39.

Known issues:
- 1 m years read ~+0.09 high in 2010/2013 (inner shadow harder to see; 2013 flown near noon, outer
  shadow only ~4.5 m).
- Shadow direction is estimated per tile from dark mass outside tanks; tiles of one flight disagree by ~12 deg.
- NAIP relief displacement makes some shell walls visible, which inflates `L_out`.

What changed in the method: the original roof-relative dark threshold (`frac=0.45`) flagged most grass
and soil as shadow and never caught the inner shadow (blue-grey, skylight-lit, brightness ~100-160 vs
roof ~225). `shadow.measure` now finds the strongest rising brightness edge after each rim on every chord.

## Code on this branch (`free-data-pipeline`)

| File | Purpose |
|---|---|
| `pipeline/tanks.py` | OSM fetch and diameter/circularity filter (402 Cushing tanks). |
| `pipeline/sites.py` | Site registry: bbox + EIA stocks series + capacity row (cushing, houston, corpus_christi). |
| `pipeline/ground_truth.py` | EIA weekly stocks, working capacity from the EIA storage report, utilization at a date. |
| `pipeline/shadow.py` | Edge-based fill-from-shadow measurement per tank chip. |
| `pipeline/naip.py` | NAIP STAC search, chip extraction per tank, per-tile measurement. |
| `pipeline/cache_chips.py` | `python -m pipeline.cache_chips --site cushing --year 2023` caches chips to `data/chips/<site>/<year>/` (~2-3 min/year; 2023 is 600 MB). |
| `pipeline/debug.py` | `python -m pipeline.debug data/chips/cushing/2023 --out data/debug/x.png`: overlays, stats, repeatability on overlapping tiles. |
| `pipeline/backtest.py` | `python -m pipeline.backtest --site cushing`: all years, floating classification, fleet fill vs EIA. Caches `data/backtest/<site>/per_tank_<year>.csv` and `roof_texture.csv`; delete those after changing `shadow.py`. |

`data/` is gitignored; everything in it can be regenerated.

Setup (macOS x86_64 note: Python 3.14 and newest rasterio don't have wheels; this worked):
```bash
python3.12 -m venv .venv-pipeline && . .venv-pipeline/bin/activate
pip install --only-binary=:all: "rasterio==1.3.11"
pip install pystac-client planetary-computer numpy pandas scipy shapely pyproj requests xlrd openpyxl matplotlib scikit-image
```

## Next steps, in order

1. ~~Security cleanup~~ done (2026-11-07).
2. ~~Validate the shadow method on Cushing NAIP 2023~~ done (edge-based rewrite, see Results).
3. ~~Classify floating vs fixed roof~~ done: floating if roof texture >= 8, or an inner shadow > 1.5 m in a
   sub-metre year and texture not < 4 (`backtest.classify_floating`). 335/402 at Cushing. Backtest r=0.89, MAE 0.053.
4. **Handle tanks that didn't exist yet** in older years: require a detected outer shadow
   (`ok == True`) before counting a tank.
5. ~~Backtest~~ first pass done (r=0.88 vs utilization over 7 dates). Rerun after steps 3-4.
6. **Port the same code to Houston/Corpus Christi** (also NAIP, also EIA PADD 3 data) for more points.
7. **Dense time series (free):** try Umbra Open Data at Rotterdam/Antwerp (double-bounce method) vs
   Insights Global ARA weekly stocks. Then decide whether Sentinel-1 SLC is worth the processing cost.
8. **Fix the existing backend** (or replace `vision_service.py` with `pipeline/shadow.py`):
   - `vision_service.py:407` `_detect_tank_shadow` masks out the tank and only finds the **outer**
     shadow. The outer shadow depends on shell height and sun, not fill.
   - `vision_service.py:457` uses distance to the shadow **centroid**, not shadow length.
   - `vision_service.py:638-641` upsamples imagery finer than 5 m but then **labels pixels as 5 m**
     (for 0.5 m input, sizes come out ~100x too large).
   - `vision_service.py:388` `fill = roof_height / wall_height` is built on the wrong shadow.
   - `satellite_service.py` searches Sentinel-2/Landsat/HLS/MODIS only; none can resolve fill.
   - `osm_service.py:_is_oil_tank` accepts any tank with no content tag (water tanks included).
9. **Wire into the app:** store per-tank fills in Postgres (`models.py` already has tanks and
   measurements), schedule NAIP/Umbra ingestion in Celery, show fleet fill vs EIA in the dashboard.

## Sources

- DLR / IEEE JSTARS 2021, SAR coherent scatterers on oil tanks: https://elib.dlr.de/142408/1/IEEE%20JSTARS%20-%20Oil%20storage.pdf
- Patent US10672139 (SAR floating roof volume): https://patents.google.com/patent/US10672139
- Robinson et al. 2024 US above-ground storage tanks: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10786938/
- Chen et al. ESSD 2024 China tanks: https://essd.copernicus.org/preprints/essd-2024-10/essd-2024-10-AC3-supplement.pdf
- Umbra Open Data: https://aws.amazon.com/marketplace/pp/prodview-ybjvekte4hg7o
- Capella Open Data: https://support.capellaspace.com/how-do-i-access-capellas-open-data
- NAIP on Planetary Computer: https://nbviewer.org/github/microsoft/PlanetaryComputerExamples/blob/main/datasets/naip/naip-example.ipynb
- Kayrros on Cushing floating roofs: https://www.kayrros.com/blog/drone-flights-over-cushing-bringing-transparency-on-crude-inventories-to-100/
- Talyvor Sentinel-1 Cushing attempt (unreviewed): https://github.com/Talyvor/talyvor-lens/pull/992
- Kaggle floating-head tank dataset (training data): https://datasetninja.com/oil-storage-tanks
- Airbus oil storage dataset (CC BY-NC-SA): https://datasetninja.com/airbus-oil-storage-detection
- Fujairah weekly inventory (FEDCom/Platts): https://www.indrastra.com/2019/09/Fujairah-Weekly-Oil-Inventory-Data-Stocks-Level-Sep-9-2019.html

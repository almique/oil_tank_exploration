"""Measure every tank in every free NAIP acquisition (US only, 0.3-1 m, ~every 2 yrs)."""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.warp import transform as warp_transform
from rasterio.windows import from_bounds
from shapely.geometry import Point, shape

from . import shadow

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MULTIRANGE="YES",
                GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES", VSI_CACHE="TRUE")


def naip_items(bbox, years=None):
    cat = pystac_client.Client.open(STAC, modifier=pc.sign_inplace)
    items = list(cat.search(collections=["naip"], bbox=bbox).items())
    if years:
        items = [i for i in items if i.datetime.year in years]
    return items


def _circmean(a: np.ndarray, w: np.ndarray | None = None) -> float:
    w = np.ones_like(a) if w is None else w
    return math.atan2((w * np.sin(a)).sum(), (w * np.cos(a)).sum())


def tanks_in_item(item, tanks: pd.DataFrame) -> pd.DataFrame:
    foot = shape(item.geometry)
    return tanks[[foot.contains(Point(lo, la)) for la, lo in zip(tanks.lat, tanks.lon)]]


def extract_chips(item, tanks: pd.DataFrame) -> tuple[float, list[tuple]]:
    """Return (gsd_m, [(tank_row, chip(3,h,w) uint8, cx_px, cy_px, r_px), ...])."""
    sel = tanks_in_item(item, tanks)
    if sel.empty:
        return float("nan"), []
    chips = []
    with rasterio.Env(**GDAL_ENV), rasterio.open(pc.sign(item.assets["image"].href)) as src:
        gsd = abs(src.transform.a)
        xs, ys = warp_transform("EPSG:4326", src.crs, list(sel.lon), list(sel.lat))
        for (_, t), x, y in zip(sel.iterrows(), xs, ys):
            half = 3.0 * t.diameter_m / 2 + 15
            win = from_bounds(x - half, y - half, x + half, y + half, src.transform)
            chip = src.read([1, 2, 3], window=win, boundless=True, fill_value=0)
            wt = src.window_transform(win)
            col, row = ~wt * (x, y)
            chips.append((t, chip, col, row, t.diameter_m / 2 / gsd))
    return gsd, chips


def _process_item(item, tanks: pd.DataFrame) -> list[dict]:
    gsd, chips = extract_chips(item, tanks)
    if not chips:
        return []
    out = []
    # pass 1: per-tank shadow direction, then one consensus direction per image tile
    dirs, weights = [], []
    for t, chip, cx, cy, r in chips:
        m = shadow.shadow_mask(chip, cx, cy, r)
        a, n = shadow.shadow_direction(m, cx, cy, r)
        if n > 0:
            dirs.append(a)
            weights.append(n)
    if not dirs:
        return []
    direction = _circmean(np.array(dirs), np.array(weights, float))
    for t, chip, cx, cy, r in chips:
        res = shadow.measure(chip, cx, cy, r, direction, gsd=gsd)
        out.append({
            "osm_id": t.osm_id, "item": item.id, "date": item.datetime.date().isoformat(),
            "year": item.datetime.year, "gsd_m": gsd, "diameter_m": t.diameter_m,
            "fill": res.fill, "l_in_m": res.l_in_px * gsd, "l_out_m": res.l_out_px * gsd,
            "n_chords": res.n_chords, "ok": res.ok, "reason": res.reason,
            "shadow_dir_deg": math.degrees(direction),
        })
    return out


def measure_site(tanks: pd.DataFrame, bbox, years=None, workers: int = 6) -> pd.DataFrame:
    items = naip_items(bbox, years)
    with ThreadPoolExecutor(workers) as ex:
        results = ex.map(lambda it: _process_item(it, tanks), items)
    rows = [r for rs in results for r in rs]
    return pd.DataFrame(rows)

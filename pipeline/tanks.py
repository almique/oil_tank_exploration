"""Tank inventory from OpenStreetMap (free, global, uneven coverage).

Each OSM `man_made=storage_tank` polygon becomes one row with centre,
diameter (from polygon area) and circularity. Works for any bbox, so the same
code serves Cushing, Rotterdam, Fujairah, etc.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import requests
from pyproj import Transformer
from shapely.geometry import Polygon

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "oil-tank-exploration/0.1 (open-data research)"


def fetch_osm_tanks(bbox: tuple[float, float, float, float], cache: Path | None = None) -> list[dict]:
    """bbox = (south, west, north, east)."""
    if cache and cache.exists():
        return json.loads(cache.read_text())["elements"]
    s, w, n, e = bbox
    q = f'[out:json][timeout:180];(way["man_made"="storage_tank"]({s},{w},{n},{e}););out geom;'
    r = requests.post(OVERPASS, data={"data": q}, headers={"User-Agent": UA}, timeout=240)
    r.raise_for_status()
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(r.text)
    return r.json()["elements"]


def _utm_epsg(lon: float, lat: float) -> int:
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def tanks_dataframe(elements: list[dict], min_diameter_m: float = 20.0,
                    min_circularity: float = 0.85) -> pd.DataFrame:
    rows = []
    for e in elements:
        g = e.get("geometry")
        if not g or len(g) < 4:
            continue
        lon0, lat0 = g[0]["lon"], g[0]["lat"]
        epsg = _utm_epsg(lon0, lat0)
        fwd = Transformer.from_crs(4326, epsg, always_xy=True)
        inv = Transformer.from_crs(epsg, 4326, always_xy=True)
        poly = Polygon([fwd.transform(p["lon"], p["lat"]) for p in g])
        if not poly.is_valid or poly.area <= 0:
            continue
        diameter = 2 * math.sqrt(poly.area / math.pi)
        circ = 4 * math.pi * poly.area / poly.length ** 2
        lon, lat = inv.transform(poly.centroid.x, poly.centroid.y)
        tags = e.get("tags", {})
        rows.append({
            "osm_id": e["id"], "lat": lat, "lon": lon, "diameter_m": diameter,
            "circularity": circ, "content": tags.get("content"),
            "operator": tags.get("operator"),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df[(df.diameter_m >= min_diameter_m) & (df.circularity >= min_circularity)].reset_index(drop=True)

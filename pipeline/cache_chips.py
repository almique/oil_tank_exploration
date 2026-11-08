"""Download NAIP chips for every tank once and cache them as .npz for offline tuning.

    python -m pipeline.cache_chips --year 2023
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from . import naip, tanks

CUSHING_BBOX = (35.90, -96.85, 36.02, -96.68)  # south, west, north, east


def cache_item(item, df, out_dir: Path) -> int:
    gsd, chips = naip.extract_chips(item, df)
    for t, chip, cx, cy, r in chips:
        np.savez_compressed(
            out_dir / f"{item.id}__{t.osm_id}.npz", chip=chip, cx=cx, cy=cy, r=r, gsd=gsd,
            osm_id=t.osm_id, diameter_m=t.diameter_m, item=item.id,
            date=item.datetime.date().isoformat())
    return len(chips)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--out", default="data/chips")
    args = ap.parse_args()
    s, w, n, e = CUSHING_BBOX
    df = tanks.tanks_dataframe(tanks.fetch_osm_tanks(CUSHING_BBOX, cache=Path("data/raw/osm_cushing.json")))
    out = Path(args.out) / str(args.year)
    out.mkdir(parents=True, exist_ok=True)
    items = naip.naip_items([w, s, e, n], {args.year})
    with ThreadPoolExecutor(6) as ex:
        for it, k in zip(items, ex.map(lambda it: cache_item(it, df, out), items)):
            print(f"{it.id}: {k} chips", flush=True)


if __name__ == "__main__":
    main()

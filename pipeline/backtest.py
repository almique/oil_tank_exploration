"""Backtest fleet fill from cached NAIP chips against EIA Cushing stocks.

    python -m pipeline.backtest data/chips --out data/backtest
"""
from __future__ import annotations

import argparse
import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from . import ground_truth, shadow
from .debug import load, tile_directions

FLOATING_MIN_LIN_M = 1.5


def _measure_one(args):
    c, direction = args
    res = shadow.measure(c["chip"], c["cx"], c["cy"], c["r"], direction, gsd=c["gsd"])
    return dict(osm_id=int(c["osm_id"]), item=c["item"], date=c["date"], gsd=c["gsd"],
                diameter_m=c["diameter_m"], fill=res.fill, l_in_m=res.l_in_px * c["gsd"],
                l_out_m=res.l_out_px * c["gsd"], ok=res.ok, reason=res.reason)


def measure_year(folder: Path, workers: int = 4) -> pd.DataFrame:
    chips = load(folder)
    if not chips:
        return pd.DataFrame()
    dirs = tile_directions(chips)
    jobs = [(c, dirs[c["item"]]) for c in chips if c["item"] in dirs]
    with ProcessPoolExecutor(workers) as ex:
        rows = list(ex.map(_measure_one, jobs, chunksize=8))
    df = pd.DataFrame(rows)
    df["year"] = int(folder.name)
    return df


def fleet(per_tank: pd.DataFrame, floating_ids: set[int]) -> pd.DataFrame:
    """One row per acquisition date: capacity-weighted fill of floating-roof tanks."""
    ok = per_tank[per_tank.ok & per_tank.osm_id.isin(floating_ids)]
    # one measurement per tank per date (overlapping tiles)
    ok = ok.sort_values("l_out_m").groupby(["date", "osm_id"]).median(numeric_only=True).reset_index()
    out = []
    for date, g in ok.groupby("date"):
        h_rel = g.l_out_m / g.l_out_m.median()          # shell height relative to the fleet, same image
        w = g.diameter_m ** 2 * h_rel
        out.append(dict(date=date, n_tanks=len(g), fill=float((g.fill * w).sum() / w.sum()),
                        volume_index=float((g.fill * g.diameter_m ** 2).sum()),
                        capacity_index=float((g.diameter_m ** 2).sum())))
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chips", help="folder with one subfolder per year")
    ap.add_argument("--out", default="data/backtest")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    frames = []
    for yd in sorted(p for p in Path(a.chips).iterdir() if p.is_dir() and p.name.isdigit()):
        cache = out / f"per_tank_{yd.name}.csv"
        if cache.exists():
            df = pd.read_csv(cache)
        else:
            df = measure_year(yd, a.workers)
            df.to_csv(cache, index=False)
        print(f"{yd.name}: {len(df)} chips, ok={int(df.ok.sum())}", flush=True)
        frames.append(df)
    per_tank = pd.concat(frames, ignore_index=True)
    lin = per_tank[per_tank.ok].groupby("osm_id").l_in_m.max()
    floating = set(lin[lin > FLOATING_MIN_LIN_M].index)
    print(f"floating-roof tanks: {len(floating)} of {per_tank.osm_id.nunique()}")
    f = fleet(per_tank, floating)
    eia = ground_truth.eia_weekly(cache=Path("data/raw/eia_cushing.xls"))
    f["eia_kbbl"] = [ground_truth.value_at(eia, d) for d in f.date]
    f.to_csv(out / "fleet_vs_eia.csv", index=False)
    print(f.round(3).to_string(index=False))
    if len(f) >= 3:
        for col in ["fill", "volume_index"]:
            r = np.corrcoef(f[col], f.eia_kbbl)[0, 1]
            k, b = np.polyfit(f[col], f.eia_kbbl, 1)
            rmse = math.sqrt(((k * f[col] + b - f.eia_kbbl) ** 2).mean())
            base = f.eia_kbbl.std(ddof=0)
            print(f"{col}: r={r:+.2f}  RMSE after linear fit={rmse:,.0f} kbbl  (mean-baseline {base:,.0f})")


if __name__ == "__main__":
    main()

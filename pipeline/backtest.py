"""Backtest fleet fill from cached NAIP chips against EIA Cushing stocks.

    python -m pipeline.backtest --site cushing
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
from .sites import SITES

FLOATING_MIN_LIN_M = 1.5      # inner shadow longer than this => roof sits below the rim
SMOOTH_TEX = 4.0              # roof texture below this => fixed (cone/dome) roof
TEXTURED = 8.0                # roof texture above this => floating roof even if never seen below rim
SUBMETRE = 0.75               # only trust inner-shadow evidence at GSD <= this
TEXTURE_MAX_GSD = 0.4         # texture thresholds were tuned at 0.3 m and do not transfer to 0.6 m


def roof_textures(chips_root: Path) -> pd.Series:
    """Roof texture per tank from the finest-resolution year available."""
    years = sorted((p for p in chips_root.iterdir() if p.is_dir() and p.name.isdigit()), key=lambda p: p.name)
    tex = {}
    for yd in reversed(years):
        for c in load(yd):
            if c["gsd"] > TEXTURE_MAX_GSD or int(c["osm_id"]) in tex:
                continue
            tex[int(c["osm_id"])] = shadow.roof_texture(c["chip"], c["cx"], c["cy"], c["r"], c["gsd"])
        if tex:
            break
    return pd.Series(tex, name="texture")


def classify_floating(per_tank: pd.DataFrame, texture: pd.Series) -> set[int]:
    hi = per_tank[per_tank.ok & (per_tank.gsd <= SUBMETRE)]
    lin = hi.groupby("osm_id").l_in_m.max()
    d = pd.concat([lin.rename("lin"), texture.reindex(lin.index.union(texture.index))], axis=1)
    shadow_seen = d.lin > FLOATING_MIN_LIN_M
    floating = (d.texture >= TEXTURED) | (shadow_seen & ~(d.texture < SMOOTH_TEX))
    return set(d.index[floating.fillna(False)])


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
    ap.add_argument("--site", default="cushing", choices=sorted(SITES))
    ap.add_argument("--chips", default="data/chips", help="root; chips are read from <root>/<site>/<year>")
    ap.add_argument("--out", default="data/backtest", help="root; results go to <root>/<site>")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    site = SITES[a.site]
    chips_root = Path(a.chips) / site.name
    out = Path(a.out) / site.name; out.mkdir(parents=True, exist_ok=True)
    frames = []
    for yd in sorted(p for p in chips_root.iterdir() if p.is_dir() and p.name.isdigit()):
        cache = out / f"per_tank_{yd.name}.csv"
        if cache.exists():
            df = pd.read_csv(cache)
        else:
            df = measure_year(yd, a.workers)
            df.to_csv(cache, index=False)
        print(f"{yd.name}: {len(df)} chips, ok={int(df.ok.sum())}", flush=True)
        frames.append(df)
    per_tank = pd.concat(frames, ignore_index=True)
    tex_cache = out / "roof_texture.csv"
    if tex_cache.exists():
        texture = pd.read_csv(tex_cache, index_col=0)["texture"]
    else:
        texture = roof_textures(chips_root)
        texture.to_csv(tex_cache)
    floating = classify_floating(per_tank, texture)
    print(f"floating-roof tanks: {len(floating)} of {per_tank.osm_id.nunique()}")
    f = fleet(per_tank, floating)
    eia = ground_truth.eia_weekly(site.eia_stocks, cache=Path(f"data/raw/eia_{site.eia_stocks}.xls"))
    f["eia_kbbl"] = [ground_truth.value_at(eia, d) for d in f.date]
    cap = ground_truth.working_capacity(site.capacity_sheet, site.capacity_row,
                                        cache=Path("data/raw/eia_crudeoilstorage.xlsx"))
    util = [ground_truth.utilization_at(eia, cap, d) for d in f.date]
    f["eia_util"] = [u for u, _ in util]
    f["cap_known"] = [k for _, k in util]
    f.to_csv(out / "fleet_vs_eia.csv", index=False)
    print(f.round(3).to_string(index=False))
    if len(f) >= 3:
        r = np.corrcoef(f.fill, f.eia_util)[0, 1]
        mae = (f.fill - f.eia_util).abs().mean()
        print(f"fill vs EIA utilization: r={r:+.2f}  mean |error|={mae:.3f}  "
              f"(constant-mean baseline {(f.eia_util - f.eia_util.mean()).abs().mean():.3f})")
        for col in ["fill", "volume_index"]:
            r = np.corrcoef(f[col], f.eia_kbbl)[0, 1]
            k, b = np.polyfit(f[col], f.eia_kbbl, 1)
            rmse = math.sqrt(((k * f[col] + b - f.eia_kbbl) ** 2).mean())
            base = f.eia_kbbl.std(ddof=0)
            print(f"{col}: r={r:+.2f}  RMSE after linear fit={rmse:,.0f} kbbl  (mean-baseline {base:,.0f})")


if __name__ == "__main__":
    main()

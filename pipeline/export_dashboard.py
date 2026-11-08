"""Export pipeline results to dashboard/data.js (static, opens from file://).

    python -m pipeline.export_dashboard

Reads data/backtest/<site>/per_tank_*.csv and roof_texture.csv (run pipeline.backtest first).
Measurements are pooled per NAIP year (one flight campaign), not per exact date, so partial-tile
dates do not produce noisy fleet points.
"""
from __future__ import annotations

import glob
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from . import ground_truth, tanks
from .backtest import classify_floating
from .sites import SITES

LABELS = {"cushing": "Cushing, OK", "houston": "Houston Ship Channel, TX", "corpus_christi": "Corpus Christi, TX"}
STATUS = {
    "cushing": ("validated", "Validated against EIA Cushing utilization"),
    "houston": ("inconclusive", "Inconclusive: EIA only publishes Gulf Coast-wide data"),
    "corpus_christi": ("inconclusive", "Inconclusive: EIA only publishes Gulf Coast-wide data"),
}


def _r(x, n=3):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), n)


def site_payload(name: str) -> dict:
    site = SITES[name]
    bt = Path("data/backtest") / name
    per = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(str(bt / "per_tank_*.csv")))], ignore_index=True)
    tex = pd.read_csv(bt / "roof_texture.csv", index_col=0)["texture"] if (bt / "roof_texture.csv").exists() \
        else pd.Series(dtype=float)
    floating = classify_floating(per, tex)
    inv = tanks.tanks_dataframe(tanks.fetch_osm_tanks(site.bbox, cache=Path(f"data/raw/osm_{name}.json")))
    observed = set(per[per.ok & (per.gsd <= 0.75)].osm_id)

    def roof(oid):
        if oid in floating:
            return "floating"
        return "fixed" if oid in observed else "unknown"

    tank_rows = [[int(t.osm_id), round(t.lat, 6), round(t.lon, 6), round(t.diameter_m, 1), roof(int(t.osm_id))]
                 for t in inv.itertuples()]

    ok = per[per.ok & per.osm_id.isin(floating)]
    per_year = ok.groupby(["year", "osm_id"]).agg(fill=("fill", "median"), l_out=("l_out_m", "median"),
                                                  d=("diameter_m", "first")).reset_index()
    eia = ground_truth.eia_weekly(site.eia_stocks, cache=Path(f"data/raw/eia_{site.eia_stocks}.xls"))
    cap = ground_truth.working_capacity(site.capacity_sheet, site.capacity_row,
                                        cache=Path("data/raw/eia_crudeoilstorage.xlsx"))
    years = []
    for y, g in per_year.groupby("year"):
        dates = pd.to_datetime(per[(per.year == y) & per.ok].date)
        mid = dates.sort_values().iloc[len(dates) // 2]
        w = g.d ** 2 * (g.l_out / g.l_out.median())
        util, cap_known = ground_truth.utilization_at(eia, cap, mid)
        years.append(dict(year=int(y), date=mid.date().isoformat(), n=int(len(g)),
                          gsd=_r(per[per.year == y].gsd.median(), 1),
                          fill=_r((g.fill * w).sum() / w.sum()), eia=_r(util), cap_known=bool(cap_known)))
    yd = pd.DataFrame(years)
    usable = yd[yd.n >= 30]
    stats = None
    if len(usable) >= 3:
        stats = dict(r=_r(np.corrcoef(usable.fill, usable.eia)[0, 1], 2),
                     mae=_r((usable.fill - usable.eia).abs().mean()),
                     baseline=_r((usable.eia - usable.eia.mean()).abs().mean()), n=int(len(usable)))

    fills = {str(int(y)): {str(int(r.osm_id)): _r(r.fill, 2) for r in g.itertuples()}
             for y, g in per_year.groupby("year")}

    lo = min(yd.date)
    start, end = pd.Timestamp(lo) - pd.DateOffset(months=6), pd.Timestamp(max(yd.date)) + pd.DateOffset(months=6)
    end = min(end, cap.index.max())
    weekly = []
    for d, v in eia[(eia.index >= max(start, cap.index.min())) & (eia.index <= end)].items():
        weekly.append([d.date().isoformat(), _r(v / ground_truth.value_at(cap, d))])

    s, w_, n_, e = site.bbox
    return dict(id=name, label=LABELS[name], status=STATUS[name][0], status_text=STATUS[name][1],
                center=[(s + n_) / 2, (w_ + e) / 2], bounds=[[s, w_], [n_, e]],
                eia_series=site.eia_stocks, tanks=tank_rows, years=years, stats=stats,
                fills=fills, eia_weekly=weekly,
                counts=dict(total=len(tank_rows), floating=sum(t[4] == "floating" for t in tank_rows),
                            fixed=sum(t[4] == "fixed" for t in tank_rows)))


def main():
    out = Path("dashboard/data.js")
    out.parent.mkdir(exist_ok=True)
    payload = {"generated": pd.Timestamp.now().date().isoformat(),
               "sites": [site_payload(n) for n in SITES if (Path("data/backtest") / n).exists()]}
    out.write_text("window.TANK_DATA = " + json.dumps(payload, separators=(",", ":")) + ";\n")
    for s in payload["sites"]:
        print(s["id"], s["counts"], s["stats"], [(y["year"], y["fill"], y["eia"], y["n"]) for y in s["years"]])
    print(out, f"{out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()

"""Debug overlays for shadow.measure on cached chips (see cache_chips.py).

    python -m pipeline.debug data/chips/2023 --n 24 --out data/debug/overlay_2023.png
"""
from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import shadow
from .naip import _circmean


def load(folder: Path) -> list[dict]:
    out = []
    for f in sorted(folder.glob("*.npz")):
        z = np.load(f, allow_pickle=False)
        out.append({k: z[k].item() if z[k].ndim == 0 else z[k] for k in z.files})
    return out


def tile_directions(chips: list[dict]) -> dict[str, float]:
    acc = defaultdict(lambda: ([], []))
    for c in chips:
        m = shadow.shadow_mask(c["chip"], c["cx"], c["cy"], c["r"])
        a, n = shadow.shadow_direction(m, c["cx"], c["cy"], c["r"])
        if n > 0:
            acc[c["item"]][0].append(a)
            acc[c["item"]][1].append(n)
    return {k: _circmean(np.array(a), np.array(w, float)) for k, (a, w) in acc.items()}


def run(chips, dirs, **kw):
    rows, dbg = [], []
    for c in chips:
        d = {}
        res = shadow.measure(c["chip"], c["cx"], c["cy"], c["r"], dirs[c["item"]], debug=d, gsd=c["gsd"], **kw)
        rows.append(dict(osm_id=c["osm_id"], item=c["item"], diameter_m=c["diameter_m"], fill=res.fill,
                         l_in_m=res.l_in_px * c["gsd"], l_out_m=res.l_out_px * c["gsd"],
                         n=res.n_chords, ok=res.ok, reason=res.reason))
        dbg.append(d)
    return pd.DataFrame(rows), dbg


def draw(ax, c, d, row):
    img = np.moveaxis(c["chip"], 0, -1)
    ax.imshow(img)
    if "mask" in d:
        ov = np.zeros((*d["mask"].shape, 4)); ov[..., 0] = 1; ov[..., 3] = 0.35 * d["mask"]
        ax.imshow(ov)
        th = np.linspace(0, 2 * np.pi, 200)
        ax.plot(d["cx"] + d["r"] * np.cos(th), d["cy"] + d["r"] * np.sin(th), "c-", lw=0.8)
    for ch in d.get("chords", []):
        x0, y0, dx, dy, h = ch["x0"], ch["y0"], ch["dx"], ch["dy"], ch["h"]
        if ch["li"]:
            ax.plot([x0 - h * dx, x0 + (ch["li"] - h) * dx], [y0 - h * dy, y0 + (ch["li"] - h) * dy], "y-", lw=1)
        if ch["lo"]:
            ax.plot([x0 + h * dx, x0 + (h + ch["lo"]) * dx], [y0 + h * dy, y0 + (h + ch["lo"]) * dy], "m-", lw=1)
    f = "—" if row.fill is None or (isinstance(row.fill, float) and math.isnan(row.fill)) else f"{row.fill:.2f}"
    ax.set_title(f"{row.osm_id} d={row.diameter_m:.0f}m fill={f}\nLin={row.l_in_m:.1f} Lout={row.l_out_m:.1f} {row.reason}",
                 fontsize=6)
    ax.axis("off")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="data/debug/overlay.png")
    a = ap.parse_args()
    chips = load(Path(a.folder))
    dirs = tile_directions(chips)
    print({k[-30:]: round(math.degrees(v), 1) for k, v in dirs.items()})
    df, dbg = run(chips, dirs)
    print(df.ok.value_counts().to_dict(), df.reason.value_counts().to_dict())
    print(df[df.ok].fill.describe().round(2).to_dict())
    df.to_csv(Path(a.out).with_suffix(".csv"), index=False)
    ok = df[df.ok]
    print("L_out m:", ok.l_out_m.describe().round(1).to_dict())
    print("L_in m:", ok.l_in_m.describe().round(1).to_dict())
    dup = ok.groupby("osm_id").filter(lambda g: len(g) > 1).groupby("osm_id").fill.agg(["min", "max"])
    if len(dup):
        print(f"repeatability: {len(dup)} tanks seen twice, median |dfill|={(dup['max'] - dup['min']).median():.3f}, "
              f"p90={(dup['max'] - dup['min']).quantile(0.9):.3f}")
    idx = np.random.default_rng(a.seed).choice(len(chips), min(a.n, len(chips)), replace=False)
    cols = 6; rows = math.ceil(len(idx) / cols)
    fig, axs = plt.subplots(rows, cols, figsize=(cols * 3, rows * 3.2))
    for ax, i in zip(axs.flat, idx):
        draw(ax, chips[i], dbg[i], df.iloc[i])
    for ax in axs.flat[len(idx):]:
        ax.axis("off")
    fig.tight_layout(); Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, dpi=130)


if __name__ == "__main__":
    main()

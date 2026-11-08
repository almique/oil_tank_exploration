"""Floating-roof fill estimation from one sub-metre optical image chip.

Geometry (sun direction d points *away* from the sun, i.e. the way shadows fall):

  * Outer shadow: the shell (height H) casts a crescent outside the tank on the
    anti-sun side, length L_out = H / tan(sun_elev).
  * Inner shadow: the rim on the sun side casts a crescent onto the floating roof,
    length L_in = depth / tan(sun_elev), where depth = rim-to-roof distance.

  fill = (H - depth) / H = 1 - L_in / L_out

Sun elevation and shell height cancel, so no acquisition time or tank height
metadata is needed. Both lengths are measured along chords parallel to d; for a
circle translated by L, every chord sees the same L, so the median over several
chords is robust to clutter.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates, sobel


@dataclass
class ShadowResult:
    fill: float | None
    l_in_px: float
    l_out_px: float
    n_chords: int
    cx: float
    cy: float
    r_px: float
    ok: bool
    reason: str = ""


def brightness(chip: np.ndarray) -> np.ndarray:
    """chip: (bands, h, w) uint8. Mean of RGB."""
    return chip[:3].astype(np.float32).mean(axis=0)


def shadow_mask(chip: np.ndarray, cx: float, cy: float, r: float, frac: float = 0.45) -> np.ndarray:
    """Dark pixels relative to the roof brightness of this tank."""
    b = brightness(chip)
    yy, xx = np.mgrid[: b.shape[0], : b.shape[1]]
    inside = (xx - cx) ** 2 + (yy - cy) ** 2 < (0.85 * r) ** 2
    roof = np.percentile(b[inside], 90) if inside.any() else np.percentile(b, 90)
    return (b < frac * roof).astype(np.float32)


def shadow_direction(mask: np.ndarray, cx: float, cy: float, r: float) -> tuple[float, int]:
    """Angle (radians, image coords, x right / y down) of dark mass just outside the tank."""
    yy, xx = np.mgrid[: mask.shape[0], : mask.shape[1]]
    rr = np.hypot(xx - cx, yy - cy)
    ann = (rr > 1.05 * r) & (rr < 1.6 * r) & (mask > 0.5)
    n = int(ann.sum())
    if n == 0:
        return float("nan"), 0
    return math.atan2((yy[ann] - cy).mean(), (xx[ann] - cx).mean()), n


def refine_circle(chip: np.ndarray, cx: float, cy: float, r: float) -> tuple[float, float, float]:
    """Snap centre/radius to the strongest circular edge near the prior (OSM) circle."""
    b = brightness(chip)
    g = np.hypot(sobel(b, 0), sobel(b, 1))
    th = np.linspace(0, 2 * np.pi, 180, endpoint=False)
    span = max(3.0, 0.15 * r)
    best = (-1.0, cx, cy, r)
    for dr in np.linspace(-0.06 * r, 0.06 * r, 7):
        rr = r + dr
        for dx in np.arange(-span, span + 0.01, 1.0):
            for dy in np.arange(-span, span + 0.01, 1.0):
                xs = cx + dx + rr * np.cos(th)
                ys = cy + dy + rr * np.sin(th)
                s = map_coordinates(g, [ys, xs], order=1, mode="nearest").mean()
                if s > best[0]:
                    best = (s, cx + dx, cy + dy, rr)
    return best[1], best[2], best[3]


def _run_length(profile: np.ndarray, t: np.ndarray, start: float, tol: float) -> float | None:
    """Length of a dark run that begins near `start` and goes toward +t.

    Returns 0 if nothing dark near `start`, None if the run never ends (clutter).
    """
    near = (t >= start - tol) & (t <= start + tol)
    if not (profile[near] > 0.5).any():
        return 0.0
    first = np.argmax((t >= start - tol) & (profile > 0.5))
    i = first
    while i < len(t) - 2:
        if profile[i] < 0.5 and profile[i + 1] < 0.5:
            return max(0.0, t[i] - start)
        i += 1
    return None


def roof_texture(chip: np.ndarray, cx: float, cy: float, r: float, gsd: float) -> float:
    """Std of ~1 m high-pass brightness inside 0.6 r. Floating roofs (drains, patches) are textured;
    fixed cone/dome roofs are smooth. Only meaningful at sub-metre GSD."""
    b = brightness(chip)
    yy, xx = np.mgrid[: b.shape[0], : b.shape[1]]
    inner = (xx - cx) ** 2 + (yy - cy) ** 2 < (0.6 * r) ** 2
    if inner.sum() < 50:
        return float("nan")
    hp = b - gaussian_filter(b, max(1.0, 0.9 / gsd))
    return float(np.std(hp[inner]))


def _rise(prof: np.ndarray, t: np.ndarray, lo: float, hi: float) -> tuple[float, float, float] | None:
    """Strongest rising edge of `prof` for t in [lo, hi].

    Returns (t_edge, mean_before, mean_after) or None if the window is empty.
    """
    sel = np.where((t >= lo) & (t <= hi))[0]
    if len(sel) < 4:
        return None
    g = np.gradient(prof)
    k = sel[np.argmax(g[sel])]
    before = prof[sel[0]:k + 1]
    after = prof[k + 1:k + 1 + max(4, len(before) // 2)]
    if len(before) == 0 or len(after) == 0:
        return None
    return float(t[k]), float(before.mean()), float(after.mean())


def measure(chip: np.ndarray, cx: float, cy: float, r: float, direction: float,
            refine: bool = True, debug: dict | None = None, gsd: float = 0.3,
            max_shadow_m: float = 35.0, rim_m: float = 0.6, contrast: float = 0.8) -> ShadowResult:
    """Edge-based measurement along chords parallel to the shadow direction.

    Inner shadow: from the sun-side rim (t=-h) to the strongest brightness rise on the roof.
    Outer shadow: from the anti-sun rim (t=+h) to the strongest brightness rise on the ground.
    A run only counts as shadow if it is clearly darker than what follows it (`contrast`).
    """
    if refine:
        cx, cy, r = refine_circle(chip, cx, cy, r)
    b = brightness(chip)
    valid = (chip[:3] > 0).all(axis=0).astype(np.float32)
    bs = gaussian_filter(b, 1.0)
    if debug is not None:
        debug.update(cx=cx, cy=cy, r=r)
    dx, dy = math.cos(direction), math.sin(direction)
    nx, ny = -dy, dx
    step = 0.5
    t = np.arange(-1.2 * r, r + max_shadow_m / gsd + 5, step)
    rim = rim_m / gsd
    lmax = max_shadow_m / gsd
    l_in, l_out = [], []
    for s in np.linspace(-0.5 * r, 0.5 * r, 11):
        h = math.sqrt(r * r - s * s)
        xs = cx + s * nx + t * dx
        ys = cy + s * ny + t * dy
        prof = map_coordinates(bs, [ys, xs], order=1, mode="constant", cval=0.0)
        okv = map_coordinates(valid, [ys, xs], order=0, mode="constant", cval=0.0)
        li = lo = None
        if okv[(t >= -h) & (t <= h + lmax)].min() > 0:
            ri = _rise(prof, t, -h + rim, -h + min(2 * h, lmax) - rim)
            if ri is not None:
                li = ri[0] + h if ri[1] < contrast * ri[2] else 0.0
            ro = _rise(prof, t, h + rim, h + lmax)
            if ro is not None and ro[1] < contrast * ro[2]:
                lo = ro[0] - h
        if debug is not None:
            debug.setdefault("chords", []).append(
                dict(s=s, h=h, li=li, lo=lo, x0=cx + s * nx, y0=cy + s * ny, dx=dx, dy=dy))
        if li is None or lo is None or lo < 2 * rim:
            continue
        l_in.append(li)
        l_out.append(lo)
    if len(l_out) < 5:
        return ShadowResult(None, float("nan"), float("nan"), len(l_out), cx, cy, r, False, "few valid chords")
    li, lo = float(np.median(l_in)), float(np.median(l_out))
    spread = float(np.subtract(*np.percentile(l_out, [75, 25])))
    if spread > 0.25 * lo + rim:
        return ShadowResult(None, li, lo, len(l_out), cx, cy, r, False, "inconsistent outer shadow")
    fill = float(np.clip(1.0 - li / lo, 0.0, 1.0))
    return ShadowResult(fill, li, lo, len(l_out), cx, cy, r, True)

"""Free ground truth: EIA weekly Cushing crude stocks (no API key needed)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

EIA_XLS = "https://www.eia.gov/dnav/pet/hist_xls/{series}w.xls"
CUSHING = "W_EPC0_SAX_YCUOK_MBBL"  # Cushing, OK ending stocks excl. SPR, thousand bbl


def eia_weekly(series: str = CUSHING, cache: Path | None = None) -> pd.Series:
    if cache is None or not cache.exists():
        r = requests.get(EIA_XLS.format(series=series), timeout=60)
        r.raise_for_status()
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(r.content)
        src = r.content if cache is None else cache
    else:
        src = cache
    df = pd.read_excel(src, sheet_name="Data 1", skiprows=2)
    df.columns = ["date", "value"]
    s = df.dropna().set_index(pd.to_datetime(df.dropna()["date"]))["value"].astype(float)
    return s.sort_index()


def value_at(series: pd.Series, when) -> float:
    """Linear interpolation of the weekly series at an arbitrary date."""
    when = pd.Timestamp(when)
    s = series.copy()
    if when not in s.index:
        s.loc[when] = float("nan")
    s = s.sort_index().interpolate(method="time")
    return float(s.loc[when])

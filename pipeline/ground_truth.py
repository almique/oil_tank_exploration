"""Free ground truth: EIA weekly Cushing crude stocks (no API key needed)."""
from __future__ import annotations

import io
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
        src = io.BytesIO(r.content) if cache is None else cache
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


EIA_CAPACITY_XLSX = "https://www.eia.gov/petroleum/storagecapacity/crudeoilstorage.xlsx"


def cushing_working_capacity(cache: Path | None = None) -> pd.Series:
    """Cushing tank working storage capacity, thousand bbl, semiannual/annual 2011-03 .. 2024-03."""
    return working_capacity("Cushing", "Tank Working Storage Capacity", cache)


def working_capacity(sheet: str, row_name: str, cache: Path | None = None) -> pd.Series:
    """One working-capacity row from EIA's discontinued Working and Net Available Shell Storage
    Capacity report (crudeoilstorage.xlsx), thousand bbl, 2011-03 .. 2024-03."""
    if cache is None or not cache.exists():
        r = requests.get(EIA_CAPACITY_XLSX, timeout=60)
        r.raise_for_status()
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(r.content)
        src = io.BytesIO(r.content) if cache is None else cache
    else:
        src = cache
    raw = pd.read_excel(src, sheet_name=sheet, header=None)
    dates = pd.to_datetime(raw.iloc[3, 1:], errors="coerce")
    row = raw[raw[0].astype(str).str.strip() == row_name].iloc[0, 1:]
    s = pd.Series(pd.to_numeric(row.values, errors="coerce"), index=dates).dropna()
    return s[s.index.notna()].sort_index()


def utilization_at(stocks: pd.Series, capacity: pd.Series, when) -> tuple[float, bool]:
    """EIA stocks / working capacity at `when`. Second value is False if capacity was extrapolated."""
    when = pd.Timestamp(when)
    inside = capacity.index.min() <= when <= capacity.index.max()
    cap = value_at(capacity, when) if inside else float(capacity.iloc[0 if when < capacity.index.min() else -1])
    return value_at(stocks, when) / cap, inside

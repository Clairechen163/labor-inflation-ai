"""Fetch macro series from the FRED API and merge them into one monthly table."""
import os
import warnings

import pandas as pd
import requests

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

# name -> FRED series id. Verify IDs on fred.stlouisfed.org if a pull fails.
SERIES = {
    "adp": "ADPMNUSNERSA",          # ADP private payrolls (persons, SA)
    "payems": "PAYEMS",             # BLS total nonfarm payrolls (thousands, SA)
    "unrate": "UNRATE",             # Unemployment rate
    "unrate_20_24": "LNS14000036",  # Unemployment rate, 20-24 yrs (verify ID)
    "wages": "CES0500000003",       # Avg hourly earnings, private (USD)
    "cpi": "CPIAUCSL",              # CPI, all items
    "core_cpi": "CPILFESL",         # CPI, less food and energy
    "pce": "PCEPI",                 # PCE price index
    "core_pce": "PCEPILFE",         # PCE price index, less food and energy
    "fedfunds": "FEDFUNDS",         # Effective federal funds rate
}


def fetch_series(series_id: str, api_key: str, start: str = "2015-01-01") -> pd.Series:
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start,
    }
    r = requests.get(FRED_URL, params=params, timeout=30)
    r.raise_for_status()
    obs = r.json()["observations"]
    s = pd.Series(
        {pd.Timestamp(o["date"]): pd.to_numeric(o["value"], errors="coerce") for o in obs},
        name=series_id,
    )
    return s.sort_index()


def build_dataset(api_key: str | None = None, start: str = "2015-01-01") -> pd.DataFrame:
    api_key = api_key or os.environ.get("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("Set FRED_API_KEY (see .env.example).")
    cols = {}
    for name, sid in SERIES.items():
        try:
            cols[name] = fetch_series(sid, api_key, start)
        except Exception as e:  # keep going if one series fails
            warnings.warn(f"Could not fetch {name} ({sid}): {e}")
    df = pd.DataFrame(cols)
    df.index = df.index.to_period("M").to_timestamp()
    return df.groupby(level=0).last()


if __name__ == "__main__":
    out = build_dataset()
    os.makedirs("data", exist_ok=True)
    out.to_csv("data/fred_monthly.csv")
    print(out.tail())

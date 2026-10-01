"""Derived measures: inflation rates, job changes, real wages, youth gap."""
import pandas as pd

PRICE_COLS = ["cpi", "core_cpi", "pce", "core_pce", "wages"]


def derive(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in PRICE_COLS:
        if c in out:
            out[f"{c}_yoy"] = out[c].pct_change(12) * 100
    if "adp" in out:
        out["adp_jobs_k"] = out["adp"].diff() / 1000  # persons -> thousands
    if "payems" in out:
        out["payems_jobs_k"] = out["payems"].diff()   # already thousands
    if {"wages_yoy", "cpi_yoy"} <= set(out.columns):
        out["real_wage_cpi"] = out["wages_yoy"] - out["cpi_yoy"]
    if {"wages_yoy", "pce_yoy"} <= set(out.columns):
        out["real_wage_pce"] = out["wages_yoy"] - out["pce_yoy"]
    if {"unrate_20_24", "unrate"} <= set(out.columns):
        out["youth_gap"] = out["unrate_20_24"] - out["unrate"]
    return out

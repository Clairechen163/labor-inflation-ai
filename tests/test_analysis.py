import numpy as np
import pandas as pd

from src.analysis import derive


def _frame(n=30):
    idx = pd.date_range("2023-01-01", periods=n, freq="MS")
    base = pd.Series(np.arange(n, dtype=float) + 100, index=idx)
    return pd.DataFrame({
        "cpi": base, "core_cpi": base, "pce": base, "core_pce": base,
        "wages": base * 0.3, "adp": base * 1e6, "payems": base * 1e3,
        "unrate": 4.0, "unrate_20_24": 8.0,
    })


def test_yoy_and_real_wage():
    out = derive(_frame())
    assert "cpi_yoy" in out and "real_wage_cpi" in out
    assert out["cpi_yoy"].iloc[:12].isna().all()
    assert abs(out["cpi_yoy"].iloc[-1] - (129 / 117 - 1) * 100) < 1e-6


def test_jobs_units_and_youth_gap():
    out = derive(_frame())
    assert out["adp_jobs_k"].iloc[-1] == 1000.0
    assert (out["youth_gap"].dropna() == 4.0).all()

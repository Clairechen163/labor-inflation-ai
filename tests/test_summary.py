import numpy as np
import pandas as pd
import pytest

from src import models, summary
from src.analysis import derive
from tests.test_models import synthetic


def macro(n=120, end="2026-10-01"):
    """A full dashboard-style table, including the real-world gap in October 2025."""
    idx = pd.date_range(end=end, periods=n, freq="MS")
    t = np.arange(n, dtype=float)
    df = pd.DataFrame({
        "cpi": 100 * 1.003 ** t, "core_cpi": 100 * 1.002 ** t, "pce": 100 * 1.0025 ** t,
        "core_pce": 100 * 1.0022 ** t, "wages": 30 * 1.0028 ** t, "energy_cpi": 200 * 1.006 ** t,
        "unrate": 4.0 + 0.001 * t, "unrate_20_24": 7.5 + 0.001 * t, "fedfunds": 3.9,
        "payems": 150000 + 100 * t, "adp": (125000 + 80 * t) * 1000, "infl_exp": 3.5,
    }, index=idx)
    df.loc["2025-10-01", ["cpi", "core_cpi", "energy_cpi", "unrate", "unrate_20_24"]] = np.nan
    df.loc[idx[-1], ["pce", "core_pce"]] = np.nan          # PCE is released later
    return df


def test_missing_base_month_is_not_padded():
    out = derive(macro())
    assert np.isnan(out.loc["2026-10-01", "cpi_yoy"])       # base month October 2025 is missing
    expected = (1.003 ** 12 - 1) * 100
    assert out.loc["2026-09-01", "cpi_yoy"] == pytest.approx(expected)


def test_latest_readings_use_last_available_month_per_series():
    tbl = summary.latest_readings(derive(macro())).set_index("Measure")
    assert tbl.loc["CPI inflation, year over year", "Month"] == "Sep 2026"       # Oct has no YoY
    assert tbl.loc["Core PCE inflation, year over year", "Month"] == "Sep 2026"  # not yet released
    assert tbl.loc["Average hourly earnings, year over year", "Month"] == "Oct 2026"
    assert tbl.loc["Unemployment rate", "A year earlier"] == "n/a"               # October 2025 missing


def test_findings_follow_the_numbers():
    text = " ".join(summary.findings(derive(macro())))
    assert "Real wages are falling" in text          # wages +3.4% vs CPI +3.7%
    assert "Energy is pushing headline inflation above core" in text
    assert "above the 2% target" in text
    assert "does not isolate AI" in text


def test_results_block_and_readme_replacement():
    res = models.run_all(synthetic(260), horizon=6, min_train=60)
    block = summary.results_block(res, models.horizon_robustness(synthetic(260), horizons=(3, 6), min_train=60))
    assert "Clark-West" in block and "Across horizons" in block and "not causal" in block
    readme = "intro\n<!-- AUTO:results:start -->\nSTALE_TEXT\n<!-- AUTO:results:end -->\nrest"
    once = summary.replace_block(readme, "results", block)
    assert "STALE_TEXT" not in once and once.startswith("intro") and once.endswith("rest")
    assert summary.replace_block(once, "results", block) == once      # idempotent
    with pytest.raises(ValueError):
        summary.replace_block("no markers", "results", block)

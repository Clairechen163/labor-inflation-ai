import numpy as np
import pandas as pd
import pytest

from src import models


def synthetic(n=300, seed=0, lead=2, beta=0.3):
    """Monthly data where wage growth leads core inflation by `lead` months."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2000-01-01", periods=n, freq="MS")
    w = np.zeros(n)
    for t in range(1, n):
        w[t] = 0.5 * w[t - 1] + rng.normal(0, 0.002)
    pi = np.zeros(n)
    for t in range(1, n):
        pi[t] = 0.002 + 0.3 * pi[t - 1] + (beta * w[t - lead] if t >= lead else 0) + rng.normal(0, 0.0005)
    core = 100 * np.cumprod(1 + pi)
    wages = 20 * np.cumprod(1 + 0.003 + w)
    energy = 100 * np.cumprod(1 + rng.normal(0.002, 0.02, n))
    return pd.DataFrame({
        "core_pce": core, "wages": wages, "energy_cpi": energy,
        "unrate": 5 + rng.normal(0, 0.5, n).cumsum() * 0.05,
        "infl_exp": 3 + rng.normal(0, 0.3, n),
    }, index=idx)


def test_target_alignment():
    df = synthetic(60)
    f = models.build_features(df, horizon=6)
    t = 10
    expected = ((df["core_pce"].iloc[t + 6] / df["core_pce"].iloc[t]) ** 2 - 1) * 100
    assert f["target"].iloc[t] == pytest.approx(expected)
    assert f["target"].iloc[-6:].isna().all()   # unknown future


def test_missing_series_raises_clear_error():
    with pytest.raises(KeyError):
        models.build_features(synthetic(40).drop(columns=["energy_cpi"]))


def test_train_mask_never_uses_unrealized_targets():
    idx = pd.date_range("2010-01-01", periods=60, freq="MS")
    months = models._months(idx)
    h, origin = 6, months[40]
    mask = models.train_mask(months, origin, h)
    assert months[mask].max() + h <= origin      # target window closed by origin month
    assert mask.sum() == 40 - h + 1


def test_walk_forward_shape_and_columns():
    df = synthetic(220)
    frame = models.build_features(df, horizon=6)
    light = {
        models.NAIVE: (None, None),
        "Ridge: + wage growth": (models.FULL_FEATURES, models._ridge),
    }
    preds = models.walk_forward(frame, horizon=6, min_train=60, models=light)
    assert list(preds.columns) == ["actual", models.NAIVE, "Ridge: + wage growth"]
    assert preds.notna().all().all()
    assert preds.index.min() >= frame.dropna().index[60]


def test_walk_forward_requires_enough_data():
    frame = models.build_features(synthetic(40), horizon=6)
    with pytest.raises(ValueError):
        models.walk_forward(frame, horizon=6, min_train=96)


def test_dm_flags_clearly_better_model():
    rng = np.random.default_rng(1)
    bench = rng.normal(0, 1, 200)
    good = rng.normal(0, 0.3, 200)
    stat, p = models.diebold_mariano(good, bench, h=6)
    assert stat < 0 and p < 0.01


def test_dm_equal_models_not_significant():
    rng = np.random.default_rng(2)
    a, b = rng.normal(0, 1, 200), rng.normal(0, 1, 200)
    assert models.diebold_mariano(a, b, h=6)[1] > 0.01


def test_granger_detects_planted_lead_and_not_reverse():
    frame = models.build_features(synthetic(400, lead=2, beta=0.3), horizon=6)
    g = models.granger_table(frame, maxlag=4)
    assert g["wages -> inflation"].min() < 0.01
    assert g["inflation -> wages"].min() > 0.001


def test_regression_recovers_wage_signal():
    frame = models.build_features(synthetic(400), horizon=6)
    table, summ = models.phillips_regression(frame, horizon=6)
    assert {"coef", "std err (HAC)", "p-value", "CI low", "CI high"} <= set(table.columns)
    assert summ["joint p-value, wage terms"] < 0.05
    assert summ["adj R2 with wages"] >= summ["adj R2 without wages"]


def test_run_all_and_report(tmp_path):
    light = {
        models.NAIVE: (None, None),
        "Ridge: + wage growth": (models.FULL_FEATURES, models._ridge),
    }
    res = models.run_all(synthetic(260), horizon=6, min_train=60, models=light)
    out = tmp_path / "results.md"
    text = models.write_report(res, str(out))
    assert out.exists()
    for heading in ["Granger", "Phillips-curve", "Out-of-sample backtest", "Diebold-Mariano"]:
        assert heading in text
    assert "Full sample" in res["scores"]

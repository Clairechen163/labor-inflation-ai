"""Statistical analysis and forecasting for the wage / inflation question.

Q1. Does wage growth help predict core inflation once energy prices, labor-market
    slack and inflation expectations are accounted for?
      -> Granger-style lead/lag tests and a Phillips-curve regression with
         heteroskedasticity- and autocorrelation-robust (HAC) standard errors.
Q2. Does adding wage growth improve *out-of-sample* forecasts of core PCE inflation
    compared with simple benchmarks?
      -> Expanding-window walk-forward backtest with an explicit embargo (no look-ahead),
         plus a Diebold-Mariano test of forecast accuracy against a naive benchmark.

Predictive relationships are not causal effects. Results describe what the data
support, not why prices move.
"""
from __future__ import annotations

import contextlib
import io
import os

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.stattools import adfuller, grangercausalitytests

REQUIRED = ["core_pce", "wages", "energy_cpi", "unrate", "infl_exp"]
AR_FEATURES = ["infl_3m", "infl_12m"]
NO_WAGE_FEATURES = AR_FEATURES + ["energy_3m", "unrate", "infl_exp"]
FULL_FEATURES = NO_WAGE_FEATURES + ["wage_3m", "wage_12m"]
NAIVE = "Naive (trailing 12m inflation)"


# --------------------------------------------------------------------------- features
def _ann(s: pd.Series, k: int) -> pd.Series:
    """Annualized % change over k months."""
    return ((s / s.shift(k)) ** (12 / k) - 1) * 100


def build_features(df: pd.DataFrame, horizon: int = 6) -> pd.DataFrame:
    """Monthly feature table plus `target` = core PCE inflation over the *next* `horizon`
    months (annualized %), aligned to the month the forecast is made."""
    missing = [c for c in REQUIRED if c not in df]
    if missing:
        raise KeyError(f"Missing series for the models: {missing}")
    d = df.asfreq("MS")
    f = pd.DataFrame(index=d.index)
    f["infl_1m"] = _ann(d["core_pce"], 1)
    f["infl_3m"] = _ann(d["core_pce"], 3)
    f["infl_12m"] = _ann(d["core_pce"], 12)
    f["wage_1m"] = _ann(d["wages"], 1)
    f["wage_3m"] = _ann(d["wages"], 3)
    f["wage_12m"] = _ann(d["wages"], 12)
    f["energy_3m"] = d["energy_cpi"].pct_change(3) * 100
    f["unrate"] = d["unrate"]
    f["infl_exp"] = d["infl_exp"]
    f["target"] = _ann(d["core_pce"], horizon).shift(-horizon)
    return f


def _months(index: pd.DatetimeIndex) -> np.ndarray:
    return (index.year * 12 + index.month).to_numpy()


def train_mask(months: np.ndarray, origin_month: int, horizon: int) -> np.ndarray:
    """Rows usable for training when forecasting at `origin_month`.

    A row at month m has a target covering months m+1..m+horizon, which is only known
    at month m+horizon. Requiring m + horizon <= origin prevents look-ahead leakage."""
    return months <= origin_month - horizon


# --------------------------------------------------------------------------- diagnostics
def _adf_p(s: pd.Series) -> float:
    """ADF p-value; avoids statsmodels' return-type FutureWarning on newer versions."""
    try:
        return float(adfuller(s, autolag="AIC", result_object=False)[1])
    except TypeError:  # older statsmodels without `result_object`
        return float(adfuller(s, autolag="AIC")[1])


def adf_table(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    rows = []
    for c in cols:
        s = frame[c].dropna()
        p = _adf_p(s)
        rows.append({"series": c, "n": len(s), "ADF p-value": p, "stationary at 5%": bool(p < 0.05)})
    return pd.DataFrame(rows).set_index("series")


def _stationary(s: pd.Series) -> tuple[pd.Series, bool]:
    s = s.dropna()
    if _adf_p(s) > 0.05:
        return s.diff().dropna(), True
    return s, False


def granger_pvalues(frame: pd.DataFrame, cause: str, effect: str, maxlag: int = 6) -> pd.Series:
    """p-values (F-test) that `cause` helps predict `effect` at lags 1..maxlag.

    Series that fail an ADF test are first-differenced. Granger tests measure
    predictive precedence, not causation."""
    both = frame[[cause, effect]].dropna()
    c, _ = _stationary(both[cause])
    e, _ = _stationary(both[effect])
    data = pd.concat([e, c], axis=1, join="inner").dropna()
    with contextlib.redirect_stdout(io.StringIO()):
        res = grangercausalitytests(data.to_numpy(), maxlag=maxlag)
    return pd.Series({lag: float(res[lag][0]["ssr_ftest"][1]) for lag in range(1, maxlag + 1)}, name=f"{cause}->{effect}")


def granger_table(frame: pd.DataFrame, maxlag: int = 6) -> pd.DataFrame:
    """Both directions: wage growth -> inflation, and inflation -> wage growth
    (the second tests the 'wage-price spiral' feedback)."""
    out = pd.DataFrame({
        "wages -> inflation": granger_pvalues(frame, "wage_1m", "infl_1m", maxlag),
        "inflation -> wages": granger_pvalues(frame, "infl_1m", "wage_1m", maxlag),
    })
    out.index.name = "lag (months)"
    return out


# --------------------------------------------------------------------------- regression
def phillips_regression(frame: pd.DataFrame, horizon: int = 6, start=None, end=None):
    """OLS of future core inflation on current predictors with HAC standard errors.

    Overlapping forecast windows make residuals autocorrelated, so plain OLS errors would
    be too small. Returns (coefficient table for the model with wages, summary dict)."""
    data = frame.dropna(subset=FULL_FEATURES + ["target"])
    if start is not None:
        data = data[data.index >= pd.Timestamp(start)]
    if end is not None:
        data = data[data.index < pd.Timestamp(end)]
    if len(data) < 40:
        raise ValueError(f"Only {len(data)} usable months; need at least 40 for the regression.")
    y = data["target"]
    maxlags = horizon + 2
    m0 = sm.OLS(y, sm.add_constant(data[NO_WAGE_FEATURES])).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    m1 = sm.OLS(y, sm.add_constant(data[FULL_FEATURES])).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    ci = m1.conf_int()
    table = pd.DataFrame({
        "coef": m1.params, "std err (HAC)": m1.bse, "p-value": m1.pvalues,
        "CI low": ci[0], "CI high": ci[1],
    })
    wald = m1.wald_test("wage_3m = 0, wage_12m = 0", use_f=True, scalar=True)
    summary = {
        "n": int(m1.nobs),
        "first month": data.index.min().strftime("%Y-%m"),
        "last month": data.index.max().strftime("%Y-%m"),
        "adj R2 without wages": float(m0.rsquared_adj),
        "adj R2 with wages": float(m1.rsquared_adj),
        "joint p-value, wage terms": float(np.squeeze(wald.pvalue)),
    }
    return table, summary


def regime_comparison(frame: pd.DataFrame, horizon: int = 6, split: str = "2021-01-01") -> pd.DataFrame:
    """Is the role of wage growth stable across the pre-2021 and 2021+ regimes?"""
    rows = []
    for label, kw in [("before " + split[:4], {"end": split}), (split[:4] + " onward", {"start": split})]:
        try:
            table, summ = phillips_regression(frame, horizon, **kw)
        except ValueError:  # too few months in this regime
            rows.append({"period": label, "n": 0, "wage_12m coef": np.nan,
                         "wage_12m p-value": np.nan, "joint p-value, wage terms": np.nan})
            continue
        rows.append({
            "period": label, "n": summ["n"],
            "wage_12m coef": table.loc["wage_12m", "coef"],
            "wage_12m p-value": table.loc["wage_12m", "p-value"],
            "joint p-value, wage terms": summ["joint p-value, wage terms"],
        })
    return pd.DataFrame(rows).set_index("period")


# --------------------------------------------------------------------------- forecasting
def _ridge():
    return make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 20)))


def _gbr():
    return GradientBoostingRegressor(n_estimators=150, max_depth=2, learning_rate=0.05,
                                     subsample=0.8, random_state=0)


def default_models() -> dict:
    """name -> (feature columns, estimator factory). The naive benchmark has no estimator."""
    return {
        NAIVE: (None, None),
        "Ridge: own lags": (AR_FEATURES, _ridge),
        "Ridge: + energy, slack, expectations": (NO_WAGE_FEATURES, _ridge),
        "Ridge: + wage growth": (FULL_FEATURES, _ridge),
        "Gradient boosting: + wage growth": (FULL_FEATURES, _gbr),
    }


def walk_forward(frame: pd.DataFrame, horizon: int = 6, min_train: int = 96, models: dict | None = None) -> pd.DataFrame:
    """Expanding-window backtest. At each origin month the models are refit using only
    rows whose targets were fully observed by that month (see `train_mask`)."""
    models = models or default_models()
    feats = sorted({c for cols, _ in models.values() if cols for c in cols} | {"infl_12m"})
    data = frame.dropna(subset=feats + ["target"])
    months = _months(data.index)
    rows, index = [], []
    for i in range(len(data)):
        mask = train_mask(months, months[i], horizon)
        if mask.sum() < min_train:
            continue
        train, x0 = data[mask], data.iloc[[i]]
        row = {"actual": float(x0["target"].iloc[0])}
        for name, (cols, factory) in models.items():
            if cols is None:
                row[name] = float(x0["infl_12m"].iloc[0])
            else:
                m = factory()
                m.fit(train[cols], train["target"])
                row[name] = float(m.predict(x0[cols])[0])
        rows.append(row)
        index.append(data.index[i])
    if not rows:
        raise ValueError("Not enough data for the walk-forward backtest; lower min_train.")
    return pd.DataFrame(rows, index=index)


def diebold_mariano(err_model, err_bench, h: int) -> tuple[float, float]:
    """Diebold-Mariano test (squared-error loss, Bartlett-weighted long-run variance,
    Harvey-Leybourne-Newbold small-sample correction). Negative statistic = model is better."""
    d = np.asarray(err_model, float) ** 2 - np.asarray(err_bench, float) ** 2
    n = len(d)
    if n <= h + 2:
        return float("nan"), float("nan")
    dc = d - d.mean()
    lrv = dc @ dc / n
    for k in range(1, h):
        lrv += 2 * (1 - k / h) * (dc[k:] @ dc[:-k]) / n
    if lrv <= 0:
        return float("nan"), float("nan")
    stat = d.mean() / np.sqrt(lrv / n)
    stat *= np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    p = 2 * (1 - stats.t.cdf(abs(stat), df=n - 1))
    return float(stat), float(p)


def score(preds: pd.DataFrame, horizon: int) -> pd.DataFrame:
    rows = []
    bench_err = preds[NAIVE] - preds["actual"]
    bench_rmse = float(np.sqrt((bench_err ** 2).mean()))
    for col in preds.columns.drop("actual"):
        err = preds[col] - preds["actual"]
        rmse = float(np.sqrt((err ** 2).mean()))
        row = {"model": col, "RMSE": rmse, "MAE": float(err.abs().mean()),
               "RMSE vs naive": np.nan, "DM p-value vs naive": np.nan}
        if col != NAIVE:
            row["RMSE vs naive"] = rmse / bench_rmse
            row["DM p-value vs naive"] = diebold_mariano(err, bench_err, horizon)[1]
        rows.append(row)
    return pd.DataFrame(rows).set_index("model")


def score_periods(preds: pd.DataFrame, horizon: int) -> dict[str, pd.DataFrame]:
    """Full sample plus 2023 onward (after the 2021-22 inflation surge dominates errors)."""
    out = {"Full sample": score(preds, horizon)}
    recent = preds[preds.index >= "2023-01-01"]
    if len(recent) >= horizon + 12:
        out["2023 onward"] = score(recent, horizon)
    return out


# --------------------------------------------------------------------------- orchestration
def run_all(df: pd.DataFrame, horizon: int = 6, min_train: int = 96, models: dict | None = None) -> dict:
    frame = build_features(df, horizon)
    preds = walk_forward(frame, horizon, min_train, models)
    reg_table, reg_summary = phillips_regression(frame, horizon)
    return {
        "horizon": horizon,
        "frame": frame,
        "adf": adf_table(frame, ["infl_1m", "wage_1m"]),
        "granger": granger_table(frame),
        "regression": reg_table,
        "regression_summary": reg_summary,
        "regimes": regime_comparison(frame, horizon),
        "predictions": preds,
        "scores": score_periods(preds, horizon),
    }


def _md(df: pd.DataFrame, digits: int = 3) -> str:
    def fmt(v):
        return "" if pd.isna(v) else (f"{v:.{digits}f}" if isinstance(v, (float, np.floating)) else str(v))
    cols = [df.index.name or ""] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for idx, row in df.iterrows():
        lines.append("| " + " | ".join([str(idx)] + [fmt(v) for v in row]) + " |")
    return "\n".join(lines)


def write_report(res: dict, path: str = "reports/results.md") -> str:
    h = res["horizon"]
    s = res["regression_summary"]
    parts = [
        "# Model results",
        "",
        "_Generated by `python -m src.models`. Predictive relationships only; nothing here is a causal claim._",
        "",
        f"Target: core PCE inflation over the next {h} months, annualized %. "
        f"Regression sample: {s['first month']} to {s['last month']} (n={s['n']}).",
        "",
        "## 1. Stationarity checks (ADF)",
        _md(res["adf"]),
        "",
        "## 2. Granger tests (p-values by lag; low = the first series helps predict the second)",
        "Series failing the ADF test are first-differenced before testing.",
        "",
        _md(res["granger"]),
        "",
        f"## 3. Phillips-curve regression (HAC standard errors, {h + 2} lags)",
        _md(res["regression"]),
        "",
        f"Adjusted R2 without wage terms: {s['adj R2 without wages']:.3f}; with: {s['adj R2 with wages']:.3f}. "
        f"Joint test that both wage terms are zero: p = {s['joint p-value, wage terms']:.3f}.",
        "",
        "### Stability across regimes",
        _md(res["regimes"]),
        "",
        f"## 4. Out-of-sample backtest ({h}-month horizon, expanding window, no look-ahead)",
    ]
    for label, tbl in res["scores"].items():
        parts += [f"### {label}", _md(tbl), ""]
    parts += [
        "RMSE vs naive below 1 means the model beat the naive benchmark. The Diebold-Mariano p-value tests "
        "whether the difference in squared errors is statistically distinguishable from zero.",
        "",
    ]
    text = "\n".join(parts)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return text


def main() -> None:
    from src.fetch import build_dataset

    res = run_all(build_dataset())
    write_report(res, "reports/results.md")
    res["predictions"].to_csv("reports/backtest_predictions.csv")
    print(f"Wrote reports/results.md (n={res['regression_summary']['n']} regression rows).")


if __name__ == "__main__":
    main()

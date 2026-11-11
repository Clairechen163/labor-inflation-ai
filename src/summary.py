"""Plain-language summaries generated from the data, so the README never goes stale.

Everything here is computed: the wording changes with the numbers (for example "above" vs
"below"), and no sentence makes a causal claim. `scripts/refresh.py` writes these blocks
into README.md between AUTO markers.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from src import models

ALPHA = 0.05


# --------------------------------------------------------------------------- helpers
def _last(s: pd.Series):
    """(value, month) of the most recent non-missing observation, or None."""
    s = s.dropna()
    return None if s.empty else (float(s.iloc[-1]), s.index[-1])


def _mon(ts: pd.Timestamp) -> str:
    return ts.strftime("%b %Y")


def _p(p: float) -> str:
    if p is None or np.isnan(p):
        return "n/a"
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def _latest_common(df: pd.DataFrame, cols: list[str]):
    """Most recent month in which every column in `cols` is observed."""
    if not set(cols) <= set(df.columns):
        return None
    d = df[cols].dropna()
    return None if d.empty else d.iloc[-1]


# --------------------------------------------------------------------------- latest readings
READINGS = [
    ("CPI inflation, year over year", "cpi_yoy", "{:.1f}%"),
    ("Core CPI inflation, year over year", "core_cpi_yoy", "{:.1f}%"),
    ("CPI energy, year over year", "energy_cpi_yoy", "{:.1f}%"),
    ("PCE inflation, year over year", "pce_yoy", "{:.1f}%"),
    ("Core PCE inflation, year over year", "core_pce_yoy", "{:.1f}%"),
    ("Average hourly earnings, year over year", "wages_yoy", "{:.1f}%"),
    ("Real wage growth (earnings minus CPI)", "real_wage_cpi", "{:+.1f} pts"),
    ("Unemployment rate", "unrate", "{:.1f}%"),
    ("Unemployment rate, ages 20-24", "unrate_20_24", "{:.1f}%"),
    ("Payroll change, BLS (thousands)", "payems_jobs_k", "{:+,.0f}"),
    ("Private payroll change, ADP (thousands)", "adp_jobs_k", "{:+,.0f}"),
    ("Effective federal funds rate", "fedfunds", "{:.2f}%"),
]


def latest_readings(df: pd.DataFrame) -> pd.DataFrame:
    """Most recent value of each headline series, with the month it refers to.

    Series end in different months (PCE is released later than CPI; year-over-year CPI is
    unavailable when the base month is missing), so each row carries its own date."""
    rows = []
    for label, col, fmt in READINGS:
        if col not in df:
            continue
        last = _last(df[col])
        if last is None:
            continue
        value, month = last
        year_ago = df[col].get(month - pd.DateOffset(years=1), np.nan)
        rows.append({
            "Measure": label, "Latest": fmt.format(value), "Month": _mon(month),
            "A year earlier": "n/a" if pd.isna(year_ago) else fmt.format(year_ago),
        })
    return pd.DataFrame(rows)


def findings(df: pd.DataFrame) -> list[str]:
    """Descriptive bullets about the latest data. Wording is chosen by the numbers."""
    out = []

    r = _latest_common(df, ["wages_yoy", "cpi_yoy"])
    if r is not None:
        gap = r["wages_yoy"] - r["cpi_yoy"]
        word = "roughly flat" if abs(gap) < 0.1 else ("falling" if gap < 0 else "rising")
        out.append(
            f"**Real wages are {word}.** In {_mon(r.name)} average hourly earnings were up "
            f"{r['wages_yoy']:.1f}% from a year earlier and consumer prices {r['cpi_yoy']:.1f}%, "
            f"a gap of {gap:+.1f} points.")

    r = _latest_common(df, ["cpi_yoy", "core_cpi_yoy", "energy_cpi_yoy"])
    if r is not None:
        head, core, en = r["cpi_yoy"], r["core_cpi_yoy"], r["energy_cpi_yoy"]
        if abs(head - core) <= 0.1:
            title, tail = "Headline and core inflation are close.", "so energy is not opening a gap between them."
        elif head > core:
            title = "Energy is pushing headline inflation above core." if en > head else "Headline inflation is above core."
            tail = ("so prices excluding food and energy are rising more slowly than the headline." if en > head
                    else "so energy is not what is lifting the headline.")
        else:
            title = "Energy is holding headline inflation below core." if en < head else "Headline inflation is below core."
            tail = ("so prices excluding food and energy are rising faster than the headline." if en < head
                    else "so energy is not what is holding the headline down.")
        out.append(
            f"**{title}** In {_mon(r.name)} CPI was up {head:.1f}% and core CPI {core:.1f}%, "
            f"while CPI energy was {'up' if en >= 0 else 'down'} {abs(en):.1f}%, {tail}")

    if "core_pce_yoy" in df and _last(df["core_pce_yoy"]):
        v, m = _last(df["core_pce_yoy"])
        word = "at" if abs(v - 2) < 0.15 else ("above" if v > 2 else "below")
        text = f"**Core PCE, the Fed's preferred measure, is {word} the 2% target.** It was {v:.1f}% in {_mon(m)}"
        prev = df["core_pce_yoy"].get(m - pd.DateOffset(months=3), np.nan)
        if not pd.isna(prev):
            text += f", compared with {prev:.1f}% three months earlier"
        text += "."
        if "fedfunds" in df and _last(df["fedfunds"]):
            f, fm = _last(df["fedfunds"])
            f3 = df["fedfunds"].get(fm - pd.DateOffset(months=3), np.nan)
            text += f" The effective federal funds rate averaged {f:.2f}% in {_mon(fm)}"
            if not pd.isna(f3):
                move = "unchanged from" if abs(f - f3) < 0.05 else ("up from" if f > f3 else "down from")
                text += f", {move} {f3:.2f}% three months earlier"
            text += "."
        out.append(text)

    if "unrate" in df and "payems_jobs_k" in df and _last(df["unrate"]) and _last(df["payems_jobs_k"]):
        u, um = _last(df["unrate"])
        j, jm = _last(df["payems_jobs_k"])
        avg3 = df["payems_jobs_k"].dropna().iloc[-3:].mean()
        out.append(
            f"**Labor market.** Unemployment was {u:.1f}% in {_mon(um)}. Payrolls changed by "
            f"{j:+,.0f} thousand in {_mon(jm)} (three-month average {avg3:+,.0f} thousand).")

    if "youth_gap" in df and _last(df["youth_gap"]):
        g, gm = _last(df["youth_gap"])
        base = df.loc["2019-01-01":"2019-12-31", "youth_gap"].mean()
        text = (f"**AI evidence is inconclusive.** The unemployment rate for ages 20-24 was {g:.1f} points "
                f"above the overall rate in {_mon(gm)}")
        if not pd.isna(base):
            word = "close to" if abs(g - base) < 0.3 else ("wider than" if g > base else "narrower than")
            text += f", {word} its 2019 average of {base:.1f}"
        text += ". This gap has many causes and does not isolate AI; it is descriptive only."
        out.append(text)
    return out


def readings_block(df: pd.DataFrame) -> str:
    through = df.dropna(how="all").index.max().strftime("%B %Y")
    parts = [f"_Generated from FRED data through {through}. Each row shows the month it refers to._", "",
             models._md(latest_readings(df).set_index("Measure")), ""]
    parts += [f"{i}. {b}" for i, b in enumerate(findings(df), 1)]
    return "\n".join(parts)


# --------------------------------------------------------------------------- model results
def results_bullets(res: dict, horizons: pd.DataFrame | None = None) -> list[str]:
    """Conclusions from the model output. Thresholds, not judgment, pick the wording."""
    h, s = res["horizon"], res["regression_summary"]
    out = []

    # 1. in-sample regression
    pj = s["joint p-value, wage terms"]
    sig = pj < ALPHA
    text = (f"**In sample, wage growth {'is' if sig else 'is not'} a significant predictor.** In the "
            f"Phillips-curve regression (HAC errors, n={s['n']}) the joint test on the wage terms gives "
            f"p {'= ' if pj >= 0.001 else ''}{_p(pj)}, and adjusted R² goes from "
            f"{s['adj R2 without wages']:.2f} without them to {s['adj R2 with wages']:.2f} with them.")
    reg = res.get("regimes")
    if reg is not None and reg["joint p-value, wage terms"].notna().all():
        ps = reg["joint p-value, wage terms"]
        labels = list(reg.index)
        verdicts = ["significant" if p < ALPHA else "not significant" for p in ps]
        text += (f" Split by period, the wage terms are {verdicts[0]} {labels[0]} (p {'= ' if ps.iloc[0] >= 0.001 else ''}{_p(ps.iloc[0])}) "
                 f"and {verdicts[1]} from {labels[1]} (p {'= ' if ps.iloc[1] >= 0.001 else ''}{_p(ps.iloc[1])}).")
    out.append(text)

    # 2. against the naive benchmark
    sentences, n_sig = [], 0
    for label, tbl in res["scores"].items():
        naive = tbl.loc[models.NAIVE, "RMSE"]
        others = tbl.drop(index=models.NAIVE)
        best = others["RMSE"].idxmin()
        n_sig += int(((others["RMSE vs naive"] < 1) & (others["DM p-value vs naive"] < ALPHA)).sum())
        where = "Over the full backtest" if label == "Full sample" else f"From {label.split()[0]} onward"
        cmp = "lower than" if others.loc[best, "RMSE"] < naive else "higher than"
        sentences.append(f"{where} the most accurate model is \"{best}\" (RMSE {others.loc[best, 'RMSE']:.2f}, "
                         f"{cmp} the naive benchmark's {naive:.2f}).")
    if n_sig:
        title = "Some models beat the naive benchmark."
        dm = f"The Diebold-Mariano test finds a significant improvement over naive in {n_sig} model-period case(s) at the 5% level."
    else:
        lower = any((t.drop(index=models.NAIVE)["RMSE vs naive"] < 1).any() for t in res["scores"].values())
        title = ("No model beats the naive benchmark by a significant margin." if lower
                 else "The naive benchmark is hard to beat.")
        dm = "In no period is any model's advantage over naive statistically significant (Diebold-Mariano, 5% level)."
    out.append(f"**{title}** " + " ".join(sentences) + " " + dm)

    # 3. what wages add
    wv = res.get("wage_value")
    if wv is not None and len(wv):
        sig_rows = wv["Clark-West p-value"] < ALPHA
        lower = wv["ratio (below 1 = wages help)"] < 1
        if sig_rows.all():
            title = "Out of sample, adding wage growth improves the forecasts."
        elif sig_rows.any():
            title = "Out of sample, the evidence that wage growth helps is mixed."
        else:
            title = "Out of sample, wage growth does not significantly improve the forecasts."
        out.append(f"**{title}** Against the smaller models it contains, the ridge model with wage terms has the "
                   f"lower RMSE in {int(lower.sum())} of {len(wv)} comparisons, and the Clark-West test is "
                   f"significant at the 5% level in {int(sig_rows.sum())} of {len(wv)} (see the table of what wage growth adds).")

    # 4. direction
    g = res["granger"]
    fwd, back = (g["wages -> inflation"] < ALPHA).sum(), (g["inflation -> wages"] < ALPHA).sum()
    n = len(g)
    if fwd and back:
        title, tail = "Direction is unclear.", "so this analysis cannot say which one leads"
    elif fwd:
        title, tail = "Wage growth leads inflation in the lead/lag tests.", "which is predictive precedence, not proof of cause"
    elif back:
        title, tail = "Inflation leads wage growth in the lead/lag tests.", "which is predictive precedence, not proof of cause"
    else:
        title, tail = "The lead/lag tests find no clear relationship.", "in either direction"
    out.append(f"**{title}** Granger tests are significant at {fwd} of {n} lags from wages to inflation "
               f"and at {back} of {n} lags from inflation to wages, {tail}. The p-values are not corrected for testing several lags.")

    # 5. horizons
    if horizons is not None and len(horizons):
        col = "vs same model without wages"
        bits = ", ".join(f"{int(hh)} months {row[col]:.2f} (p {'= ' if row['Clark-West p-value'] >= 0.001 else ''}{_p(row['Clark-West p-value'])})"
                         for hh, row in horizons.iterrows())
        out.append(f"**Across horizons.** RMSE of the wage model relative to the same model without wages "
                   f"(below 1 means wages help; Clark-West p-value in brackets): {bits}.")

    out.append(f"**Caveats.** The {h}-month forecast windows overlap, so the {s['n']} monthly observations "
               "contain far fewer independent ones; the 2021-22 surge dominates full-sample errors; the recent "
               "period is short; and all results are predictive, not causal.")
    return out


def results_table(res: dict) -> str:
    """Compact backtest table: one row per model, full sample and recent period side by side."""
    scores = res["scores"]
    labels = list(scores)
    head = ["Model"] + [f"{lab} RMSE (vs naive)" for lab in labels] + ["DM p-value (" + " / ".join(labels) + ")"]
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] * len(head)) + "|"]
    for model in scores[labels[0]].index:
        cells, ps = [model], []
        for lab in labels:
            row = scores[lab].loc[model]
            if model == models.NAIVE:
                cells.append(f"{row['RMSE']:.3f}")
            else:
                cells.append(f"{row['RMSE']:.3f} ({row['RMSE vs naive']:.2f})")
                ps.append(f"{row['DM p-value vs naive']:.2f}")
        cells.append(" / ".join(ps) if ps else "n/a")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def results_block(res: dict, horizons: pd.DataFrame | None = None) -> str:
    h, s = res["horizon"], res["regression_summary"]
    parts = [
        f"_Generated by `python -m scripts.refresh` from FRED data through {res.get('data_through', 'n/a')}; "
        f"the last forecast with a known outcome was made in {s['last month']}._",
        "",
        f"Core PCE inflation {h} months ahead, walk-forward backtest (RMSE in percentage points; "
        "\"vs naive\" below 1 means the model beat the benchmark; p-value is Diebold-Mariano against naive):",
        "",
        results_table(res),
        "",
    ]
    parts += [f"- {b}" for b in results_bullets(res, horizons)]
    wv = res.get("wage_value")
    if wv is not None and len(wv):
        parts += ["", "What wage growth adds: ridge model with wage terms against the smaller models it contains "
                  "(Clark-West test, one-sided, for nested models):", "", models._md(wv)]
    return "\n".join(parts)


# --------------------------------------------------------------------------- README plumbing
def replace_block(text: str, name: str, body: str) -> str:
    """Replace what sits between <!-- AUTO:name:start --> and <!-- AUTO:name:end -->."""
    start, end = f"<!-- AUTO:{name}:start -->", f"<!-- AUTO:{name}:end -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        raise ValueError(f"README is missing the markers for the '{name}' block.")
    return pattern.sub(lambda _: f"{start}\n{body.strip()}\n{end}", text)

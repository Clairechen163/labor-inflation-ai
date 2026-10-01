"""Plotly figures used by the app and README exports."""
import plotly.graph_objects as go


def _line(df, cols, labels, title, ytitle):
    fig = go.Figure()
    for c, lab in zip(cols, labels):
        if c in df:
            fig.add_scatter(x=df.index, y=df[c], name=lab, mode="lines")
    fig.update_layout(title=title, yaxis_title=ytitle, hovermode="x unified",
                      legend=dict(orientation="h", y=-0.2))
    return fig


def inflation_measures(df):
    return _line(df, ["cpi_yoy", "core_cpi_yoy", "pce_yoy", "core_pce_yoy"],
                 ["CPI", "Core CPI", "PCE", "Core PCE"],
                 "Inflation, year over year", "%")


def real_wages(df):
    fig = _line(df, ["wages_yoy", "cpi_yoy", "real_wage_cpi"],
                ["Wage growth", "CPI inflation", "Real wage growth (vs CPI)"],
                "Wage growth vs inflation", "%")
    fig.add_hline(y=0, line_dash="dot")
    return fig


def adp_vs_bls(df):
    fig = go.Figure()
    if "adp_jobs_k" in df:
        fig.add_bar(x=df.index, y=df["adp_jobs_k"], name="ADP")
    if "payems_jobs_k" in df:
        fig.add_bar(x=df.index, y=df["payems_jobs_k"], name="BLS")
    fig.update_layout(title="Monthly job change: ADP vs BLS", yaxis_title="Thousands",
                      barmode="group", hovermode="x unified",
                      legend=dict(orientation="h", y=-0.2))
    return fig


def policy_vs_inflation(df):
    return _line(df, ["fedfunds", "core_pce_yoy", "unrate"],
                 ["Fed funds rate", "Core PCE (YoY)", "Unemployment rate"],
                 "Policy rate, inflation and unemployment", "%")


def youth_gap(df):
    return _line(df, ["unrate_20_24", "unrate", "youth_gap"],
                 ["Unemployment, ages 20-24", "Overall unemployment", "Gap (pp)"],
                 "Young-worker unemployment vs overall (suggestive only)", "%")

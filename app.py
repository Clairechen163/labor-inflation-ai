import os

import pandas as pd
import streamlit as st

from src import charts, models
from src.analysis import derive
from src.fetch import build_dataset

st.set_page_config(page_title="US Labor, Inflation & AI", layout="wide")
st.title("US labor market, inflation, and AI")
st.caption("Data: FRED (St. Louis Fed). ADP series copyright ADP; cited via FRED.")


@st.cache_data(ttl=60 * 60 * 24)
def load(key: str) -> pd.DataFrame:
    return derive(build_dataset(api_key=key))


@st.cache_data(ttl=60 * 60 * 24)
def run_models(df: pd.DataFrame, horizon: int) -> dict:
    return models.run_all(df, horizon=horizon)


try:
    key = st.secrets["FRED_API_KEY"]
except Exception:
    key = None
key = key or os.environ.get("FRED_API_KEY")
if not key:
    st.error("Set FRED_API_KEY as an environment variable or Streamlit secret.")
    st.stop()

df = load(key)
start = st.sidebar.slider("From year", int(df.index.year.min()), int(df.index.year.max()) - 1, 2019)
view = df[df.index.year >= start]

tabs = st.tabs(["Inflation", "Real wages", "ADP vs BLS", "Fed policy", "Young workers / AI", "Model"])
with tabs[0]:
    st.plotly_chart(charts.inflation_measures(view), width="stretch")
    st.markdown("Core PCE is the Fed's preferred gauge; CPI and PCE weight components differently.")
with tabs[1]:
    st.plotly_chart(charts.real_wages(view), width="stretch")
with tabs[2]:
    st.plotly_chart(charts.adp_vs_bls(view[view.index >= "2022-01-01"]), width="stretch")
    st.markdown("ADP and BLS often diverge; treat ADP as a preview, not the final word.")
with tabs[3]:
    st.plotly_chart(charts.policy_vs_inflation(view), width="stretch")
with tabs[4]:
    st.plotly_chart(charts.youth_gap(view), width="stretch")
    st.warning("Suggestive only. Rising youth unemployment has many causes (cycle, rates, "
               "demographics). It is not proof of AI displacement.")
with tabs[5]:
    st.subheader("Does wage growth predict inflation?")
    st.markdown(
        "Two questions on the full sample (not affected by the sidebar year filter): "
        "**(1)** does wage growth help predict core PCE inflation once energy prices, labor-market "
        "slack and inflation expectations are included, and **(2)** do models that use it forecast "
        "better out of sample than simple benchmarks? Results are predictive, not causal."
    )
    horizon = st.select_slider("Forecast horizon (months)", options=[3, 6, 12], value=6)
    try:
        with st.spinner("Fitting models (cached for 24 hours)..."):
            res = run_models(df, horizon)
    except Exception as e:  # missing series, too little data, etc.
        st.error(f"Could not run the models: {e}")
        st.stop()

    s = res["regression_summary"]
    st.markdown("#### 1. Lead/lag tests (Granger, p-values by lag)")
    st.dataframe(res["granger"].style.format("{:.3f}"), width="stretch")
    st.caption("A low p-value means the first series helps predict the second. Series failing a "
               "stationarity test are first-differenced first. Predictive precedence, not causation.")

    st.markdown("#### 2. Phillips-curve regression (HAC standard errors)")
    st.dataframe(res["regression"].style.format("{:.3f}"), width="stretch")
    st.caption(f"Sample {s['first month']} to {s['last month']} (n={s['n']}). Adjusted R² "
               f"{s['adj R2 without wages']:.3f} without wage terms vs {s['adj R2 with wages']:.3f} with. "
               f"Joint test that both wage terms are zero: p = {s['joint p-value, wage terms']:.3f}.")
    st.markdown("Stability across regimes")
    st.dataframe(res["regimes"].style.format("{:.3f}", na_rep="n/a"), width="stretch")

    st.markdown("#### 3. Out-of-sample backtest")
    st.plotly_chart(charts.backtest_chart(res["predictions"], horizon), width="stretch")
    for label, tbl in res["scores"].items():
        st.markdown(f"**{label}**")
        st.dataframe(tbl.style.format("{:.3f}", na_rep=""), width="stretch")
    st.caption("RMSE vs naive below 1 means the model beat the benchmark. Models are refit each month "
               "using only data whose outcomes were already known (no look-ahead). The Diebold-Mariano "
               "p-value tests whether accuracy differs from the naive benchmark.")

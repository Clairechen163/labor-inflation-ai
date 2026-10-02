import os

import pandas as pd
import streamlit as st

from src import charts
from src.analysis import derive
from src.fetch import build_dataset

st.set_page_config(page_title="US Labor, Inflation & AI", layout="wide")
st.title("US labor market, inflation, and AI")
st.caption("Data: FRED (St. Louis Fed). ADP series copyright ADP; cited via FRED.")


@st.cache_data(ttl=60 * 60 * 24)
def load(key: str) -> pd.DataFrame:
    return derive(build_dataset(api_key=key))


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

tabs = st.tabs(["Inflation", "Real wages", "ADP vs BLS", "Fed policy", "Young workers / AI"])
with tabs[0]:
    st.plotly_chart(charts.inflation_measures(view), use_container_width=True)
    st.markdown("Core PCE is the Fed's preferred gauge; CPI and PCE weight components differently.")
with tabs[1]:
    st.plotly_chart(charts.real_wages(view), use_container_width=True)
with tabs[2]:
    st.plotly_chart(charts.adp_vs_bls(view[view.index >= "2022-01-01"]), use_container_width=True)
    st.markdown("ADP and BLS often diverge; treat ADP as a preview, not the final word.")
with tabs[3]:
    st.plotly_chart(charts.policy_vs_inflation(view), use_container_width=True)
with tabs[4]:
    st.plotly_chart(charts.youth_gap(view), use_container_width=True)
    st.warning("Suggestive only. Rising youth unemployment has many causes (cycle, rates, "
               "demographics). It is not proof of AI displacement.")

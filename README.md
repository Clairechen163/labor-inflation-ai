# ![CI]([https://github.com/Clairechen163/labor-inflation-ai/actions/workflows/ci.yml/badge.svg?branch=main)[](https://github.com/Clairechen163/labor-inflation-ai/actions/workflows/ci.yml)](https://github.com/Clairechen163/labor-inflation-ai/actions/workflows/ci.yml/badge.svg?branch=main)]([https://github.com/Clairechen163/labor-inflation-ai/actions/workflows/ci.yml](https://github.com/Clairechen163/labor-inflation-ai/actions/workflows/ci.yml)))

# US Labor, Inflation & AI

An interactive dashboard asking: **is wage growth driving US inflation, and is there early evidence that AI is affecting hiring?**

Data comes from the [FRED API](https://fred.stlouisfed.org/docs/api/) (St. Louis Fed), refreshed daily in the app.

> Add a screenshot here: `docs/dashboard.png`



## Key findings (as of September 2026)

Update these from the dashboard before publishing.

1. **Inflation is energy-led, not wage-led.** August CPI was 3.4% YoY with energy up 16.3%, while ADP base pay rose 3.2%. Wages are slightly trailing prices.
2. **CPI and PCE gap narrowed.** August headline PCE (3.4%) matched headline CPI (3.4%). Core PCE (3.0%) still ran above core CPI (2.4%). Different weights may explain part of this; see Methods.
3. **The Fed is tightening into weak hiring.** It raised rates to 3.75-4.00% on Sept 16 while ADP payrolls added just 38,000 jobs in August.
4. **AI evidence is narrow.** Aggregate unemployment shows no clear AI effect; the signal, if any, is in entry-level hiring. This is suggestive, not proven.



## What changed this month (September 30 release)

- **August PCE:** headline +0.3% m/m and 3.4% YoY (July: 3.7%); core +0.2% m/m and 3.0% YoY (July: 3.3%). Core came in below the ~3.4% forecast.
- **Real disposable income was flat (0.0%)** even as spending rose 0.9%, so consumers are spending faster than income is growing.
- The release included BEA's annual update, which can revise earlier months.
- Source: BEA, Personal Income and Outlays, August 2026.



## Run it

```bash
git clone https://github.com/Clairechen163/labor-inflation-ai.git && cd labor-inflation-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your free FRED API key
export FRED_API_KEY=...     # or set in .streamlit/secrets.toml
streamlit run app.py
pytest                      # unit tests for derived measures
```



## Structure

```
app.py            Streamlit dashboard
src/fetch.py      FRED API pulls -> monthly table
src/analysis.py   YoY inflation, job changes, real wages, youth gap
src/charts.py     Plotly figures
tests/            pytest checks on the calculations
.github/          CI + monthly live-fetch smoke test
```



## Methods

- Inflation = 12-month % change in the CPI/PCE indexes.
- Real wage growth = wage growth YoY minus inflation YoY (percentage-point difference).
- ADP monthly change = first difference of the ADP level series; BLS from PAYEMS.
- Youth gap = unemployment rate ages 20-24 minus overall rate.



## Limitations

- ADP and BLS are different surveys and often diverge.
- The youth-unemployment gap has many causes and does not isolate AI. Treat it as a signal to watch.
- Wage series here is average hourly earnings, which differs from ADP's base pay measure.
- Verify each FRED series ID (in `src/fetch.py`) before trusting a chart.

 - Some CPI observations are missing around late 2025 because the source agency did not publish them (see FRED for details). Charts show a gap or a straight line across that period, and year-over-year figures that depend on the missing month may be unavailable.



## Data and licensing

Data via FRED; ADP data is copyrighted by ADP and cited here through FRED. Raw data files are not committed to this repository.
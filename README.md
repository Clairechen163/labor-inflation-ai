[![CI](https://github.com/Clairechen163/labor-inflation-ai/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Clairechen163/labor-inflation-ai/actions/workflows/ci.yml) [![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://labor-inflation-ai.streamlit.app)

# US Labor, Inflation & AI

**Live app:** https://labor-inflation-ai.streamlit.app

Tests whether wage growth is driving US inflation and whether AI shows up in hiring data. **Finding:** inflation is energy-led, and the AI evidence is inconclusive.

Data comes from the [FRED API](https://fred.stlouisfed.org/docs/api/) (St. Louis Fed), refreshed daily in the app.

![Dashboard](docs/dashboard.png)

## Key findings (as of September 2026)

1. **Inflation is energy-led, not wage-led.** August CPI was 3.4% with energy up 16.3%; average hourly earnings grew about 3.1%, so real wages are slightly negative (about -0.3%).
2. **CPI and PCE gap narrowed.** Headline PCE and CPI were both 3.4% in August, but core PCE (3.0%) still exceeds core CPI (2.4%).
3. **The Fed is tightening because of inflation, not weak labor demand.** It raised rates to 3.75-4.00% on Sept 16 with unemployment at 4.1% in August.
4. **AI evidence is inconclusive.** Unemployment for ages 20-24 rose relative to the overall rate in 2024-2025 but has since narrowed to roughly its 2019 level.

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

On Windows (PowerShell), activate with `.venv\Scripts\Activate.ps1` and set the key with `$env:FRED_API_KEY = "your_key"`.

## Structure

```
app.py            Streamlit dashboard
src/fetch.py      FRED API pulls -> monthly table
src/analysis.py   YoY inflation, job changes, real wages, youth gap
src/charts.py     Plotly figures
tests/            pytest checks on the calculations
pytest.ini        pytest import-path config
docs/             dashboard screenshot
.github/          CI + monthly live-fetch smoke test
LICENSE           MIT license
```

## Methods

- Inflation = 12-month % change in the CPI/PCE indexes.
- Real wage growth = wage growth YoY minus inflation YoY (percentage-point difference).
- ADP monthly change = first difference of the ADP level series; BLS from PAYEMS.
- Youth gap = unemployment rate ages 20-24 minus overall rate.

## Limitations

- ADP and BLS monthly job changes often differ in size and occasionally in sign (for example, early 2024 and February 2026), so ADP is best read as a rough preview of the official data.
- The youth-unemployment gap has many causes and does not isolate AI. Treat it as a signal to watch.
- Wage series here is average hourly earnings, which differs from ADP's base pay measure.
- Series IDs are listed in `src/fetch.py`. If FRED renames or retires a series, that chart will be empty until the ID is updated.
- October 2025 is missing from the CPI and household-survey series (including the unemployment rates) because the federal government shutdown prevented BLS from collecting the data, and it cannot be collected retroactively. Charts show a gap there, and year-over-year figures that use October 2025 as a base (such as October 2026) will also be missing. Wage data come from a different survey and are not affected.
- The 20-24 unemployment rate counts only people actively looking for work, and includes recent graduates and students entering the labor force. It does not measure hiring in AI-exposed occupations, which is where studies looking for AI effects focus (for example, Stanford's analysis of payroll data by occupation).
- Average hourly earnings jumped in spring 2020 because job losses were concentrated among low-wage workers, not because individual wages rose. Real wage growth here is a simple percentage-point difference (wage growth minus inflation), an approximation.

## Roadmap

- Add occupation-level AI-exposure and entry-level job postings data, since youth unemployment is only a rough proxy.
- Offer a downloadable CSV of the derived series from the app.
- Automate the monthly refresh of the findings above after each CPI, PCE and jobs release.

<details>
<summary><strong>What changed this month (September 30 release)</strong></summary>

- **August PCE:** headline +0.3% m/m and 3.4% YoY (July: 3.7%); core +0.2% m/m and 3.0% YoY (July: 3.3%). Core came in below the ~3.4% forecast.
- **ADP (Sept 30):** private payrolls +90,000 in September (August revised to +36,000). Base pay +3.2% YoY.
- **Real disposable income was flat (0.0%)** even as spending rose 0.9%, so consumers are spending faster than income is growing.
- The release included BEA's annual update, which can revise earlier months.
- Source: BEA, Personal Income and Outlays, August 2026.

</details>

## Sources

- FRED, Federal Reserve Bank of St. Louis (series IDs in `src/fetch.py`)
- U.S. Bureau of Labor Statistics: CPI and Employment Situation reports
- U.S. Bureau of Economic Analysis: Personal Income and Outlays (PCE)
- ADP National Employment Report

## Data and licensing

Code is released under the MIT License (see `LICENSE`). Data via FRED; ADP data is copyrighted by ADP and cited here through FRED. Raw data files are not committed to this repository.

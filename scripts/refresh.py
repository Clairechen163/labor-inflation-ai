"""Refresh everything that depends on the data, from one FRED pull:

    reports/results.md, reports/backtest_predictions.csv   model output
    README.md                                              the two AUTO blocks
    docs/dashboard.png                                     the chart at the top of the README

Run by the scheduled GitHub Action (.github/workflows/refresh-image.yml) or locally:
    python -m scripts.refresh
Nothing here contains today's date, so the files only change when the data change.
"""
from src import models, summary
from src.analysis import derive
from src.fetch import build_dataset

README = "README.md"


def update_readme(df, res, horizons, path=README):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    text = summary.replace_block(text, "results", summary.results_block(res, horizons))
    text = summary.replace_block(text, "readings", summary.readings_block(df))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def main():
    from scripts.make_dashboard_image import make_figure

    df = derive(build_dataset())
    res = models.run_all(df)
    horizons = models.horizon_robustness(df)
    models.write_report(res, "reports/results.md", horizons)
    res["predictions"].to_csv("reports/backtest_predictions.csv", lineterminator="\n")
    update_readme(df, res, horizons)
    fig = make_figure(df, res["predictions"])
    fig.savefig("docs/dashboard.png", dpi=130, metadata={"Software": None})
    print(f"Refreshed results, README and image (data through {res['data_through']}).")


if __name__ == "__main__":
    main()

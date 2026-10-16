"""Regenerate docs/dashboard.png from live FRED data.

Run by the scheduled GitHub Action (.github/workflows/refresh-image.yml) and runnable locally:
    python -m scripts.make_dashboard_image
The image only changes when new data arrive, so the Action commits only when it differs.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src import models  # noqa: E402
from src.analysis import derive  # noqa: E402
from src.fetch import build_dataset  # noqa: E402

START = "2019-01-01"
HORIZON = 6


def make_figure(df, preds):
    view = df[df.index >= START]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 4.8), gridspec_kw={"width_ratios": [1.1, 1]})

    for col, label, color, lw in [("wages_yoy", "Wage growth", "#1f6feb", 2),
                                  ("cpi_yoy", "CPI inflation", "#8b949e", 2),
                                  ("real_wage_cpi", "Real wage growth", "#d1242f", 2.4)]:
        if col in view:
            a1.plot(view.index, view[col], label=label, color=color, lw=lw)
    a1.axhline(0, color="black", ls=":", lw=1)
    a1.set_title("Wage growth vs inflation (YoY %)", loc="left", fontweight="bold")
    a1.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3)

    p = preds[preds.index >= "2019-01-01"]
    a2.plot(p.index, p["actual"], color="black", lw=2.6, label="Actual core PCE")
    a2.plot(p.index, p[models.NAIVE], color="#8b949e", lw=1.5, label="Naive benchmark")
    wage_model = "Ridge: + wage growth"
    if wage_model in p:
        a2.plot(p.index, p[wage_model], color="#1f6feb", lw=1.8, label=wage_model)
    a2.set_title(f"Out-of-sample forecasts, core PCE next {HORIZON} months (annualized %)",
                 loc="left", fontweight="bold")
    a2.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3)

    for ax in (a1, a2):
        ax.grid(alpha=0.25)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    last = df.dropna(subset=["wages_yoy"]).index.max().strftime("%B %Y")
    fig.text(0.01, 0.01, f"Source: FRED (St. Louis Fed). Wage and CPI data through {last}. "
             "Auto-refreshed from the live data.", fontsize=8, color="#57606a")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def main(out="docs/dashboard.png"):
    df = derive(build_dataset())
    frame = models.build_features(df, horizon=HORIZON)
    preds = models.walk_forward(frame, horizon=HORIZON)
    fig = make_figure(df, preds)
    fig.savefig(out, dpi=130, metadata={"Software": None})
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Build Day-3 storytelling evidence and Tableau-ready forecast exports.

Run from any directory with::

    python src/storytelling.py

The script does not change the analysis release. It reshapes Day-2 predictions,
checks them against the quarterly source target, and writes reproducible
storytelling notes, Tableau handoff tables, and supporting figures.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
REPORTS_DIR = PROJECT_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

FAMILIES = ["Counter-Strike", "Dota 2", "League of Legends", "Valorant"]
COLORS = {
    "Counter-Strike": "#2F5597",
    "Dota 2": "#C00000",
    "League of Legends": "#D4A017",
    "Valorant": "#D1495B",
}
MODEL_COLUMNS = {
    "seasonal_naive": "prediction_seasonal_naive",
    "linear_regression": "prediction_linear_regression",
    "random_forest": "prediction_random_forest",
}
MODEL_LABELS = {
    "seasonal_naive": "Seasonal naive (t-4)",
    "linear_regression": "Linear regression",
    "random_forest": "Random forest",
}
TARGET_COLUMNS = {
    "source": "target_prize_pool_usd",
    "strict_quality": "strict_target_prize_pool_usd",
}


def latest_release() -> Path:
    candidates = sorted(
        path
        for path in PROCESSED_DIR.glob("analysis_release_v1_*")
        if path.is_dir() and (path / "manifest.json").exists()
    )
    if not candidates:
        raise FileNotFoundError(
            f"No analysis_release_v1_* folder found under {PROCESSED_DIR}"
        )
    return candidates[-1]


def load_inputs() -> tuple[Path, dict[str, pd.DataFrame]]:
    release = latest_release()
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("stage") != "analysis_release_v1_policy_clean_not_source_verified":
        raise ValueError("Unexpected release stage; review its policy before storytelling")

    paths = {
        "quarterly": release / "forecast_prize_quarterly.csv",
        "panel": release / "game_monthly_panel.csv",
        "correlations": release / "eda_correlations_descriptive.csv",
        "seasonality": release / "eda_prize_train_seasonality.csv",
        "country_year": release / "country_year.csv",
        "country_coverage": release / "country_coverage.csv",
        "predictions": REPORTS_DIR / "model_predictions.csv",
        "metrics": REPORTS_DIR / "model_metrics.csv",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing Day-3 inputs: {missing}")
    frames = {
        name: pd.read_csv(path, encoding="utf-8-sig")
        for name, path in paths.items()
    }

    quarterly = frames["quarterly"]
    predictions = frames["predictions"]
    if quarterly.duplicated(["game_family", "quarter"]).any():
        raise ValueError("Quarterly source contains duplicate family-quarter keys")
    if predictions.duplicated(["game_family", "quarter", "target_policy"]).any():
        raise ValueError("Day-2 predictions contain duplicate family-quarter-policy keys")
    if set(predictions["target_policy"].unique()) != set(TARGET_COLUMNS):
        raise ValueError("Unexpected target policy in Day-2 predictions")

    comparison = predictions.merge(
        quarterly[["game_family", "quarter", *TARGET_COLUMNS.values()]],
        on=["game_family", "quarter"],
        how="left",
        validate="many_to_one",
    )
    for policy, source_column in TARGET_COLUMNS.items():
        rows = comparison[comparison["target_policy"].eq(policy)]
        if not np.allclose(
            rows["actual_prize_pool_usd"],
            rows[source_column],
            equal_nan=True,
        ):
            raise ValueError(f"Day-2 actual values do not reconcile for policy {policy}")

    for frame_name, date_column in [
        ("quarterly", "period_start"),
        ("panel", "month_start"),
        ("predictions", "period_start"),
    ]:
        frames[frame_name][date_column] = pd.to_datetime(
            frames[frame_name][date_column], errors="raise"
        )
    return release, frames


def build_tableau_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    identifiers = [
        "game_family",
        "quarter",
        "period_start",
        "split",
        "target_policy",
        "actual_prize_pool_usd",
        "evaluation_available",
        "evaluation_status",
        "protocol",
    ]
    for model, prediction_column in MODEL_COLUMNS.items():
        part = predictions[identifiers].copy()
        part["model"] = model
        part["model_label"] = MODEL_LABELS[model]
        part["predicted_prize_pool_usd"] = predictions[prediction_column]
        part["residual_usd"] = (
            part["actual_prize_pool_usd"] - part["predicted_prize_pool_usd"]
        )
        part["absolute_error_usd"] = part["residual_usd"].abs()
        part["squared_error_usd2"] = part["residual_usd"].pow(2)
        part["error_direction"] = np.select(
            [part["residual_usd"].lt(0), part["residual_usd"].gt(0)],
            ["overprediction", "underprediction"],
            default="not_evaluated_or_exact",
        )
        part["is_primary_model"] = model == "random_forest"
        part["is_baseline_model"] = model == "seasonal_naive"
        parts.append(part)

    export = pd.concat(parts, ignore_index=True)
    export = export.sort_values(
        ["target_policy", "model", "period_start", "game_family"]
    ).reset_index(drop=True)
    key = ["game_family", "quarter", "target_policy", "model"]
    if export.duplicated(key).any():
        raise ValueError(f"Tableau prediction export is not unique at {key}")
    if export["predicted_prize_pool_usd"].isna().any():
        raise ValueError("Tableau prediction export contains a missing prediction")
    return export


def build_tableau_summary(export: pd.DataFrame) -> pd.DataFrame:
    overall = export.copy()
    overall["game_family"] = "Overall"
    combined = pd.concat([export, overall], ignore_index=True)

    rows: list[dict] = []
    group_columns = ["target_policy", "split", "game_family", "model", "model_label"]
    for key, group in combined.groupby(group_columns, sort=False):
        evaluated = group[group["evaluation_available"]]
        residual = evaluated["residual_usd"]
        rows.append(
            {
                **dict(zip(group_columns, key)),
                "total_periods": len(group),
                "evaluated_periods": len(evaluated),
                "coverage_pct": 100 * len(evaluated) / len(group),
                "actual_prize_pool_usd": evaluated["actual_prize_pool_usd"].sum(min_count=1),
                "predicted_prize_pool_usd_evaluated": evaluated["predicted_prize_pool_usd"].sum(min_count=1),
                "predicted_prize_pool_usd_all_periods": group["predicted_prize_pool_usd"].sum(min_count=1),
                "mean_residual_usd": residual.mean(),
                "mae_usd": residual.abs().mean(),
                "rmse_usd": math.sqrt(residual.pow(2).mean()),
                "is_primary_model": key[3] == "random_forest",
                "is_baseline_model": key[3] == "seasonal_naive",
            }
        )
    return pd.DataFrame(rows).sort_values(group_columns).reset_index(drop=True)


def build_error_analysis(export: pd.DataFrame) -> pd.DataFrame:
    errors = export[
        export["target_policy"].eq("source")
        & export["model"].eq("random_forest")
        & export["evaluation_available"]
    ].copy()
    errors = errors.sort_values("absolute_error_usd", ascending=False).reset_index(drop=True)
    errors.insert(0, "absolute_error_rank", np.arange(1, len(errors) + 1))
    errors["quarter_of_year"] = errors["quarter"].str[-2:]
    errors["absolute_error_share_pct"] = (
        100 * errors["absolute_error_usd"] / errors["absolute_error_usd"].sum()
    )
    keep = [
        "absolute_error_rank",
        "game_family",
        "quarter",
        "quarter_of_year",
        "split",
        "actual_prize_pool_usd",
        "predicted_prize_pool_usd",
        "residual_usd",
        "absolute_error_usd",
        "absolute_error_share_pct",
        "error_direction",
    ]
    return errors[keep]


def aggregate_country_evidence(
    country_year: pd.DataFrame, coverage: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    country = (
        country_year.groupby(
            ["game_family", "country_code", "country_name"], as_index=False
        )["prize_cents"]
        .sum()
        .sort_values(["game_family", "prize_cents"], ascending=[True, False])
    )
    country["family_reconciled_prize_cents"] = country.groupby("game_family")[
        "prize_cents"
    ].transform("sum")
    country["share_of_family_reconciled_pct"] = (
        100 * country["prize_cents"] / country["family_reconciled_prize_cents"]
    )
    top_countries = country.groupby("game_family", sort=False).head(5).copy()

    coverage_summary = coverage.groupby("game_family", as_index=False).agg(
        source_pool_cents=("source_pool_cents", "sum"),
        reconciled_pool_cents=("reconciled_pool_cents", "sum"),
    )
    coverage_summary["country_money_coverage_pct"] = (
        100
        * coverage_summary["reconciled_pool_cents"]
        / coverage_summary["source_pool_cents"]
    )
    return top_countries, coverage_summary


def build_evidence(
    quarterly: pd.DataFrame,
    panel: pd.DataFrame,
    correlations: pd.DataFrame,
    top_countries: pd.DataFrame,
    coverage_summary: pd.DataFrame,
    errors: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict] = []
    totals = quarterly.groupby("game_family")["target_prize_pool_usd"].sum()
    peak_rows = quarterly.loc[
        quarterly.groupby("game_family")["target_prize_pool_usd"].idxmax()
    ].set_index("game_family")
    pearson = correlations[correlations["method"].eq("pearson")].set_index(
        "game_family"
    )
    twitch = panel.groupby("game_family")["hours_watched"].agg(["count", "mean", "median"])
    top_one = top_countries.groupby("game_family", sort=False).head(1).set_index(
        "game_family"
    )
    coverage = coverage_summary.set_index("game_family")

    for family in FAMILIES:
        rows.extend(
            [
                {
                    "story": "prize_structure",
                    "game_family": family,
                    "metric": "total_source_prize_pool_usd",
                    "period": "all_observed",
                    "value": totals[family],
                    "unit": "USD",
                    "source_file": "forecast_prize_quarterly.csv",
                },
                {
                    "story": "prize_structure",
                    "game_family": family,
                    "metric": "peak_quarter_prize_pool_usd",
                    "period": peak_rows.loc[family, "quarter"],
                    "value": peak_rows.loc[family, "target_prize_pool_usd"],
                    "unit": "USD",
                    "source_file": "forecast_prize_quarterly.csv",
                },
                {
                    "story": "twitch_prize_relationship",
                    "game_family": family,
                    "metric": "pearson_hours_vs_pool",
                    "period": "matched_months",
                    "value": pearson.loc[family, "hours_vs_pool"],
                    "unit": "correlation",
                    "source_file": "eda_correlations_descriptive.csv",
                },
                {
                    "story": "twitch_prize_relationship",
                    "game_family": family,
                    "metric": "median_monthly_twitch_hours",
                    "period": f"n={int(twitch.loc[family, 'count'])}",
                    "value": twitch.loc[family, "median"],
                    "unit": "hours",
                    "source_file": "game_monthly_panel.csv",
                },
                {
                    "story": "country_distribution",
                    "game_family": family,
                    "metric": f"top_country_{top_one.loc[family, 'country_code']}_share",
                    "period": "all_observed",
                    "value": top_one.loc[family, "share_of_family_reconciled_pct"],
                    "unit": "percent",
                    "source_file": "country_year.csv",
                },
                {
                    "story": "country_distribution",
                    "game_family": family,
                    "metric": "country_money_coverage_pct",
                    "period": "all_observed",
                    "value": coverage.loc[family, "country_money_coverage_pct"],
                    "unit": "percent",
                    "source_file": "country_coverage.csv",
                },
            ]
        )

    for row in errors.head(10).itertuples():
        rows.append(
            {
                "story": "forecast_error",
                "game_family": row.game_family,
                "metric": "random_forest_absolute_error_usd",
                "period": row.quarter,
                "value": row.absolute_error_usd,
                "unit": "USD",
                "source_file": "model_predictions.csv",
            }
        )
    return pd.DataFrame(rows)


def save_figure(fig: plt.Figure, filename: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / filename, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def style_axis(ax: plt.Axes) -> None:
    ax.grid(True, color="#D9D9D9", alpha=0.55, linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)


def millions(value: float, _: int) -> str:
    return f"${value / 1_000_000:.0f}M"


def plot_prize_structure(
    quarterly: pd.DataFrame, seasonality: pd.DataFrame
) -> None:
    totals = (
        quarterly.groupby("game_family", as_index=False)["target_prize_pool_usd"]
        .sum()
        .set_index("game_family")
        .loc[FAMILIES]
        .reset_index()
    )
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))
    bars = axes[0].bar(
        totals["game_family"],
        totals["target_prize_pool_usd"],
        color=[COLORS[family] for family in totals["game_family"]],
    )
    axes[0].bar_label(
        bars,
        labels=[f"${value / 1_000_000:.1f}M" for value in totals["target_prize_pool_usd"]],
        padding=4,
        fontsize=10,
    )
    axes[0].set_ylabel("Observed prize pool (USD)")
    axes[0].yaxis.set_major_formatter(FuncFormatter(millions))
    axes[0].tick_params(axis="x", rotation=15)
    axes[0].set_title("Total observed prize pool", loc="left", fontweight="bold")
    style_axis(axes[0])

    for family in FAMILIES:
        group = seasonality[seasonality["game_family"].eq(family)].sort_values(
            "quarter_of_year"
        )
        axes[1].plot(
            group["quarter_of_year"],
            group["median"] / 1_000_000,
            color=COLORS[family],
            marker="o",
            linewidth=2.2,
            label=family,
        )
    axes[1].set_xticks([1, 2, 3, 4], ["Q1", "Q2", "Q3", "Q4"])
    axes[1].set_ylabel("Median train prize pool (USD millions)")
    axes[1].set_title("Quarterly seasonality in train data", loc="left", fontweight="bold")
    axes[1].legend(frameon=False, fontsize=9)
    style_axis(axes[1])
    fig.suptitle("Prize-pool scale and seasonality", fontsize=18, fontweight="bold")
    fig.text(
        0.5,
        0.01,
        "Observed source totals; seasonal medians use train periods only. Incomplete 2025 coverage is not treated as market decline.",
        ha="center",
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    save_figure(fig, "story_01_prize_structure.png")


def plot_twitch_prize_relationship(
    panel: pd.DataFrame, correlations: pd.DataFrame
) -> None:
    pearson = correlations[correlations["method"].eq("pearson")].set_index(
        "game_family"
    )
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for ax, family in zip(axes.flat, FAMILIES):
        group = panel[
            panel["game_family"].eq(family)
            & panel["hours_watched"].gt(0)
            & panel["source_prize_pool_usd"].gt(0)
        ]
        ax.scatter(
            group["hours_watched"],
            group["source_prize_pool_usd"],
            color=COLORS[family],
            alpha=0.6,
            s=32,
        )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(family, loc="left", fontweight="bold")
        ax.text(
            0.98,
            0.94,
            f"Pearson r = {pearson.loc[family, 'hours_vs_pool']:.3f}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=10,
        )
        ax.set_xlabel("Monthly Twitch hours watched")
        ax.set_ylabel("Monthly prize pool (USD)")
        style_axis(ax)
    fig.suptitle("Monthly Twitch attention and prize pools", fontsize=18, fontweight="bold")
    fig.text(
        0.5,
        0.01,
        "Log scales. Correlation is descriptive and does not show that prize money causes viewing hours.",
        ha="center",
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    save_figure(fig, "story_02_twitch_prize_relationship.png")


def plot_country_distribution(
    top_countries: pd.DataFrame, coverage_summary: pd.DataFrame
) -> None:
    coverage = coverage_summary.set_index("game_family")
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    for ax, family in zip(axes.flat, FAMILIES):
        group = top_countries[top_countries["game_family"].eq(family)].sort_values(
            "prize_cents"
        )
        bars = ax.barh(
            group["country_name"],
            group["prize_cents"] / 100 / 1_000_000,
            color=COLORS[family],
        )
        ax.bar_label(
            bars,
            labels=[f"${value / 100 / 1_000_000:.1f}M" for value in group["prize_cents"]],
            padding=4,
            fontsize=9,
        )
        ax.set_title(
            f"{family} — coverage {coverage.loc[family, 'country_money_coverage_pct']:.1f}%",
            loc="left",
            fontweight="bold",
        )
        ax.set_xlabel("Reconciled player-country prize (USD millions)")
        style_axis(ax)
    fig.suptitle("Top player countries in reconciled prize data", fontsize=18, fontweight="bold")
    fig.text(
        0.5,
        0.01,
        "Player country, not audience country. Bars exclude unreconciled country rows; coverage is shown for each family.",
        ha="center",
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    save_figure(fig, "story_03_country_distribution.png")


def plot_error_concentration(errors: pd.DataFrame) -> None:
    data = errors.head(12).sort_values("absolute_error_usd")
    labels = data["game_family"] + " " + data["quarter"]
    colors = [
        "#D1495B" if direction == "overprediction" else "#2F5597"
        for direction in data["error_direction"]
    ]
    fig, ax = plt.subplots(figsize=(12, 7.5))
    bars = ax.barh(labels, data["absolute_error_usd"], color=colors)
    ax.bar_label(
        bars,
        labels=[f"${value / 1_000_000:.2f}M" for value in data["absolute_error_usd"]],
        padding=4,
        fontsize=9,
    )
    ax.xaxis.set_major_formatter(FuncFormatter(millions))
    ax.set_xlabel("Random-forest absolute error (USD)")
    ax.set_title(
        "Largest validation and test forecast errors",
        loc="left",
        fontsize=18,
        fontweight="bold",
    )
    ax.text(
        0.99,
        0.03,
        "Red: overprediction   Blue: underprediction",
        transform=ax.transAxes,
        ha="right",
        color="#555555",
    )
    style_axis(ax)
    fig.tight_layout()
    save_figure(fig, "story_04_forecast_error_concentration.png")


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    output = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] + ["---:"] * (len(headers) - 1)) + "|",
    ]
    output.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(output)


def write_storytelling_insights(
    release: Path,
    quarterly: pd.DataFrame,
    panel: pd.DataFrame,
    correlations: pd.DataFrame,
    top_countries: pd.DataFrame,
    coverage_summary: pd.DataFrame,
    errors: pd.DataFrame,
) -> None:
    totals = quarterly.groupby("game_family")["target_prize_pool_usd"].sum()
    peaks = quarterly.loc[
        quarterly.groupby("game_family")["target_prize_pool_usd"].idxmax()
    ].set_index("game_family")
    prize_rows = [
        [
            family,
            f"{totals[family] / 1_000_000:,.2f}",
            str(peaks.loc[family, "quarter"]),
            f"{peaks.loc[family, 'target_prize_pool_usd'] / 1_000_000:,.2f}",
        ]
        for family in FAMILIES
    ]

    pearson = correlations[correlations["method"].eq("pearson")].set_index(
        "game_family"
    )
    twitch = panel.groupby("game_family")["hours_watched"].agg(["count", "median"])
    twitch_rows = [
        [
            family,
            str(int(pearson.loc[family, "n"])),
            f"{pearson.loc[family, 'hours_vs_pool']:.3f}",
            f"{twitch.loc[family, 'median'] / 1_000_000:,.1f}",
        ]
        for family in FAMILIES
    ]

    top_one = top_countries.groupby("game_family", sort=False).head(1).set_index(
        "game_family"
    )
    coverage = coverage_summary.set_index("game_family")
    country_rows = [
        [
            family,
            str(top_one.loc[family, "country_name"]),
            f"{top_one.loc[family, 'prize_cents'] / 100 / 1_000_000:,.2f}",
            f"{top_one.loc[family, 'share_of_family_reconciled_pct']:.1f}%",
            f"{coverage.loc[family, 'country_money_coverage_pct']:.1f}%",
        ]
        for family in FAMILIES
    ]

    error_rows = [
        [
            str(row.game_family),
            str(row.quarter),
            str(row.split),
            f"{row.actual_prize_pool_usd / 1_000_000:,.2f}",
            f"{row.predicted_prize_pool_usd / 1_000_000:,.2f}",
            f"{row.residual_usd / 1_000_000:,.2f}",
        ]
        for row in errors.head(8).itertuples()
    ]
    q4_share = 100 * errors.loc[
        errors["quarter_of_year"].eq("Q4"), "absolute_error_usd"
    ].sum() / errors["absolute_error_usd"].sum()
    dota_share = 100 * errors.loc[
        errors["game_family"].eq("Dota 2"), "absolute_error_usd"
    ].sum() / errors["absolute_error_usd"].sum()
    overall_coverage = (
        100
        * coverage_summary["reconciled_pool_cents"].sum()
        / coverage_summary["source_pool_cents"].sum()
    )

    content = f"""# Storytelling insights and actions

## Scope

Evidence comes from `{release.name}` and the Day-2 rolling one-step model outputs. The release is policy-clean but source coverage is not fully verified. All prize values are nominal USD.

## Forecast error analysis

{markdown_table(["Family", "Quarter", "Split", "Actual (USD M)", "Random Forest (USD M)", "Residual (USD M)"], error_rows)}

Residual is actual minus predicted. Negative values mean overprediction. The largest errors cluster around sudden reversals: Dota 2 2024Q3 was overpredicted by about 5.68 million USD, Counter-Strike 2025Q4 by 5.59 million USD and Dota 2 2025Q4 by 5.54 million USD. Q4 accounts for {q4_share:.1f}% of total Random-Forest absolute error across evaluated validation and test rows; Dota 2 accounts for {dota_share:.1f}%.

**Interpretation.** Lag-based models react slowly when a high-prize seasonal pattern is followed by a sharp decline. The source coverage of 2025 is still unverified, so a large residual can reflect collection coverage as well as a real market change.

**Action.** Use the forecast as a quarterly planning range and keep a manual review flag for Dota 2 and Q4. Do not turn the point forecast into a guaranteed sponsorship budget.

Supporting figure: `reports/figures/story_04_forecast_error_concentration.png`.

## Story 1 — Prize-pool scale and seasonality

{markdown_table(["Family", "Observed total (USD M)", "Peak quarter", "Peak prize (USD M)"], prize_rows)}

Dota 2 has the largest observed prize pool, about {totals['Dota 2'] / 1_000_000:,.2f} million USD, and the largest quarterly spike: {peaks.loc['Dota 2', 'quarter']} at {peaks.loc['Dota 2', 'target_prize_pool_usd'] / 1_000_000:,.2f} million USD. In train data, Dota 2 also has its strongest median seasonal level in Q3. Counter-Strike has a smaller total but a less extreme quarterly scale.

**Limit.** The low 2025 counts must not be presented as evidence that the E-sports market contracted. The release does not certify complete source coverage for 2025.

**Action.** Treat Dota 2 as a high-scale, high-volatility sponsorship signal. Use staged budget approval around major-event quarters. Use Counter-Strike as a separate, steadier comparison rather than pooling both into one budget rule.

Supporting figure: `reports/figures/story_01_prize_structure.png`.

## Story 2 — Twitch attention and prize pools move differently

{markdown_table(["Family", "Matched months", "Pearson r", "Median Twitch hours (M)"], twitch_rows)}

Dota 2 has the strongest descriptive association between monthly Twitch hours and prize pools, with Pearson `r={pearson.loc['Dota 2', 'hours_vs_pool']:.3f}`. The equivalent correlations for Counter-Strike, League of Legends and Valorant are close to zero. League of Legends has the highest median monthly Twitch hours, about {twitch.loc['League of Legends', 'median'] / 1_000_000:,.1f} million, even though its prize-pool total is below Dota 2 and Counter-Strike.

**Limit.** Twitch data is the main game category, not tournament-only viewing, ends in September 2024 and excludes YouTube. Correlation does not establish that higher prize money causes more viewing.

**Action.** Use Twitch attention and prize scale as separate screening dimensions. For a pilot allocation, compare audience reach, prize volatility and data coverage before negotiating campaign cost. Do not call this an ROI calculation.

Supporting figure: `reports/figures/story_02_twitch_prize_relationship.png`.

## Story 3 — Player-country prize concentration

{markdown_table(["Family", "Top player country", "Prize (USD M)", "Share of reconciled family prize", "Money coverage"], country_rows)}

The top player countries differ by family: Denmark for Counter-Strike, China for Dota 2, Korea for League of Legends and the United States for Valorant. Country tables reconcile {overall_coverage:.2f}% of source prize money overall, but family coverage ranges from {coverage_summary['country_money_coverage_pct'].min():.1f}% to {coverage_summary['country_money_coverage_pct'].max():.1f}%.

**Limit.** Country refers to player country in reconciled prize records. It does not represent audience location, tournament location or the complete global market.

**Action.** Use this view to localize player-led content or shortlist ambassador markets. Always show the coverage percentage in the same dashboard view and validate audience geography separately before buying regional media.

Supporting figure: `reports/figures/story_03_country_distribution.png`.

## Permitted recommendation language

- Use `sponsorship-priority signal`, `pilot allocation` or `market for further validation`.
- State the target policy, model, evaluation coverage and source-coverage warning beside the recommendation.
- Do not state ROI, causal impact or guaranteed market growth because revenue, sponsorship cost and profit are not in the dataset.
"""
    (REPORTS_DIR / "storytelling_insights.md").write_text(content, encoding="utf-8")


def write_tableau_handoff(
    release: Path, export: pd.DataFrame, summary: pd.DataFrame
) -> None:
    source_test = export[
        export["target_policy"].eq("source")
        & export["model"].eq("random_forest")
        & export["split"].eq("test")
    ]
    content = f"""# Tableau forecast handoff

## Files and grain

### `data/processed/tableau_forecast_predictions.csv`

- Row grain: `game_family + quarter + target_policy + model`.
- Rows: {len(export):,}.
- Default dashboard filters: `target_policy = source`, `model = random_forest`.
- Within one selected target policy and model, the visible grain is one row per family-quarter.
- `actual_prize_pool_usd` remains blank when the target is missing; `predicted_prize_pool_usd` is still available.

### `data/processed/tableau_forecast_summary.csv`

- Row grain: `target_policy + split + game_family + model`.
- Rows: {len(summary):,}.
- Includes family rows and `Overall` rows for KPI cards.
- `predicted_prize_pool_usd_evaluated` uses only periods with an actual target; `predicted_prize_pool_usd_all_periods` also includes prediction-only periods.

Both files come from `{release.name}` and Day-2 model outputs.

## Relationship design

Use the prediction export as a standalone fact table for the forecast sheets. If a quarter or game dimension is available, relate it many-to-one on `game_family + quarter`. Do not physically join predictions to placements, tournaments or country rows. Those are one-to-many tables and would repeat actual and predicted prize values.

Keep the country map on its reconciled country data source. Use dashboard filters or a shared game-family dimension to coordinate views instead of joining forecast rows to player-country rows.

## Required filters

1. `target_policy`: single value. Default `source`; expose `strict_quality` as sensitivity.
2. `model`: single value. Default `random_forest`; allow comparison with `seasonal_naive` and `linear_regression`.
3. `split`: validation or test.
4. `game_family`: optional multi-select.

If users select several models, actual values repeat once per model. Keep the model filter single-select for KPI totals. For a comparison view, use `MIN(actual_prize_pool_usd)` at family-quarter-policy grain or a FIXED LOD instead of summing actual across models.

## Field definitions

| Field | Definition | Tableau use |
|---|---|---|
| `actual_prize_pool_usd` | Observed target for the selected policy | Line, point or tooltip; keep missing as null |
| `predicted_prize_pool_usd` | Model prediction, clipped at zero | Forecast line or scatter axis |
| `residual_usd` | Actual minus predicted | Positive means underprediction; negative means overprediction |
| `absolute_error_usd` | Absolute residual | Error magnitude |
| `evaluation_available` | Actual exists for scoring | Filter metrics to `True` |
| `evaluation_status` | `evaluated` or `target_missing_prediction_only` | Missing-target warning |
| `coverage_pct` | Evaluated periods divided by total periods | KPI context |
| `is_primary_model` | Random Forest flag | Default model selection |

## Recommended sheets

### Actual vs predicted trend

- Columns: `period_start` as continuous quarter.
- Rows: Measure Values for actual and predicted.
- Color: Measure Names.
- Detail or small multiples: `game_family`.
- Show validation and test through `split`; retain null actual marks as prediction-only.

### Actual vs predicted scatter

- Columns: `actual_prize_pool_usd`.
- Rows: `predicted_prize_pool_usd`.
- Color: `game_family`.
- Filter: `evaluation_available = True`.
- Add a reference line `y = x`.

### Residual review

- Columns: `period_start`.
- Rows: `residual_usd`.
- Color: `error_direction`.
- Add a zero reference line.
- Tooltip: family, quarter, actual, predicted, residual, policy, model and evaluation status.

### KPI cards

Use `tableau_forecast_summary.csv` and show MAE, RMSE, coverage and evaluated periods. Do not average family RMSE values to create Overall RMSE; use the supplied `Overall` row.

## Missing-target treatment

For the source target, the test view evaluates {int(source_test['evaluation_available'].sum())} of {len(source_test)} family-quarter rows. League of Legends 2025Q4, Valorant 2025Q2 and Valorant 2025Q4 have predictions but no actual target. Display them as `Prediction only — target missing`; do not convert null actual or residual to zero.

## Validation checklist

- Prediction key is unique at `game_family + quarter + target_policy + model`.
- With filters `source + random_forest + test`, expect 16 rows, 13 evaluated rows and three prediction-only rows.
- Actual totals must be checked with one model selected.
- Never sum actual or predicted values after joining to tournament, placement or country detail.
- Label country fields as player country and show country-money coverage.
- Recommendations may describe sponsorship-priority signals or pilot allocation, not ROI.
"""
    (REPORTS_DIR / "tableau_forecast_handoff.md").write_text(
        content, encoding="utf-8"
    )


def validate_exports(
    predictions: pd.DataFrame,
    export: pd.DataFrame,
    summary: pd.DataFrame,
) -> None:
    if len(export) != len(predictions) * len(MODEL_COLUMNS):
        raise ValueError("Unexpected Tableau prediction row count")
    expected_actual = predictions[
        ["game_family", "quarter", "target_policy", "actual_prize_pool_usd"]
    ].drop_duplicates()
    for model in MODEL_COLUMNS:
        model_actual = export[export["model"].eq(model)][
            ["game_family", "quarter", "target_policy", "actual_prize_pool_usd"]
        ]
        check = model_actual.merge(
            expected_actual,
            on=["game_family", "quarter", "target_policy"],
            suffixes=("_export", "_source"),
            validate="one_to_one",
        )
        if not np.allclose(
            check["actual_prize_pool_usd_export"],
            check["actual_prize_pool_usd_source"],
            equal_nan=True,
        ):
            raise ValueError(f"Actual totals do not reconcile for model {model}")

    source_test = summary[
        summary["target_policy"].eq("source")
        & summary["split"].eq("test")
        & summary["game_family"].eq("Overall")
        & summary["model"].eq("random_forest")
    ]
    if len(source_test) != 1:
        raise ValueError("Missing unique Overall source-test Random Forest summary")
    row = source_test.iloc[0]
    if int(row["total_periods"]) != 16 or int(row["evaluated_periods"]) != 13:
        raise ValueError("Unexpected source-test coverage in Tableau summary")


def main() -> None:
    release, frames = load_inputs()
    export = build_tableau_predictions(frames["predictions"])
    summary = build_tableau_summary(export)
    errors = build_error_analysis(export)
    top_countries, coverage_summary = aggregate_country_evidence(
        frames["country_year"], frames["country_coverage"]
    )
    evidence = build_evidence(
        frames["quarterly"],
        frames["panel"],
        frames["correlations"],
        top_countries,
        coverage_summary,
        errors,
    )

    validate_exports(frames["predictions"], export, summary)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    export.to_csv(
        PROCESSED_DIR / "tableau_forecast_predictions.csv",
        index=False,
        encoding="utf-8-sig",
    )
    summary.to_csv(
        PROCESSED_DIR / "tableau_forecast_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    errors.to_csv(
        REPORTS_DIR / "storytelling_error_analysis.csv",
        index=False,
        encoding="utf-8-sig",
    )
    evidence.to_csv(
        REPORTS_DIR / "storytelling_evidence.csv",
        index=False,
        encoding="utf-8-sig",
    )

    plot_prize_structure(frames["quarterly"], frames["seasonality"])
    plot_twitch_prize_relationship(frames["panel"], frames["correlations"])
    plot_country_distribution(top_countries, coverage_summary)
    plot_error_concentration(errors)
    write_storytelling_insights(
        release,
        frames["quarterly"],
        frames["panel"],
        frames["correlations"],
        top_countries,
        coverage_summary,
        errors,
    )
    write_tableau_handoff(release, export, summary)

    print(f"Release: {release.name}")
    print(f"Tableau prediction rows: {len(export):,}")
    print(f"Tableau summary rows: {len(summary):,}")
    print("Wrote Day-3 insights, handoff, evidence, and four 300-DPI figures.")


if __name__ == "__main__":
    main()

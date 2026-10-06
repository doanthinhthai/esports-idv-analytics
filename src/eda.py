# -*- coding: utf-8 -*-
"""Reproducible Day-1 EDA for the latest policy-clean analysis release.

Run from any directory with:

    python src/eda.py

The script deliberately ignores the legacy processed tables and uses only the
latest ``analysis_release_v1_*`` folder. It validates the release grain and
key relationships, writes a compact audit summary, and creates five report
figures without modifying the source release.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter
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


def latest_release() -> Path:
    """Return the newest analysis release folder by timestamped name."""
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


def load_release() -> tuple[Path, dict[str, pd.DataFrame], dict]:
    """Load required files and validate their intended analytical grain."""
    release = latest_release()
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    required_files = {
        "tournaments": "tournaments.csv",
        "placements": "placements.csv",
        "twitch": "twitch_monthly.csv",
        "panel": "game_monthly_panel.csv",
        "quarterly": "forecast_prize_quarterly.csv",
        "country_coverage": "country_coverage.csv",
        "quality_sensitivity": "eda_quality_sensitivity.csv",
        "correlations": "eda_correlations_descriptive.csv",
        "annual_counts": "eda_annual_source_counts.csv",
        "forecast_status": "forecast_status.csv",
        "country_prizes": "country_prizes.csv",
    }
    missing = [filename for filename in required_files.values() if not (release / filename).exists()]
    if missing:
        raise FileNotFoundError(f"Missing release files: {missing}")
    frames = {
        name: pd.read_csv(release / filename, encoding="utf-8-sig")
        for name, filename in required_files.items()
    }

    tournaments = frames["tournaments"]
    placements = frames["placements"]
    twitch = frames["twitch"]
    quarterly = frames["quarterly"]
    panel = frames["panel"]

    if manifest.get("stage") != "analysis_release_v1_policy_clean_not_source_verified":
        raise ValueError("Unexpected release stage; review the release policy before EDA.")
    if not tournaments["tournament_id"].is_unique:
        raise ValueError("tournament_id must be unique in tournaments.csv")
    if not placements["placement_id"].is_unique:
        raise ValueError("placement_id must be unique in placements.csv")
    if not placements["tournament_id"].isin(tournaments["tournament_id"]).all():
        raise ValueError("Found placements without a parent tournament")
    if twitch.duplicated(["game_family", "month_start"]).any():
        raise ValueError("Duplicate game_family + month_start in twitch_monthly.csv")
    if panel.duplicated(["game_family", "month_start"]).any():
        raise ValueError("Duplicate game_family + month_start in game_monthly_panel.csv")
    if quarterly.duplicated(["game_family", "quarter"]).any():
        raise ValueError("Duplicate game_family + quarter in forecast_prize_quarterly.csv")
    if set(tournaments["game_family"].unique()) != set(FAMILIES):
        raise ValueError("Tournament game families do not match the approved project scope")
    if set(twitch["game_family"].unique()) != set(FAMILIES):
        raise ValueError("Twitch game families do not match the approved project scope")

    starts = pd.to_datetime(tournaments["start_date"], errors="raise")
    ends = pd.to_datetime(tournaments["end_date"], errors="raise")
    if not starts.le(ends).all():
        raise ValueError("Found a tournament with start_date after end_date")
    if not starts.between("2012-01-01", "2025-12-31").all():
        raise ValueError("Tournament date falls outside the approved 2012-2025 scope")
    if (tournaments["prize_pool_usd"] < 0).any():
        raise ValueError("Prize pools must be non-negative")

    money_from_quarters = int(round(quarterly["pool_cents"].sum()))
    money_from_tournaments = int(tournaments["pool_cents"].sum())
    count_from_quarters = int(round(quarterly["observed_tournament_count"].sum()))
    if money_from_quarters != money_from_tournaments:
        raise ValueError("Quarterly prize totals do not reconcile with tournaments.csv")
    if count_from_quarters != len(tournaments):
        raise ValueError("Quarterly tournament counts do not reconcile with tournaments.csv")

    return release, frames, manifest


def save_figure(fig: plt.Figure, filename: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / filename, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def style_axis(ax: plt.Axes) -> None:
    ax.grid(True, color="#D9D9D9", alpha=0.55, linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)


def plot_quarterly_prize(quarterly: pd.DataFrame) -> None:
    data = quarterly.copy()
    data["period_start"] = pd.to_datetime(data["period_start"])
    fig, axes = plt.subplots(2, 2, figsize=(15, 9), sharex=True)
    for ax, family in zip(axes.flat, FAMILIES):
        group = data[data["game_family"] == family].sort_values("period_start")
        ax.plot(
            group["period_start"],
            group["target_prize_pool_usd"] / 1_000_000,
            color=COLORS[family],
            linewidth=2.2,
            marker="o",
            markersize=3,
            label="Source target",
        )
        ax.plot(
            group["period_start"],
            group["strict_target_prize_pool_usd"] / 1_000_000,
            color="#555555",
            linewidth=1.4,
            linestyle="--",
            alpha=0.85,
            label="Strict-quality sensitivity",
        )
        ax.axvspan(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31"), color="#F2C14E", alpha=0.10)
        ax.axvspan(pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31"), color="#D1495B", alpha=0.08)
        missing_test = group[group["split"].eq("test") & group["target_prize_pool_usd"].isna()]
        if not missing_test.empty:
            labels = ", ".join(missing_test["quarter"].tolist())
            ax.text(0.98, 0.94, f"Missing: {labels}", transform=ax.transAxes, ha="right", va="top", fontsize=9, color="#8B1E2D")
        ax.set_title(family, loc="left", fontweight="bold")
        ax.set_ylabel("Prize pool (USD millions)")
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        style_axis(ax)
    axes[0, 0].legend(loc="upper left", fontsize=9, frameon=False)
    fig.suptitle("Quarterly tournament prize pools by game family", fontsize=18, fontweight="bold")
    fig.text(0.5, 0.01, "Validation: 2024 (yellow). Test: 2025 (red). Missing quarters remain blank.", ha="center", fontsize=11, color="#555555")
    fig.tight_layout(rect=(0, 0.035, 1, 0.95))
    save_figure(fig, "eda_01_quarterly_prize.png")


def plot_twitch_hours(twitch: pd.DataFrame) -> None:
    data = twitch.copy()
    data["month_start"] = pd.to_datetime(data["month_start"])
    fig, axes = plt.subplots(2, 2, figsize=(15, 9), sharex=False)
    for ax, family in zip(axes.flat, FAMILIES):
        group = data[data["game_family"] == family].sort_values("month_start").copy()
        group["rolling_12m"] = group["hours_watched"].rolling(12, min_periods=6).mean()
        ax.plot(group["month_start"], group["hours_watched"] / 1_000_000, color=COLORS[family], alpha=0.28, linewidth=1.1, label="Monthly")
        ax.plot(group["month_start"], group["rolling_12m"] / 1_000_000, color=COLORS[family], linewidth=2.4, label="12-month rolling mean")
        ax.set_title(family, loc="left", fontweight="bold")
        ax.set_ylabel("Hours watched (millions)")
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        style_axis(ax)
    axes[0, 0].legend(loc="upper left", fontsize=9, frameon=False)
    fig.suptitle("Monthly Twitch viewing hours", fontsize=18, fontweight="bold")
    fig.text(0.5, 0.01, "Main Twitch category only. Data ends in September 2024; Valorant begins in April 2020.", ha="center", fontsize=11, color="#555555")
    fig.tight_layout(rect=(0, 0.035, 1, 0.95))
    save_figure(fig, "eda_02_twitch_hours.png")


def plot_annual_counts(annual: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 9), sharex=False)
    for ax, family in zip(axes.flat, FAMILIES):
        group = annual[annual["game_family"] == family].sort_values("year")
        ax.plot(group["year"], group["observed_tournaments"], color=COLORS[family], marker="o", linewidth=2.2)
        latest = group[group["year"] == 2025]
        if not latest.empty:
            ax.scatter(latest["year"], latest["observed_tournaments"], color="#D1495B", s=65, zorder=3)
            ax.annotate(
                f"2025: {int(latest['observed_tournaments'].iloc[0])}",
                (2025, latest["observed_tournaments"].iloc[0]),
                xytext=(-6, 10),
                textcoords="offset points",
                ha="right",
                fontsize=9,
                color="#8B1E2D",
            )
        ax.axvspan(2024.5, 2025.5, color="#D1495B", alpha=0.08)
        ax.set_title(family, loc="left", fontweight="bold")
        ax.set_ylabel("Observed tournaments")
        ax.set_xticks(range(int(group["year"].min()), 2026, 2))
        style_axis(ax)
    fig.suptitle("Observed tournament counts by year", fontsize=18, fontweight="bold")
    fig.text(0.5, 0.01, "The 2025 decline may reflect incomplete source coverage and is not evidence of market contraction.", ha="center", fontsize=11, color="#8B1E2D")
    fig.tight_layout(rect=(0, 0.035, 1, 0.95))
    save_figure(fig, "eda_03_annual_tournament_counts.png")


def plot_quality_sensitivity(sensitivity: pd.DataFrame) -> None:
    data = sensitivity.set_index("game_family").loc[FAMILIES].reset_index()
    data = data.sort_values("strict_share_of_source_pool_pct")
    fig, ax = plt.subplots(figsize=(12, 6.8))
    bars = ax.barh(
        data["game_family"],
        data["strict_share_of_source_pool_pct"],
        color=[COLORS[value] for value in data["game_family"]],
    )
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.set_xlabel("Share of source prize pool retained by strict-quality filter")
    ax.set_ylabel("")
    ax.set_title("Prize-pool sensitivity to the strict-quality filter", loc="left", fontsize=18, fontweight="bold")
    ax.bar_label(bars, labels=[f"{value:.1f}%" for value in data["strict_share_of_source_pool_pct"]], padding=5, fontsize=11)
    style_axis(ax)
    fig.tight_layout()
    save_figure(fig, "eda_04_quality_sensitivity.png")


def plot_country_coverage(coverage: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, 7.5))
    for family in FAMILIES:
        group = coverage[coverage["game_family"] == family].sort_values("year")
        ax.plot(
            group["year"],
            group["country_money_coverage_pct"],
            color=COLORS[family],
            marker="o",
            linewidth=2.1,
            label=family,
        )
    ax.axhline(90, color="#777777", linestyle="--", linewidth=1.2, label="90% reference")
    ax.set_ylim(65, 102)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.set_xlabel("Year")
    ax.set_ylabel("Prize pool covered by reconciled country tables")
    ax.set_title("Country-prize coverage by game family and year", loc="left", fontsize=18, fontweight="bold")
    ax.legend(ncol=3, frameon=False, loc="lower left")
    style_axis(ax)
    fig.tight_layout()
    save_figure(fig, "eda_05_country_coverage.png")


def write_summary(release: Path, frames: dict[str, pd.DataFrame], manifest: dict) -> Path:
    tournaments = frames["tournaments"]
    placements = frames["placements"]
    twitch = frames["twitch"]
    sensitivity = frames["quality_sensitivity"].set_index("game_family")
    correlations = frames["correlations"]
    correlations = correlations[correlations["method"] == "pearson"].set_index("game_family")
    coverage = frames["country_coverage"].groupby("game_family")["country_money_coverage_pct"].min()
    annual = frames["annual_counts"]
    statuses = frames["forecast_status"].set_index("game_family")

    rows: list[dict[str, object]] = []

    def add(section: str, family: str, metric: str, value: object, unit: str, note: str) -> None:
        rows.append(
            {
                "Section": section,
                "Game_Family": family,
                "Metric": metric,
                "Value": value,
                "Unit": unit,
                "Interpretation": note,
            }
        )

    add("Release", "All", "Release folder", release.name, "text", "Newest policy-clean analysis release")
    add("Release", "All", "Release stage", manifest["stage"], "text", "Source coverage is not fully verified")
    add("Scope", "All", "Tournaments", len(tournaments), "rows", "One row per tournament")
    add("Scope", "All", "Placements", len(placements), "rows", "One row per accepted team result")
    add("Scope", "All", "Twitch observations", len(twitch), "game-months", "Main Twitch category; not tournament-level viewers")
    add("Scope", "All", "Country prize observations", len(frames["country_prizes"]), "rows", "Only reconciled tournament-country tables")
    add("Scope", "All", "Total source prize pool", float(tournaments["prize_pool_usd"].sum()), "USD", "Nominal USD; not inflation-adjusted")
    add("Scope", "All", "Earliest tournament", tournaments["start_date"].min(), "date", "Approved scope begins in 2012")
    add("Scope", "All", "Latest tournament", tournaments["start_date"].max(), "date", "2025 source coverage remains unverified")
    strict_pool_share = tournaments.loc[tournaments["strict_quality"], "prize_pool_usd"].sum() / tournaments["prize_pool_usd"].sum() * 100
    add("Quality", "All", "Strict prize pool retained", float(strict_pool_share), "percent", "Sensitivity filter changes the target materially")
    add("Quality", "All", "Country prize coverage", float(manifest["country_prize_coverage_pct"]), "percent", "Coverage of source prize pool, not total market")

    for family in FAMILIES:
        family_tournaments = tournaments[tournaments["game_family"] == family]
        twitch_family = twitch[twitch["game_family"] == family]
        count_2025 = annual.loc[(annual["game_family"] == family) & (annual["year"] == 2025), "observed_tournaments"]
        missing_quarters = statuses.loc[family, "missing_2025_quarters"]
        missing_text = "No missing quarters" if pd.isna(missing_quarters) or str(missing_quarters).strip() == "" else str(missing_quarters)
        add("Family", family, "Tournaments", len(family_tournaments), "rows", "Observed tournament metadata")
        add("Family", family, "Source prize pool", float(family_tournaments["prize_pool_usd"].sum()), "USD", "Nominal source total")
        add("Family", family, "Median tournament prize", float(family_tournaments["prize_pool_usd"].median()), "USD", "Robust typical tournament size")
        add("Family", family, "Strict prize pool retained", float(sensitivity.loc[family, "strict_share_of_source_pool_pct"]), "percent", "Sensitivity to quality policy")
        add("Family", family, "Twitch months", len(twitch_family), "months", f"{twitch_family['month_start'].min()} to {twitch_family['month_start'].max()}")
        add("Family", family, "Pearson hours-prize correlation", float(correlations.loc[family, "hours_vs_pool"]), "coefficient", f"Descriptive, n={int(correlations.loc[family, 'n'])}; not causal")
        add("Family", family, "Minimum country coverage", float(coverage.loc[family]), "percent", "Lowest annual reconciled prize coverage")
        add("Family", family, "Observed tournaments in 2025", int(count_2025.iloc[0]), "rows", "May reflect incomplete source coverage")
        add("Forecast", family, "Missing 2025 target quarters", missing_text, "quarters", "Do not impute missing observations as zero")

    summary = pd.DataFrame(rows)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output = REPORTS_DIR / "eda_summary.csv"
    summary.to_csv(output, index=False, encoding="utf-8-sig")
    return output


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlepad": 10,
            "figure.dpi": 120,
        }
    )
    release, frames, manifest = load_release()
    summary_path = write_summary(release, frames, manifest)
    plot_quarterly_prize(frames["quarterly"])
    plot_twitch_hours(frames["twitch"])
    plot_annual_counts(frames["annual_counts"])
    plot_quality_sensitivity(frames["quality_sensitivity"])
    plot_country_coverage(frames["country_coverage"])

    print(f"EDA completed from release: {release.name}")
    print(f"Tournaments: {len(frames['tournaments']):,}")
    print(f"Placements: {len(frames['placements']):,}")
    print(f"Summary: {summary_path}")
    print(f"Figures: {FIGURES_DIR}")


if __name__ == "__main__":
    main()

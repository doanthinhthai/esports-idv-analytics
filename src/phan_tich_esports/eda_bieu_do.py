"""Các biểu đồ tĩnh của bước khám phá dữ liệu."""

from __future__ import annotations

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd

from phan_tich_esports.cau_hinh import COLORS, FAMILIES, save_figure, style_axis


def plot_quarterly_prize(quarterly: pd.DataFrame) -> None:
    """Vẽ quỹ thưởng theo quý và so sánh chính sách chất lượng."""
    data = quarterly.copy()
    data["period_start"] = pd.to_datetime(data["period_start"])
    fig, axes = plt.subplots(2, 2, figsize=(15, 9), sharex=True)
    for ax, family in zip(axes.flat, FAMILIES):
        group = data[data["game_family"] == family].sort_values("period_start")
        ax.plot(group["period_start"], group["target_prize_pool_usd"] / 1_000_000, color=COLORS[family], linewidth=2.2, marker="o", markersize=3, label="Source target")
        ax.plot(group["period_start"], group["strict_target_prize_pool_usd"] / 1_000_000, color="#555555", linewidth=1.4, linestyle="--", alpha=0.85, label="Strict-quality sensitivity")
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
    """Vẽ giờ xem Twitch hàng tháng và trung bình trượt 12 tháng."""
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
    """Vẽ số giải quan sát theo năm và đánh dấu năm 2025."""
    fig, axes = plt.subplots(2, 2, figsize=(15, 9), sharex=False)
    for ax, family in zip(axes.flat, FAMILIES):
        group = annual[annual["game_family"] == family].sort_values("year")
        ax.plot(group["year"], group["observed_tournaments"], color=COLORS[family], marker="o", linewidth=2.2)
        latest = group[group["year"] == 2025]
        if not latest.empty:
            ax.scatter(latest["year"], latest["observed_tournaments"], color="#D1495B", s=65, zorder=3)
            ax.annotate(f"2025: {int(latest['observed_tournaments'].iloc[0])}", (2025, latest["observed_tournaments"].iloc[0]), xytext=(-6, 10), textcoords="offset points", ha="right", fontsize=9, color="#8B1E2D")
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
    """Vẽ tỷ lệ quỹ thưởng còn lại sau bộ lọc strict-quality."""
    data = sensitivity.set_index("game_family").loc[FAMILIES].reset_index()
    data = data.sort_values("strict_share_of_source_pool_pct")
    fig, ax = plt.subplots(figsize=(12, 6.8))
    bars = ax.barh(data["game_family"], data["strict_share_of_source_pool_pct"], color=[COLORS[value] for value in data["game_family"]])
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
    """Vẽ độ phủ tiền thưởng theo quốc gia tuyển thủ."""
    fig, ax = plt.subplots(figsize=(13, 7.5))
    for family in FAMILIES:
        group = coverage[coverage["game_family"] == family].sort_values("year")
        ax.plot(group["year"], group["country_money_coverage_pct"], color=COLORS[family], marker="o", linewidth=2.1, label=family)
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


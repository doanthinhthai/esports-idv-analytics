"""Các biểu đồ hỗ trợ kể chuyện bằng dữ liệu."""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd

from phan_tich_esports.cau_hinh import COLORS, FAMILIES, save_figure, style_axis


def millions(value: float, _: int) -> str:
    """Định dạng trục tiền tệ theo triệu USD."""
    return f"${value / 1_000_000:.0f}M"


def plot_prize_structure(quarterly: pd.DataFrame, seasonality: pd.DataFrame) -> None:
    """Vẽ quy mô quỹ thưởng và mùa vụ theo quý."""
    totals = quarterly.groupby("game_family", as_index=False)["target_prize_pool_usd"].sum().set_index("game_family").loc[FAMILIES].reset_index()
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))
    bars = axes[0].bar(totals["game_family"], totals["target_prize_pool_usd"], color=[COLORS[family] for family in totals["game_family"]])
    axes[0].bar_label(bars, labels=[f"${value / 1_000_000:.1f}M" for value in totals["target_prize_pool_usd"]], padding=4, fontsize=10)
    axes[0].set_ylabel("Observed prize pool (USD)")
    axes[0].yaxis.set_major_formatter(FuncFormatter(millions))
    axes[0].tick_params(axis="x", rotation=15)
    axes[0].set_title("Total observed prize pool", loc="left", fontweight="bold")
    style_axis(axes[0])

    for family in FAMILIES:
        group = seasonality[seasonality["game_family"].eq(family)].sort_values("quarter_of_year")
        axes[1].plot(group["quarter_of_year"], group["median"] / 1_000_000, color=COLORS[family], marker="o", linewidth=2.2, label=family)
    axes[1].set_xticks([1, 2, 3, 4], ["Q1", "Q2", "Q3", "Q4"])
    axes[1].set_ylabel("Median train prize pool (USD millions)")
    axes[1].set_title("Quarterly seasonality in train data", loc="left", fontweight="bold")
    axes[1].legend(frameon=False, fontsize=9)
    style_axis(axes[1])
    fig.suptitle("Prize-pool scale and seasonality", fontsize=18, fontweight="bold")
    fig.text(0.5, 0.01, "Observed source totals; seasonal medians use train periods only. Incomplete 2025 coverage is not treated as market decline.", ha="center", color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    save_figure(fig, "story_01_prize_structure.png")


def plot_twitch_prize_relationship(panel: pd.DataFrame, correlations: pd.DataFrame) -> None:
    """Vẽ mối quan hệ mô tả giữa giờ xem Twitch và quỹ thưởng."""
    pearson = correlations[correlations["method"].eq("pearson")].set_index("game_family")
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for ax, family in zip(axes.flat, FAMILIES):
        group = panel[panel["game_family"].eq(family) & panel["hours_watched"].gt(0) & panel["source_prize_pool_usd"].gt(0)]
        ax.scatter(group["hours_watched"], group["source_prize_pool_usd"], color=COLORS[family], alpha=0.6, s=32)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(family, loc="left", fontweight="bold")
        ax.text(0.98, 0.94, f"Pearson r = {pearson.loc[family, 'hours_vs_pool']:.3f}", transform=ax.transAxes, ha="right", va="top", fontsize=10)
        ax.set_xlabel("Monthly Twitch hours watched")
        ax.set_ylabel("Monthly prize pool (USD)")
        style_axis(ax)
    fig.suptitle("Monthly Twitch attention and prize pools", fontsize=18, fontweight="bold")
    fig.text(0.5, 0.01, "Log scales. Correlation is descriptive and does not show that prize money causes viewing hours.", ha="center", color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    save_figure(fig, "story_02_twitch_prize_relationship.png")


def plot_country_distribution(top_countries: pd.DataFrame, coverage_summary: pd.DataFrame) -> None:
    """Vẽ top quốc gia tuyển thủ và hiển thị độ phủ dữ liệu."""
    coverage = coverage_summary.set_index("game_family")
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    for ax, family in zip(axes.flat, FAMILIES):
        group = top_countries[top_countries["game_family"].eq(family)].sort_values("prize_cents")
        bars = ax.barh(group["country_name"], group["prize_cents"] / 100 / 1_000_000, color=COLORS[family])
        ax.bar_label(bars, labels=[f"${value / 100 / 1_000_000:.1f}M" for value in group["prize_cents"]], padding=4, fontsize=9)
        ax.set_title(f"{family} — coverage {coverage.loc[family, 'country_money_coverage_pct']:.1f}%", loc="left", fontweight="bold")
        ax.set_xlabel("Reconciled player-country prize (USD millions)")
        style_axis(ax)
    fig.suptitle("Top player countries in reconciled prize data", fontsize=18, fontweight="bold")
    fig.text(0.5, 0.01, "Player country, not audience country. Bars exclude unreconciled country rows; coverage is shown for each family.", ha="center", color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    save_figure(fig, "story_03_country_distribution.png")


def plot_error_concentration(errors: pd.DataFrame) -> None:
    """Vẽ các kỳ có sai số tuyệt đối lớn nhất."""
    data = errors.head(12).sort_values("absolute_error_usd")
    labels = data["game_family"] + " " + data["quarter"]
    colors = ["#D1495B" if direction == "overprediction" else "#2F5597" for direction in data["error_direction"]]
    fig, ax = plt.subplots(figsize=(12, 7.5))
    bars = ax.barh(labels, data["absolute_error_usd"], color=colors)
    ax.bar_label(bars, labels=[f"${value / 1_000_000:.2f}M" for value in data["absolute_error_usd"]], padding=4, fontsize=9)
    ax.xaxis.set_major_formatter(FuncFormatter(millions))
    ax.set_xlabel("Random-forest absolute error (USD)")
    ax.set_title("Largest validation and test forecast errors", loc="left", fontsize=18, fontweight="bold")
    ax.text(0.99, 0.03, "Red: overprediction   Blue: underprediction", transform=ax.transAxes, ha="right", color="#555555")
    style_axis(ax)
    fig.tight_layout()
    save_figure(fig, "story_04_forecast_error_concentration.png")


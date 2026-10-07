"""Các biểu đồ đánh giá mô hình dự báo."""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

from phan_tich_esports.cau_hinh import COLORS, FAMILIES, save_figure, style_axis
from phan_tich_esports.mo_hinh_core import MODEL_LABELS


def millions(value: float, _: int) -> str:
    """Định dạng trục tiền tệ theo triệu USD."""
    return f"${value / 1_000_000:.1f}M"


def plot_actual_vs_predicted(predictions: pd.DataFrame) -> None:
    """So sánh actual và prediction của ba mô hình trên test."""
    data = predictions[predictions["target_policy"].eq("source") & predictions["split"].eq("test") & predictions["evaluation_available"]]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), sharex=True, sharey=True)
    maximum = max(data["actual_prize_pool_usd"].max(), data[[f"prediction_{name}" for name in MODEL_LABELS]].max().max())
    limit = maximum * 1.08
    for ax, (name, label) in zip(axes, MODEL_LABELS.items()):
        for family in FAMILIES:
            group = data[data["game_family"].eq(family)]
            ax.scatter(group["actual_prize_pool_usd"], group[f"prediction_{name}"], s=65, alpha=0.85, color=COLORS[family], label=family)
        ax.plot([0, limit], [0, limit], color="#555555", linestyle="--", linewidth=1.3)
        ax.set_xlim(0, limit)
        ax.set_ylim(0, limit)
        ax.set_title(label, loc="left", fontweight="bold")
        ax.set_xlabel("Actual prize pool")
        ax.xaxis.set_major_formatter(FuncFormatter(millions))
        ax.yaxis.set_major_formatter(FuncFormatter(millions))
        style_axis(ax)
    axes[0].set_ylabel("Predicted prize pool")
    axes[-1].legend(frameon=False, fontsize=8, loc="lower right")
    fig.suptitle("2025 quarterly prize-pool forecasts", fontsize=18, fontweight="bold")
    fig.text(0.5, 0.01, "Source target. Only 13 observed family-quarter test rows are scored.", ha="center", color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    save_figure(fig, "model_actual_vs_predicted.png")


def plot_performance(metrics: pd.DataFrame) -> None:
    """Vẽ MAE và RMSE của ba mô hình theo validation và test."""
    data = metrics[metrics["target_policy"].eq("source") & metrics["game_family"].eq("Overall")].copy()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    x = np.arange(len(MODEL_LABELS))
    width = 0.36
    for ax, metric, title in zip(axes, ["mae_usd", "rmse_usd"], ["MAE", "RMSE"]):
        for offset, split, color in [(-width / 2, "validation", "#2F5597"), (width / 2, "test", "#D1495B")]:
            values = data[data["split"].eq(split)].set_index("model").loc[list(MODEL_LABELS), metric].to_numpy()
            bars = ax.bar(x + offset, values, width, label=split.title(), color=color)
            ax.bar_label(bars, labels=[f"${value / 1_000_000:.2f}M" for value in values], padding=3, fontsize=9)
        ax.set_xticks(x, ["Seasonal\nnaive", "Linear\nregression", "Random\nforest"])
        ax.set_ylabel(f"{title} (USD)")
        ax.yaxis.set_major_formatter(FuncFormatter(millions))
        ax.set_title(f"Overall {title}", loc="left", fontweight="bold")
        style_axis(ax)
    axes[0].legend(frameon=False)
    fig.suptitle("Forecast error by model and time split", fontsize=18, fontweight="bold")
    fig.text(0.5, 0.01, "The primary model is selected using validation RMSE, not the test result.", ha="center", color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    save_figure(fig, "model_performance_comparison.png")


def plot_feature_importance(importance: pd.DataFrame) -> None:
    """Vẽ 15 đặc trưng quan trọng nhất của Random Forest."""
    data = importance.head(15).sort_values("importance")
    fig, ax = plt.subplots(figsize=(11, 6.8))
    bars = ax.barh(data["feature"], data["importance"], color="#2F5597")
    ax.bar_label(bars, labels=[f"{value:.3f}" for value in data["importance"]], padding=4, fontsize=9)
    ax.set_xlabel("Random-forest impurity importance")
    ax.set_title("Features used by the final source-target random forest", loc="left", fontsize=17, fontweight="bold")
    style_axis(ax)
    fig.tight_layout()
    save_figure(fig, "model_feature_importance.png")


def plot_residuals(predictions: pd.DataFrame, primary_model: str) -> None:
    """Vẽ residual test của mô hình chính theo family và quý."""
    data = predictions[predictions["target_policy"].eq("source") & predictions["split"].eq("test") & predictions["evaluation_available"]].copy()
    data = data.sort_values(["period_start", "game_family"])
    fig, ax = plt.subplots(figsize=(13, 6.5))
    for family in FAMILIES:
        group = data[data["game_family"].eq(family)]
        ax.scatter(group["period_start"], group[f"residual_{primary_model}"], s=75, color=COLORS[family], label=family, alpha=0.9)
    ax.axhline(0, color="#555555", linestyle="--", linewidth=1.3)
    ax.yaxis.set_major_formatter(FuncFormatter(millions))
    ax.set_ylabel("Actual minus predicted prize pool")
    ax.set_xlabel("2025 quarter")
    ax.set_title(f"Test residuals: {MODEL_LABELS[primary_model]}", loc="left", fontsize=17, fontweight="bold")
    ax.legend(frameon=False, ncol=2)
    style_axis(ax)
    fig.tight_layout()
    save_figure(fig, "model_residuals.png")


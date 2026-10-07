"""Ghi tài liệu kỹ thuật tóm tắt kết quả mô hình."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from phan_tich_esports.cau_hinh import REPORTS_DIR
from phan_tich_esports.mo_hinh_core import MODEL_LABELS


def write_notes(
    release: Path,
    metrics: pd.DataFrame,
    tuning: pd.DataFrame,
    predictions: pd.DataFrame,
    primary_model: str,
) -> None:
    """Ghi giao thức, chỉ số, missing target và giới hạn diễn giải."""
    overall = metrics[metrics["target_policy"].eq("source") & metrics["game_family"].eq("Overall")].copy()
    validation = overall[overall["split"].eq("validation")].set_index("model")
    test = overall[overall["split"].eq("test")].set_index("model")
    selected_tuning = tuning[tuning["target"].eq("target_prize_pool_usd")].sort_values(["validation_rmse_usd", "validation_mae_usd"]).iloc[0]
    missing = predictions[predictions["target_policy"].eq("source") & predictions["split"].eq("test") & ~predictions["evaluation_available"]]
    missing_label = ", ".join(f"{row.game_family} {row.quarter}" for row in missing.itertuples())

    table_lines = [
        "| Model | Validation MAE | Validation RMSE | Test MAE | Test RMSE |",
        "|---|---:|---:|---:|---:|",
    ]
    for model_name, label in MODEL_LABELS.items():
        table_lines.append(
            f"| {label} | {validation.loc[model_name, 'mae_usd']:,.0f} | "
            f"{validation.loc[model_name, 'rmse_usd']:,.0f} | "
            f"{test.loc[model_name, 'mae_usd']:,.0f} | "
            f"{test.loc[model_name, 'rmse_usd']:,.0f} |"
        )

    content = f"""# Day 2 model evaluation notes

## Scope and protocol

- Release: `{release.name}`.
- Target grain: game family–quarter.
- Train: through 2023. Validation: 2024. Test: 2025.
- Protocol: rolling one-step. Earlier observed validation/test targets may become lag features for later quarters in the same split.
- Predictions are clipped at zero because prize pools cannot be negative.
- The primary model is selected by overall source-target validation RMSE before inspecting the test score.

## Source-target performance (USD)

{chr(10).join(table_lines)}

Selected primary model: **{MODEL_LABELS[primary_model]}**. Validation RMSE is **{validation.loc[primary_model, 'rmse_usd']:,.0f} USD** and test RMSE on observed rows is **{test.loc[primary_model, 'rmse_usd']:,.0f} USD**.

The selected random-forest setting for the source target is `max_depth={selected_tuning['max_depth']}`, `min_samples_leaf={selected_tuning['min_samples_leaf']}` and `max_features={selected_tuning['max_features']}`. The random forest is still reported even when another benchmark wins validation.

## Missing target and coverage

The source-target test score uses **{int(test.loc[primary_model, 'n_evaluated'])} of {int(test.loc[primary_model, 'n_total_periods'])}** available family-quarter rows. Missing test targets remain blank and are excluded from all metrics: {missing_label}. Their predictions are retained for Tableau with `evaluation_status=target_missing_prediction_only`.

## Interpretation limits

- This release is policy-clean but source coverage is not fully verified. A forecast error can reflect source completeness as well as market behavior.
- Seasonal naive, linear regression and random forest use only lagged prize data, rolling statistics, time and quarter/family indicators. Current-quarter tournament count, placements, prize fields and Twitch values are excluded to prevent leakage.
- The strict-quality target is a sensitivity analysis, not a substitute for source verification.
- R² is diagnostic only and is blank for family-level groups with fewer than four evaluated rows.
- Impurity importance can favor continuous variables and does not establish causality.
"""
    (REPORTS_DIR / "model_evaluation_notes.md").write_text(content, encoding="utf-8")


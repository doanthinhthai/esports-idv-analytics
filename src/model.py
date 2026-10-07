# -*- coding: utf-8 -*-
"""Điều phối huấn luyện và đánh giá dự báo quỹ thưởng theo quý.

Chạy bằng: ``python src/model.py``.
"""

import pandas as pd
from sklearn.pipeline import Pipeline

from phan_tich_esports.cau_hinh import REPORTS_DIR, configure_console
from phan_tich_esports.mo_hinh_bao_cao import write_notes
from phan_tich_esports.mo_hinh_bieu_do import (
    plot_actual_vs_predicted,
    plot_feature_importance,
    plot_performance,
    plot_residuals,
)
from phan_tich_esports.mo_hinh_core import (
    MODEL_LABELS,
    TARGETS,
    extract_model_diagnostics,
    fit_and_predict_target,
    load_quarterly_release,
    quality_sensitivity,
    score_predictions,
)


def main() -> None:
    """Chạy pipeline mô hình, xuất bảng kết quả, biểu đồ và ghi chú."""
    configure_console()
    release, base, _ = load_quarterly_release()
    all_predictions: list[pd.DataFrame] = []
    all_tuning: list[pd.DataFrame] = []
    source_linear: Pipeline | None = None
    source_forest: Pipeline | None = None

    for policy, target in TARGETS.items():
        predictions, linear, forest, tuning = fit_and_predict_target(base, policy, target)
        all_predictions.append(predictions)
        all_tuning.append(tuning)
        if policy == "source":
            source_linear = linear
            source_forest = forest

    assert source_linear is not None and source_forest is not None
    predictions = pd.concat(all_predictions, ignore_index=True).sort_values(
        ["target_policy", "split", "period_start", "game_family"]
    )
    tuning = pd.concat(all_tuning, ignore_index=True)
    metrics = score_predictions(predictions)
    sensitivity = quality_sensitivity(base)
    coefficients, importance = extract_model_diagnostics(source_linear, source_forest)

    overall_validation = metrics[
        metrics["target_policy"].eq("source")
        & metrics["split"].eq("validation")
        & metrics["game_family"].eq("Overall")
    ].sort_values(["rmse_usd", "mae_usd", "model"])
    primary_model = str(overall_validation.iloc[0]["model"])

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(REPORTS_DIR / "model_predictions.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(REPORTS_DIR / "model_metrics.csv", index=False, encoding="utf-8-sig")
    importance.to_csv(REPORTS_DIR / "model_feature_importance.csv", index=False, encoding="utf-8-sig")
    coefficients.to_csv(REPORTS_DIR / "model_linear_coefficients.csv", index=False, encoding="utf-8-sig")
    sensitivity.to_csv(REPORTS_DIR / "model_quality_sensitivity.csv", index=False, encoding="utf-8-sig")
    tuning.to_csv(REPORTS_DIR / "model_tuning_results.csv", index=False, encoding="utf-8-sig")

    plot_actual_vs_predicted(predictions)
    plot_performance(metrics)
    plot_feature_importance(importance)
    plot_residuals(predictions, primary_model)
    write_notes(release, metrics, tuning, predictions, primary_model)

    selected = overall_validation.iloc[0]
    print(f"Release: {release.name}")
    print(f"Mô hình chính: {MODEL_LABELS[primary_model]}")
    print(f"Validation RMSE: {selected['rmse_usd']:,.2f} USD")
    print("Đã ghi bảng, ghi chú và bốn biểu đồ mô hình vào reports/.")


if __name__ == "__main__":
    main()

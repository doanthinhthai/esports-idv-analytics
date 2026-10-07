"""Chuẩn bị dữ liệu, bằng chứng và kiểm tra đầu ra storytelling."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from phan_tich_esports.cau_hinh import FAMILIES, REPORTS_DIR, latest_release
from phan_tich_esports.mo_hinh_core import MODEL_LABELS


MODEL_COLUMNS = {
    "seasonal_naive": "prediction_seasonal_naive",
    "linear_regression": "prediction_linear_regression",
    "random_forest": "prediction_random_forest",
}
TARGET_COLUMNS = {
    "source": "target_prize_pool_usd",
    "strict_quality": "strict_target_prize_pool_usd",
}


def load_inputs() -> tuple[Path, dict[str, pd.DataFrame]]:
    """Đọc dữ liệu EDA và mô hình, sau đó đối chiếu actual với nguồn."""
    release = latest_release()
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("stage") != "analysis_release_v1_policy_clean_not_source_verified":
        raise ValueError("Stage của release không phù hợp cho storytelling")

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
        raise FileNotFoundError(f"Thiếu đầu vào storytelling: {missing}")
    frames = {name: pd.read_csv(path, encoding="utf-8-sig") for name, path in paths.items()}

    quarterly = frames["quarterly"]
    predictions = frames["predictions"]
    if quarterly.duplicated(["game_family", "quarter"]).any():
        raise ValueError("Bảng quý nguồn bị trùng khóa family-quarter")
    if predictions.duplicated(["game_family", "quarter", "target_policy"]).any():
        raise ValueError("Bảng dự báo bị trùng khóa family-quarter-policy")
    if set(predictions["target_policy"].unique()) != set(TARGET_COLUMNS):
        raise ValueError("Bảng dự báo có target policy không hợp lệ")

    comparison = predictions.merge(
        quarterly[["game_family", "quarter", *TARGET_COLUMNS.values()]],
        on=["game_family", "quarter"],
        how="left",
        validate="many_to_one",
    )
    for policy, source_column in TARGET_COLUMNS.items():
        rows = comparison[comparison["target_policy"].eq(policy)]
        if not np.allclose(rows["actual_prize_pool_usd"], rows[source_column], equal_nan=True):
            raise ValueError(f"Actual không khớp nguồn cho policy {policy}")

    for frame_name, date_column in [
        ("quarterly", "period_start"),
        ("panel", "month_start"),
        ("predictions", "period_start"),
    ]:
        frames[frame_name][date_column] = pd.to_datetime(frames[frame_name][date_column], errors="raise")
    return release, frames


def build_tableau_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    """Chuyển dự báo sang bảng dài theo model để Tableau lọc đúng grain."""
    parts: list[pd.DataFrame] = []
    identifiers = [
        "game_family", "quarter", "period_start", "split", "target_policy",
        "actual_prize_pool_usd", "evaluation_available", "evaluation_status",
        "protocol",
    ]
    for model, prediction_column in MODEL_COLUMNS.items():
        part = predictions[identifiers].copy()
        part["model"] = model
        part["model_label"] = MODEL_LABELS[model]
        part["predicted_prize_pool_usd"] = predictions[prediction_column]
        part["residual_usd"] = part["actual_prize_pool_usd"] - part["predicted_prize_pool_usd"]
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

    export = pd.concat(parts, ignore_index=True).sort_values(
        ["target_policy", "model", "period_start", "game_family"]
    ).reset_index(drop=True)
    key = ["game_family", "quarter", "target_policy", "model"]
    if export.duplicated(key).any():
        raise ValueError(f"Bảng Tableau không duy nhất tại khóa {key}")
    if export["predicted_prize_pool_usd"].isna().any():
        raise ValueError("Bảng Tableau có prediction bị thiếu")
    return export


def build_tableau_summary(export: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp KPI Tableau theo policy, split, family và model."""
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
    """Xếp hạng sai số Random Forest theo độ lớn tuyệt đối."""
    errors = export[
        export["target_policy"].eq("source")
        & export["model"].eq("random_forest")
        & export["evaluation_available"]
    ].copy()
    errors = errors.sort_values("absolute_error_usd", ascending=False).reset_index(drop=True)
    errors.insert(0, "absolute_error_rank", np.arange(1, len(errors) + 1))
    errors["quarter_of_year"] = errors["quarter"].str[-2:]
    errors["absolute_error_share_pct"] = 100 * errors["absolute_error_usd"] / errors["absolute_error_usd"].sum()
    keep = [
        "absolute_error_rank", "game_family", "quarter", "quarter_of_year",
        "split", "actual_prize_pool_usd", "predicted_prize_pool_usd",
        "residual_usd", "absolute_error_usd", "absolute_error_share_pct",
        "error_direction",
    ]
    return errors[keep]


def aggregate_country_evidence(
    country_year: pd.DataFrame, coverage: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tổng hợp top quốc gia tuyển thủ và độ phủ tiền thưởng theo family."""
    country = country_year.groupby(
        ["game_family", "country_code", "country_name"], as_index=False
    )["prize_cents"].sum().sort_values(["game_family", "prize_cents"], ascending=[True, False])
    country["family_reconciled_prize_cents"] = country.groupby("game_family")["prize_cents"].transform("sum")
    country["share_of_family_reconciled_pct"] = 100 * country["prize_cents"] / country["family_reconciled_prize_cents"]
    top_countries = country.groupby("game_family", sort=False).head(5).copy()

    coverage_summary = coverage.groupby("game_family", as_index=False).agg(
        source_pool_cents=("source_pool_cents", "sum"),
        reconciled_pool_cents=("reconciled_pool_cents", "sum"),
    )
    coverage_summary["country_money_coverage_pct"] = 100 * coverage_summary["reconciled_pool_cents"] / coverage_summary["source_pool_cents"]
    return top_countries, coverage_summary


def build_evidence(
    quarterly: pd.DataFrame,
    panel: pd.DataFrame,
    correlations: pd.DataFrame,
    top_countries: pd.DataFrame,
    coverage_summary: pd.DataFrame,
    errors: pd.DataFrame,
) -> pd.DataFrame:
    """Tạo bảng bằng chứng truy vết cho các phát biểu storytelling."""
    rows: list[dict] = []
    totals = quarterly.groupby("game_family")["target_prize_pool_usd"].sum()
    peak_rows = quarterly.loc[quarterly.groupby("game_family")["target_prize_pool_usd"].idxmax()].set_index("game_family")
    pearson = correlations[correlations["method"].eq("pearson")].set_index("game_family")
    twitch = panel.groupby("game_family")["hours_watched"].agg(["count", "mean", "median"])
    top_one = top_countries.groupby("game_family", sort=False).head(1).set_index("game_family")
    coverage = coverage_summary.set_index("game_family")

    for family in FAMILIES:
        rows.extend(
            [
                {"story": "prize_structure", "game_family": family, "metric": "total_source_prize_pool_usd", "period": "all_observed", "value": totals[family], "unit": "USD", "source_file": "forecast_prize_quarterly.csv"},
                {"story": "prize_structure", "game_family": family, "metric": "peak_quarter_prize_pool_usd", "period": peak_rows.loc[family, "quarter"], "value": peak_rows.loc[family, "target_prize_pool_usd"], "unit": "USD", "source_file": "forecast_prize_quarterly.csv"},
                {"story": "twitch_prize_relationship", "game_family": family, "metric": "pearson_hours_vs_pool", "period": "matched_months", "value": pearson.loc[family, "hours_vs_pool"], "unit": "correlation", "source_file": "eda_correlations_descriptive.csv"},
                {"story": "twitch_prize_relationship", "game_family": family, "metric": "median_monthly_twitch_hours", "period": f"n={int(twitch.loc[family, 'count'])}", "value": twitch.loc[family, "median"], "unit": "hours", "source_file": "game_monthly_panel.csv"},
                {"story": "country_distribution", "game_family": family, "metric": f"top_country_{top_one.loc[family, 'country_code']}_share", "period": "all_observed", "value": top_one.loc[family, "share_of_family_reconciled_pct"], "unit": "percent", "source_file": "country_year.csv"},
                {"story": "country_distribution", "game_family": family, "metric": "country_money_coverage_pct", "period": "all_observed", "value": coverage.loc[family, "country_money_coverage_pct"], "unit": "percent", "source_file": "country_coverage.csv"},
            ]
        )

    for row in errors.head(10).itertuples():
        rows.append(
            {"story": "forecast_error", "game_family": row.game_family, "metric": "random_forest_absolute_error_usd", "period": row.quarter, "value": row.absolute_error_usd, "unit": "USD", "source_file": "model_predictions.csv"}
        )
    return pd.DataFrame(rows)


def validate_exports(
    predictions: pd.DataFrame, export: pd.DataFrame, summary: pd.DataFrame
) -> None:
    """Kiểm tra số dòng, actual và coverage trước khi bàn giao Tableau."""
    if len(export) != len(predictions) * len(MODEL_COLUMNS):
        raise ValueError("Số dòng bảng dự báo Tableau không đúng")
    expected_actual = predictions[["game_family", "quarter", "target_policy", "actual_prize_pool_usd"]].drop_duplicates()
    for model in MODEL_COLUMNS:
        model_actual = export[export["model"].eq(model)][["game_family", "quarter", "target_policy", "actual_prize_pool_usd"]]
        check = model_actual.merge(
            expected_actual,
            on=["game_family", "quarter", "target_policy"],
            suffixes=("_export", "_source"),
            validate="one_to_one",
        )
        if not np.allclose(check["actual_prize_pool_usd_export"], check["actual_prize_pool_usd_source"], equal_nan=True):
            raise ValueError(f"Actual không khớp cho model {model}")

    source_test = summary[
        summary["target_policy"].eq("source")
        & summary["split"].eq("test")
        & summary["game_family"].eq("Overall")
        & summary["model"].eq("random_forest")
    ]
    if len(source_test) != 1:
        raise ValueError("Thiếu dòng Overall source-test Random Forest duy nhất")
    row = source_test.iloc[0]
    if int(row["total_periods"]) != 16 or int(row["evaluated_periods"]) != 13:
        raise ValueError("Coverage source-test không đúng")


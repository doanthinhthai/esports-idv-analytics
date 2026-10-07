"""Chuẩn bị đặc trưng, huấn luyện và đánh giá các mô hình dự báo."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from phan_tich_esports.cau_hinh import FAMILIES, latest_release


TARGETS = {
    "source": "target_prize_pool_usd",
    "strict_quality": "strict_target_prize_pool_usd",
}
MODEL_LABELS = {
    "seasonal_naive": "Seasonal naive (t-4)",
    "linear_regression": "Linear regression",
    "random_forest": "Random forest",
}
NUMERIC_FEATURES = [
    "lag_1",
    "lag_2",
    "lag_4",
    "rolling_mean_4",
    "rolling_median_4",
    "rolling_std_4",
    "time_index",
]
CATEGORICAL_FEATURES = ["game_family", "quarter_of_year"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
RF_GRID = [
    {"max_depth": 4, "min_samples_leaf": 1, "max_features": "sqrt"},
    {"max_depth": 4, "min_samples_leaf": 2, "max_features": 0.8},
    {"max_depth": 8, "min_samples_leaf": 1, "max_features": "sqrt"},
    {"max_depth": 8, "min_samples_leaf": 2, "max_features": 0.8},
    {"max_depth": None, "min_samples_leaf": 1, "max_features": "sqrt"},
    {"max_depth": None, "min_samples_leaf": 2, "max_features": 0.8},
]


def load_quarterly_release() -> tuple[Path, pd.DataFrame, dict]:
    """Đọc bảng mục tiêu theo quý và xác nhận quy tắc chia tập theo thời gian."""
    release = latest_release()
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("stage") != "analysis_release_v1_policy_clean_not_source_verified":
        raise ValueError("Stage của release không phù hợp để huấn luyện mô hình")

    path = release / "forecast_prize_quarterly.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    data = pd.read_csv(path, encoding="utf-8-sig")
    required = {"game_family", "quarter", "period_start", "split", *TARGETS.values()}
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"Bảng theo quý thiếu cột: {missing}")
    if data.duplicated(["game_family", "quarter"]).any():
        raise ValueError("Trùng khóa game_family + quarter")
    if set(data["game_family"].dropna().unique()) != set(FAMILIES):
        raise ValueError("Danh sách game không đúng phạm vi")
    if not set(data["split"].dropna().unique()).issubset({"train", "validation", "test"}):
        raise ValueError("Có nhãn split không hợp lệ")

    data["period_start"] = pd.to_datetime(data["period_start"], errors="raise")
    data["quarter_of_year"] = data["period_start"].dt.quarter.astype(str)
    data = data.sort_values(["game_family", "period_start"]).reset_index(drop=True)
    expected_split = np.select(
        [data["period_start"].dt.year <= 2023, data["period_start"].dt.year == 2024],
        ["train", "validation"],
        default="test",
    )
    if not np.array_equal(data["split"].to_numpy(), expected_split):
        raise ValueError("Split phải là train đến 2023, validation 2024, test 2025")
    for target in TARGETS.values():
        if (data[target].dropna() < 0).any():
            raise ValueError(f"{target} chứa giá trị âm")
    return release, data, manifest


def add_lag_features(data: pd.DataFrame, target: str) -> pd.DataFrame:
    """Tạo lag và thống kê trượt chỉ từ các kỳ đã quan sát trước đó."""
    featured = data.copy()
    grouped = featured.groupby("game_family", sort=False)[target]
    featured["lag_1"] = grouped.shift(1)
    featured["lag_2"] = grouped.shift(2)
    featured["lag_4"] = grouped.shift(4)
    featured["rolling_mean_4"] = grouped.transform(lambda series: series.shift(1).rolling(4, min_periods=2).mean())
    featured["rolling_median_4"] = grouped.transform(lambda series: series.shift(1).rolling(4, min_periods=2).median())
    featured["rolling_std_4"] = grouped.transform(lambda series: series.shift(1).rolling(4, min_periods=2).std())
    featured["time_index"] = featured.groupby("game_family", sort=False).cumcount()
    return featured


def build_linear_pipeline() -> Pipeline:
    """Tạo pipeline hồi quy tuyến tính với chuẩn hóa và one-hot encoding."""
    preprocessing = ColumnTransformer(
        [
            ("numeric", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), NUMERIC_FEATURES),
            ("categorical", OneHotEncoder(handle_unknown="ignore", drop="first", sparse_output=False), CATEGORICAL_FEATURES),
        ],
        verbose_feature_names_out=False,
    )
    return Pipeline([("preprocessing", preprocessing), ("model", LinearRegression())])


def build_rf_pipeline(params: dict) -> Pipeline:
    """Tạo pipeline Random Forest theo bộ tham số được chọn."""
    preprocessing = ColumnTransformer(
        [
            ("numeric", SimpleImputer(strategy="median", add_indicator=True), NUMERIC_FEATURES),
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
        ],
        verbose_feature_names_out=False,
    )
    model = RandomForestRegressor(
        n_estimators=500,
        random_state=42,
        n_jobs=-1,
        criterion="squared_error",
        **params,
    )
    return Pipeline([("preprocessing", preprocessing), ("model", model)])


def clipped_predict(model: Pipeline, frame: pd.DataFrame) -> np.ndarray:
    """Dự báo và chặn giá trị âm vì quỹ thưởng không thể âm."""
    return np.maximum(model.predict(frame[FEATURES]), 0.0)


def tune_random_forest(featured: pd.DataFrame, target: str) -> tuple[dict, pd.DataFrame]:
    """Chọn tham số Random Forest theo RMSE validation."""
    train = featured[featured["split"].eq("train") & featured[target].notna() & featured["lag_4"].notna()]
    validation = featured[featured["split"].eq("validation") & featured[target].notna() & featured["lag_4"].notna()]
    if train.empty or validation.empty:
        raise ValueError(f"Không đủ dòng train hoặc validation cho {target}")

    rows: list[dict] = []
    for candidate_id, params in enumerate(RF_GRID, start=1):
        model = build_rf_pipeline(params)
        model.fit(train[FEATURES], train[target])
        prediction = clipped_predict(model, validation)
        rows.append(
            {
                "candidate_id": candidate_id,
                "target": target,
                "max_depth": "None" if params["max_depth"] is None else params["max_depth"],
                "min_samples_leaf": params["min_samples_leaf"],
                "max_features": params["max_features"],
                "validation_rows": len(validation),
                "validation_mae_usd": mean_absolute_error(validation[target], prediction),
                "validation_rmse_usd": math.sqrt(mean_squared_error(validation[target], prediction)),
            }
        )
    tuning = pd.DataFrame(rows).sort_values(["validation_rmse_usd", "validation_mae_usd", "candidate_id"])
    best_id = int(tuning.iloc[0]["candidate_id"])
    return RF_GRID[best_id - 1], tuning


def fit_and_predict_target(
    base: pd.DataFrame, policy: str, target: str
) -> tuple[pd.DataFrame, Pipeline, Pipeline, pd.DataFrame]:
    """Huấn luyện ba mô hình và dự báo rolling one-step cho một target policy."""
    featured = add_lag_features(base, target)
    best_rf_params, tuning = tune_random_forest(featured, target)
    output_parts: list[pd.DataFrame] = []
    final_linear: Pipeline | None = None
    final_rf: Pipeline | None = None

    for split in ["validation", "test"]:
        train_splits = ["train"] if split == "validation" else ["train", "validation"]
        fit_rows = featured[featured["split"].isin(train_splits) & featured[target].notna() & featured["lag_4"].notna()]
        predict_rows = featured[featured["split"].eq(split) & featured["lag_4"].notna()].copy()
        if fit_rows.empty or predict_rows.empty:
            raise ValueError(f"Không đủ dữ liệu cho {policy} {split}")

        linear = build_linear_pipeline()
        forest = build_rf_pipeline(best_rf_params)
        linear.fit(fit_rows[FEATURES], fit_rows[target])
        forest.fit(fit_rows[FEATURES], fit_rows[target])
        predict_rows["target_policy"] = policy
        predict_rows["actual_prize_pool_usd"] = predict_rows[target]
        predict_rows["prediction_seasonal_naive"] = np.maximum(predict_rows["lag_4"], 0.0)
        predict_rows["prediction_linear_regression"] = clipped_predict(linear, predict_rows)
        predict_rows["prediction_random_forest"] = clipped_predict(forest, predict_rows)
        for model_name in MODEL_LABELS:
            predict_rows[f"residual_{model_name}"] = predict_rows["actual_prize_pool_usd"] - predict_rows[f"prediction_{model_name}"]
        predict_rows["evaluation_available"] = predict_rows["actual_prize_pool_usd"].notna()
        predict_rows["evaluation_status"] = np.where(predict_rows["evaluation_available"], "evaluated", "target_missing_prediction_only")
        predict_rows["protocol"] = "rolling_one_step"
        output_parts.append(predict_rows)
        if split == "test":
            final_linear = linear
            final_rf = forest

    assert final_linear is not None and final_rf is not None
    predictions = pd.concat(output_parts, ignore_index=True)
    keep = [
        "game_family", "quarter", "period_start", "split", "target_policy",
        "actual_prize_pool_usd", "prediction_seasonal_naive",
        "prediction_linear_regression", "prediction_random_forest",
        "residual_seasonal_naive", "residual_linear_regression",
        "residual_random_forest", "evaluation_available", "evaluation_status",
        "protocol",
    ]
    return predictions[keep], final_linear, final_rf, tuning


def score_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    """Tính MAE, RMSE, R² và coverage cho từng mô hình, split, family."""
    rows: list[dict] = []
    for policy in TARGETS:
        for split in ["validation", "test"]:
            split_data = predictions[predictions["target_policy"].eq(policy) & predictions["split"].eq(split)]
            for family in [*FAMILIES, "Overall"]:
                group = split_data if family == "Overall" else split_data[split_data["game_family"].eq(family)]
                evaluated = group[group["evaluation_available"]].copy()
                for model_name, model_label in MODEL_LABELS.items():
                    actual = evaluated["actual_prize_pool_usd"]
                    predicted = evaluated[f"prediction_{model_name}"]
                    rows.append(
                        {
                            "target_policy": policy,
                            "split": split,
                            "game_family": family,
                            "model": model_name,
                            "model_label": model_label,
                            "n_evaluated": len(evaluated),
                            "n_total_periods": len(group),
                            "coverage_pct": 100 * len(evaluated) / len(group) if len(group) else np.nan,
                            "mae_usd": mean_absolute_error(actual, predicted) if len(evaluated) else np.nan,
                            "rmse_usd": math.sqrt(mean_squared_error(actual, predicted)) if len(evaluated) else np.nan,
                            "r2_diagnostic": r2_score(actual, predicted) if len(evaluated) >= 4 else np.nan,
                            "protocol": "rolling_one_step",
                        }
                    )
    return pd.DataFrame(rows)


def quality_sensitivity(base: pd.DataFrame) -> pd.DataFrame:
    """So sánh tổng target nguồn với target strict-quality theo split."""
    eligible_parts: list[pd.DataFrame] = []
    for family in FAMILIES:
        family_data = base[base["game_family"].eq(family)].copy()
        first_observed = family_data.loc[family_data["target_prize_pool_usd"].notna(), "period_start"].min()
        eligible_parts.append(family_data[family_data["period_start"].ge(first_observed)])
    eligible_base = pd.concat(eligible_parts, ignore_index=True)

    rows: list[dict] = []
    for split in ["train", "validation", "test"]:
        split_data = eligible_base[eligible_base["split"].eq(split)]
        for family in [*FAMILIES, "Overall"]:
            group = split_data if family == "Overall" else split_data[split_data["game_family"].eq(family)]
            source = group["target_prize_pool_usd"].sum(min_count=1)
            strict = group["strict_target_prize_pool_usd"].sum(min_count=1)
            observed = int(group["target_prize_pool_usd"].notna().sum())
            rows.append(
                {
                    "split": split,
                    "game_family": family,
                    "total_periods": len(group),
                    "source_observed_periods": observed,
                    "missing_source_periods": int(group["target_prize_pool_usd"].isna().sum()),
                    "source_prize_pool_usd": source,
                    "strict_prize_pool_usd": strict,
                    "strict_share_of_source_pct": 100 * strict / source if pd.notna(source) and source != 0 else np.nan,
                }
            )
    return pd.DataFrame(rows)


def extract_model_diagnostics(
    linear: Pipeline, forest: Pipeline
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Trích hệ số Linear Regression và importance của Random Forest."""
    linear_names = linear.named_steps["preprocessing"].get_feature_names_out()
    coefficients = linear.named_steps["model"].coef_
    coefficient_table = pd.DataFrame(
        {"feature": linear_names, "coefficient": coefficients, "absolute_coefficient": np.abs(coefficients)}
    ).sort_values("absolute_coefficient", ascending=False)

    forest_names = forest.named_steps["preprocessing"].get_feature_names_out()
    importances = forest.named_steps["model"].feature_importances_
    importance_table = pd.DataFrame(
        {"feature": forest_names, "importance": importances}
    ).sort_values("importance", ascending=False)
    return coefficient_table, importance_table


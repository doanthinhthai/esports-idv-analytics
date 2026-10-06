# -*- coding: utf-8 -*-
"""Day-2 quarterly prize-pool forecasting benchmarks.

The script uses only the newest ``analysis_release_v1_*`` folder and compares
seasonal naive, linear regression, and random forest models. Validation uses
2024, test uses 2025, and every prediction is rolling one-step: earlier
observed values in the same evaluation split may be used as lag features.

Run from any directory with::

    python src/model.py
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
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


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


def load_quarterly_release() -> tuple[Path, pd.DataFrame, dict]:
    release = latest_release()
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("stage") != "analysis_release_v1_policy_clean_not_source_verified":
        raise ValueError("Unexpected release stage; review its policy before modeling")

    path = release / "forecast_prize_quarterly.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    data = pd.read_csv(path, encoding="utf-8-sig")
    required = {
        "game_family",
        "quarter",
        "period_start",
        "split",
        *TARGETS.values(),
    }
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"Quarterly release is missing columns: {missing}")
    if data.duplicated(["game_family", "quarter"]).any():
        raise ValueError("Duplicate game_family + quarter rows")
    if set(data["game_family"].dropna().unique()) != set(FAMILIES):
        raise ValueError("Game families do not match the approved scope")
    if not set(data["split"].dropna().unique()).issubset({"train", "validation", "test"}):
        raise ValueError("Unexpected split label")

    data["period_start"] = pd.to_datetime(data["period_start"], errors="raise")
    data["quarter_of_year"] = data["period_start"].dt.quarter.astype(str)
    data = data.sort_values(["game_family", "period_start"]).reset_index(drop=True)

    expected_split = np.select(
        [data["period_start"].dt.year <= 2023, data["period_start"].dt.year == 2024],
        ["train", "validation"],
        default="test",
    )
    if not np.array_equal(data["split"].to_numpy(), expected_split):
        raise ValueError("Split labels do not match train through 2023, validation 2024, test 2025")
    for target in TARGETS.values():
        if (data[target].dropna() < 0).any():
            raise ValueError(f"{target} contains a negative value")
    return release, data, manifest


def add_lag_features(data: pd.DataFrame, target: str) -> pd.DataFrame:
    featured = data.copy()
    grouped = featured.groupby("game_family", sort=False)[target]
    featured["lag_1"] = grouped.shift(1)
    featured["lag_2"] = grouped.shift(2)
    featured["lag_4"] = grouped.shift(4)
    featured["rolling_mean_4"] = grouped.transform(
        lambda series: series.shift(1).rolling(4, min_periods=2).mean()
    )
    featured["rolling_median_4"] = grouped.transform(
        lambda series: series.shift(1).rolling(4, min_periods=2).median()
    )
    featured["rolling_std_4"] = grouped.transform(
        lambda series: series.shift(1).rolling(4, min_periods=2).std()
    )
    featured["time_index"] = featured.groupby("game_family", sort=False).cumcount()
    return featured


def build_linear_pipeline() -> Pipeline:
    preprocessing = ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                NUMERIC_FEATURES,
            ),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", drop="first", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
        ],
        verbose_feature_names_out=False,
    )
    return Pipeline(
        [("preprocessing", preprocessing), ("model", LinearRegression())]
    )


def build_rf_pipeline(params: dict) -> Pipeline:
    preprocessing = ColumnTransformer(
        [
            (
                "numeric",
                SimpleImputer(strategy="median", add_indicator=True),
                NUMERIC_FEATURES,
            ),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
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
    return np.maximum(model.predict(frame[FEATURES]), 0.0)


def tune_random_forest(featured: pd.DataFrame, target: str) -> tuple[dict, pd.DataFrame]:
    train = featured[featured["split"].eq("train") & featured[target].notna() & featured["lag_4"].notna()]
    validation = featured[featured["split"].eq("validation") & featured[target].notna() & featured["lag_4"].notna()]
    if train.empty or validation.empty:
        raise ValueError(f"Insufficient train or validation rows for {target}")

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
    tuning = pd.DataFrame(rows).sort_values(
        ["validation_rmse_usd", "validation_mae_usd", "candidate_id"]
    )
    best_id = int(tuning.iloc[0]["candidate_id"])
    return RF_GRID[best_id - 1], tuning


def fit_and_predict_target(
    base: pd.DataFrame, policy: str, target: str
) -> tuple[pd.DataFrame, Pipeline, Pipeline, pd.DataFrame]:
    featured = add_lag_features(base, target)
    best_rf_params, tuning = tune_random_forest(featured, target)
    output_parts: list[pd.DataFrame] = []
    final_linear: Pipeline | None = None
    final_rf: Pipeline | None = None

    for split in ["validation", "test"]:
        train_splits = ["train"] if split == "validation" else ["train", "validation"]
        fit_rows = featured[
            featured["split"].isin(train_splits)
            & featured[target].notna()
            & featured["lag_4"].notna()
        ]
        predict_rows = featured[
            featured["split"].eq(split) & featured["lag_4"].notna()
        ].copy()
        if fit_rows.empty or predict_rows.empty:
            raise ValueError(f"Insufficient rows for {policy} {split}")

        linear = build_linear_pipeline()
        forest = build_rf_pipeline(best_rf_params)
        linear.fit(fit_rows[FEATURES], fit_rows[target])
        forest.fit(fit_rows[FEATURES], fit_rows[target])

        predict_rows["target_policy"] = policy
        predict_rows["actual_prize_pool_usd"] = predict_rows[target]
        predict_rows["prediction_seasonal_naive"] = np.maximum(
            predict_rows["lag_4"], 0.0
        )
        predict_rows["prediction_linear_regression"] = clipped_predict(
            linear, predict_rows
        )
        predict_rows["prediction_random_forest"] = clipped_predict(
            forest, predict_rows
        )
        for model_name in MODEL_LABELS:
            predict_rows[f"residual_{model_name}"] = (
                predict_rows["actual_prize_pool_usd"]
                - predict_rows[f"prediction_{model_name}"]
            )
        predict_rows["evaluation_available"] = predict_rows[
            "actual_prize_pool_usd"
        ].notna()
        predict_rows["evaluation_status"] = np.where(
            predict_rows["evaluation_available"],
            "evaluated",
            "target_missing_prediction_only",
        )
        predict_rows["protocol"] = "rolling_one_step"
        output_parts.append(predict_rows)
        if split == "test":
            final_linear = linear
            final_rf = forest

    assert final_linear is not None and final_rf is not None
    predictions = pd.concat(output_parts, ignore_index=True)
    keep = [
        "game_family",
        "quarter",
        "period_start",
        "split",
        "target_policy",
        "actual_prize_pool_usd",
        "prediction_seasonal_naive",
        "prediction_linear_regression",
        "prediction_random_forest",
        "residual_seasonal_naive",
        "residual_linear_regression",
        "residual_random_forest",
        "evaluation_available",
        "evaluation_status",
        "protocol",
    ]
    return predictions[keep], final_linear, final_rf, tuning


def score_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for policy in TARGETS:
        for split in ["validation", "test"]:
            split_data = predictions[
                predictions["target_policy"].eq(policy)
                & predictions["split"].eq(split)
            ]
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
    eligible_parts: list[pd.DataFrame] = []
    for family in FAMILIES:
        family_data = base[base["game_family"].eq(family)].copy()
        first_observed = family_data.loc[
            family_data["target_prize_pool_usd"].notna(), "period_start"
        ].min()
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
    linear_names = linear.named_steps["preprocessing"].get_feature_names_out()
    coefficients = linear.named_steps["model"].coef_
    coefficient_table = pd.DataFrame(
        {
            "feature": linear_names,
            "coefficient": coefficients,
            "absolute_coefficient": np.abs(coefficients),
        }
    ).sort_values("absolute_coefficient", ascending=False)

    forest_names = forest.named_steps["preprocessing"].get_feature_names_out()
    importances = forest.named_steps["model"].feature_importances_
    importance_table = pd.DataFrame(
        {"feature": forest_names, "importance": importances}
    ).sort_values("importance", ascending=False)
    return coefficient_table, importance_table


def style_axis(ax: plt.Axes) -> None:
    ax.grid(True, color="#D9D9D9", alpha=0.55, linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)


def save_figure(fig: plt.Figure, filename: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / filename, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def millions(value: float, _: int) -> str:
    return f"${value / 1_000_000:.1f}M"


def plot_actual_vs_predicted(predictions: pd.DataFrame) -> None:
    data = predictions[
        predictions["target_policy"].eq("source")
        & predictions["split"].eq("test")
        & predictions["evaluation_available"]
    ]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), sharex=True, sharey=True)
    maximum = max(
        data["actual_prize_pool_usd"].max(),
        data[[f"prediction_{name}" for name in MODEL_LABELS]].max().max(),
    )
    limit = maximum * 1.08
    for ax, (name, label) in zip(axes, MODEL_LABELS.items()):
        for family in FAMILIES:
            group = data[data["game_family"].eq(family)]
            ax.scatter(
                group["actual_prize_pool_usd"],
                group[f"prediction_{name}"],
                s=65,
                alpha=0.85,
                color=COLORS[family],
                label=family,
            )
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
    data = metrics[
        metrics["target_policy"].eq("source")
        & metrics["game_family"].eq("Overall")
    ].copy()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    x = np.arange(len(MODEL_LABELS))
    width = 0.36
    for ax, metric, title in zip(axes, ["mae_usd", "rmse_usd"], ["MAE", "RMSE"]):
        for offset, split, color in [(-width / 2, "validation", "#2F5597"), (width / 2, "test", "#D1495B")]:
            values = (
                data[data["split"].eq(split)]
                .set_index("model")
                .loc[list(MODEL_LABELS), metric]
                .to_numpy()
            )
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
    data = predictions[
        predictions["target_policy"].eq("source")
        & predictions["split"].eq("test")
        & predictions["evaluation_available"]
    ].copy()
    data = data.sort_values(["period_start", "game_family"])
    fig, ax = plt.subplots(figsize=(13, 6.5))
    for family in FAMILIES:
        group = data[data["game_family"].eq(family)]
        ax.scatter(
            group["period_start"],
            group[f"residual_{primary_model}"],
            s=75,
            color=COLORS[family],
            label=family,
            alpha=0.9,
        )
    ax.axhline(0, color="#555555", linestyle="--", linewidth=1.3)
    ax.yaxis.set_major_formatter(FuncFormatter(millions))
    ax.set_ylabel("Actual minus predicted prize pool")
    ax.set_xlabel("2025 quarter")
    ax.set_title(f"Test residuals: {MODEL_LABELS[primary_model]}", loc="left", fontsize=17, fontweight="bold")
    ax.legend(frameon=False, ncol=2)
    style_axis(ax)
    fig.tight_layout()
    save_figure(fig, "model_residuals.png")


def write_notes(
    release: Path,
    metrics: pd.DataFrame,
    tuning: pd.DataFrame,
    predictions: pd.DataFrame,
    primary_model: str,
) -> None:
    overall = metrics[
        metrics["target_policy"].eq("source")
        & metrics["game_family"].eq("Overall")
    ].copy()
    validation = overall[overall["split"].eq("validation")].set_index("model")
    test = overall[overall["split"].eq("test")].set_index("model")
    selected_tuning = (
        tuning[tuning["target"].eq("target_prize_pool_usd")]
        .sort_values(["validation_rmse_usd", "validation_mae_usd"])
        .iloc[0]
    )
    missing = predictions[
        predictions["target_policy"].eq("source")
        & predictions["split"].eq("test")
        & ~predictions["evaluation_available"]
    ]
    missing_label = ", ".join(
        f"{row.game_family} {row.quarter}" for row in missing.itertuples()
    )

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


def main() -> None:
    release, base, _ = load_quarterly_release()
    all_predictions: list[pd.DataFrame] = []
    all_tuning: list[pd.DataFrame] = []
    source_linear: Pipeline | None = None
    source_forest: Pipeline | None = None

    for policy, target in TARGETS.items():
        predictions, linear, forest, tuning = fit_and_predict_target(
            base, policy, target
        )
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
    print(f"Primary model: {MODEL_LABELS[primary_model]}")
    print(f"Validation RMSE: {selected['rmse_usd']:,.2f} USD")
    print("Wrote model tables, notes, and four 300-DPI figures under reports/.")


if __name__ == "__main__":
    main()

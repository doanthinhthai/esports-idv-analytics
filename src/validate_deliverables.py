# -*- coding: utf-8 -*-
"""Validate the final Member-C deliverables and write auditable results."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
REPORTS_DIR = PROJECT_DIR / "reports"

FAMILIES = {"Counter-Strike", "Dota 2", "League of Legends", "Valorant"}
MISSING_SOURCE_TEST = {
    ("League of Legends", "2025Q4"),
    ("Valorant", "2025Q2"),
    ("Valorant", "2025Q4"),
}


def latest_release() -> Path:
    candidates = sorted(
        path
        for path in PROCESSED_DIR.glob("analysis_release_v1_*")
        if path.is_dir() and (path / "manifest.json").exists()
    )
    if not candidates:
        raise FileNotFoundError("No analysis_release_v1_* release found")
    return candidates[-1]


def main() -> None:
    checks: list[dict[str, str]] = []

    def record(check_id: str, category: str, passed: bool, detail: str) -> None:
        checks.append(
            {
                "check_id": check_id,
                "category": category,
                "status": "PASS" if passed else "FAIL",
                "detail": detail,
            }
        )

    release = latest_release()
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    record(
        "release_stage",
        "source",
        manifest.get("stage") == "analysis_release_v1_policy_clean_not_source_verified",
        str(manifest.get("stage")),
    )

    required_release = [
        "tournaments.csv",
        "placements.csv",
        "forecast_prize_quarterly.csv",
        "game_monthly_panel.csv",
        "country_coverage.csv",
        "eda_correlations_descriptive.csv",
    ]
    missing_release = [name for name in required_release if not (release / name).exists()]
    record(
        "release_files",
        "source",
        not missing_release,
        "all required release files present" if not missing_release else str(missing_release),
    )

    required_outputs = [
        REPORTS_DIR / "eda_summary.csv",
        REPORTS_DIR / "model_predictions.csv",
        REPORTS_DIR / "model_metrics.csv",
        REPORTS_DIR / "model_feature_importance.csv",
        REPORTS_DIR / "storytelling_insights.md",
        REPORTS_DIR / "tableau_forecast_handoff.md",
        PROCESSED_DIR / "tableau_forecast_predictions.csv",
        PROCESSED_DIR / "tableau_forecast_summary.csv",
    ]
    missing_outputs = [str(path.relative_to(PROJECT_DIR)) for path in required_outputs if not path.exists()]
    record(
        "pipeline_outputs",
        "output",
        not missing_outputs,
        "all pipeline outputs present" if not missing_outputs else str(missing_outputs),
    )

    quarterly = pd.read_csv(release / "forecast_prize_quarterly.csv", encoding="utf-8-sig")
    model_predictions = pd.read_csv(REPORTS_DIR / "model_predictions.csv", encoding="utf-8-sig")
    model_metrics = pd.read_csv(REPORTS_DIR / "model_metrics.csv", encoding="utf-8-sig")
    tableau_predictions = pd.read_csv(
        PROCESSED_DIR / "tableau_forecast_predictions.csv", encoding="utf-8-sig"
    )
    tableau_summary = pd.read_csv(
        PROCESSED_DIR / "tableau_forecast_summary.csv", encoding="utf-8-sig"
    )

    record(
        "quarterly_key",
        "grain",
        not quarterly.duplicated(["game_family", "quarter"]).any(),
        f"rows={len(quarterly)}",
    )
    record(
        "model_prediction_key",
        "grain",
        not model_predictions.duplicated(
            ["game_family", "quarter", "target_policy"]
        ).any(),
        f"rows={len(model_predictions)}; expected=64",
    )
    tableau_key = ["game_family", "quarter", "target_policy", "model"]
    record(
        "tableau_prediction_key",
        "grain",
        len(tableau_predictions) == 192
        and not tableau_predictions.duplicated(tableau_key).any(),
        f"rows={len(tableau_predictions)}; expected=192",
    )
    summary_key = ["target_policy", "split", "game_family", "model"]
    record(
        "tableau_summary_key",
        "grain",
        len(tableau_summary) == 60
        and not tableau_summary.duplicated(summary_key).any(),
        f"rows={len(tableau_summary)}; expected=60",
    )

    missing = model_predictions[
        model_predictions["target_policy"].eq("source")
        & model_predictions["split"].eq("test")
        & ~model_predictions["evaluation_available"]
    ]
    missing_keys = set(zip(missing["game_family"], missing["quarter"]))
    missing_residual_columns = [
        "residual_seasonal_naive",
        "residual_linear_regression",
        "residual_random_forest",
    ]
    record(
        "missing_target_policy",
        "missing",
        missing_keys == MISSING_SOURCE_TEST
        and missing["actual_prize_pool_usd"].isna().all()
        and missing[missing_residual_columns].isna().all().all(),
        f"missing={sorted(missing_keys)}",
    )

    prediction_columns = [
        "prediction_seasonal_naive",
        "prediction_linear_regression",
        "prediction_random_forest",
    ]
    record(
        "nonnegative_predictions",
        "model",
        model_predictions[prediction_columns].notna().all().all()
        and (model_predictions[prediction_columns] >= 0).all().all(),
        "all model predictions present and non-negative",
    )

    comparison = tableau_predictions.merge(
        quarterly[
            [
                "game_family",
                "quarter",
                "target_prize_pool_usd",
                "strict_target_prize_pool_usd",
            ]
        ],
        on=["game_family", "quarter"],
        how="left",
        validate="many_to_one",
    )
    source_rows = comparison[comparison["target_policy"].eq("source")]
    strict_rows = comparison[comparison["target_policy"].eq("strict_quality")]
    actual_reconciles = np.allclose(
        source_rows["actual_prize_pool_usd"],
        source_rows["target_prize_pool_usd"],
        equal_nan=True,
    ) and np.allclose(
        strict_rows["actual_prize_pool_usd"],
        strict_rows["strict_target_prize_pool_usd"],
        equal_nan=True,
    )
    record(
        "actual_reconciliation",
        "reconciliation",
        actual_reconciles,
        "Tableau actual values reconcile to quarterly targets for both policies",
    )

    metric_check = tableau_summary.merge(
        model_metrics,
        on=["target_policy", "split", "game_family", "model"],
        suffixes=("_tableau", "_model"),
        validate="one_to_one",
    )
    metrics_reconcile = (
        len(metric_check) == 60
        and np.allclose(metric_check["mae_usd_tableau"], metric_check["mae_usd_model"])
        and np.allclose(metric_check["rmse_usd_tableau"], metric_check["rmse_usd_model"])
    )
    record(
        "metric_reconciliation",
        "reconciliation",
        metrics_reconcile,
        f"matched_rows={len(metric_check)}; expected=60",
    )

    source_test = tableau_summary[
        tableau_summary["target_policy"].eq("source")
        & tableau_summary["split"].eq("test")
        & tableau_summary["game_family"].eq("Overall")
        & tableau_summary["model"].eq("random_forest")
    ]
    coverage_ok = (
        len(source_test) == 1
        and int(source_test.iloc[0]["total_periods"]) == 16
        and int(source_test.iloc[0]["evaluated_periods"]) == 13
        and np.isclose(source_test.iloc[0]["coverage_pct"], 81.25)
    )
    record(
        "source_test_coverage",
        "evaluation",
        coverage_ok,
        "source + random_forest + test expects 13 evaluated of 16 periods",
    )

    required_figures = [
        *[FIGURES for FIGURES in (REPORTS_DIR / "figures").glob("eda_*.png")],
        *[FIGURES for FIGURES in (REPORTS_DIR / "figures").glob("model_*.png")],
        *[FIGURES for FIGURES in (REPORTS_DIR / "figures").glob("story_*.png")],
    ]
    dpi_failures: list[str] = []
    for path in required_figures:
        with Image.open(path) as image:
            dpi = image.info.get("dpi", (0, 0))[0]
        if dpi < 295:
            dpi_failures.append(f"{path.name}:{dpi}")
    record(
        "figure_inventory",
        "figure",
        len(required_figures) == 13 and not dpi_failures,
        f"figures={len(required_figures)}; dpi_failures={dpi_failures}",
    )

    required_documents = [
        REPORTS_DIR / "chapters" / "ch5_modeling.md",
        REPORTS_DIR / "chapters" / "ch6_implementation.md",
        REPORTS_DIR / "chapters" / "ch7_conclusion.md",
        PROJECT_DIR / "demo" / "video_script.md",
        PROJECT_DIR / "demo" / "defense_faq.md",
        REPORTS_DIR / "final_integration_checklist.md",
    ]
    missing_documents = [
        str(path.relative_to(PROJECT_DIR)) for path in required_documents if not path.exists()
    ]
    record(
        "report_package",
        "documentation",
        not missing_documents,
        "all report/demo documents present" if not missing_documents else str(missing_documents),
    )

    prohibited_tokens = ["TODO", "TBD", "[INSERT", "<INSERT", "PLACEHOLDER"]
    token_hits: list[str] = []
    for path in required_documents:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").upper()
        for token in prohibited_tokens:
            if token in text:
                token_hits.append(f"{path.name}:{token}")
    record(
        "placeholder_scan",
        "documentation",
        not token_hits,
        "no placeholder tokens" if not token_hits else str(token_hits),
    )

    tournaments = pd.read_csv(release / "tournaments.csv", encoding="utf-8-sig")
    placements = pd.read_csv(release / "placements.csv", encoding="utf-8-sig")
    correlations = pd.read_csv(
        release / "eda_correlations_descriptive.csv", encoding="utf-8-sig"
    )
    country_coverage = pd.read_csv(
        release / "country_coverage.csv", encoding="utf-8-sig"
    )
    errors = pd.read_csv(
        REPORTS_DIR / "storytelling_error_analysis.csv", encoding="utf-8-sig"
    )
    overall_metrics = model_metrics[
        model_metrics["target_policy"].eq("source")
        & model_metrics["game_family"].eq("Overall")
    ].set_index(["split", "model"])
    pearson = correlations[correlations["method"].eq("pearson")].set_index(
        "game_family"
    )
    country_pct = (
        100
        * country_coverage["reconciled_pool_cents"].sum()
        / country_coverage["source_pool_cents"].sum()
    )
    error_total = errors["absolute_error_usd"].sum()
    q4_share = (
        100
        * errors.loc[errors["quarter_of_year"].eq("Q4"), "absolute_error_usd"].sum()
        / error_total
    )
    dota_share = (
        100
        * errors.loc[errors["game_family"].eq("Dota 2"), "absolute_error_usd"].sum()
        / error_total
    )
    def relative(path: Path) -> str:
        return path.relative_to(PROJECT_DIR).as_posix()

    traceability = pd.DataFrame(
        [
            ["release_tournaments", "Tournament rows", len(tournaments), "rows", relative(release / "tournaments.csv"), "all rows"],
            ["release_placements", "Placement rows", len(placements), "rows", relative(release / "placements.csv"), "all rows"],
            ["total_source_prize", "Observed source prize pool", quarterly["target_prize_pool_usd"].sum(), "USD", relative(release / "forecast_prize_quarterly.csv"), "all observed family-quarter rows"],
            ["rf_validation_rmse", "Random Forest validation RMSE", overall_metrics.loc[("validation", "random_forest"), "rmse_usd"], "USD", relative(REPORTS_DIR / "model_metrics.csv"), "source, validation, Overall, random_forest"],
            ["rf_test_rmse", "Random Forest test RMSE", overall_metrics.loc[("test", "random_forest"), "rmse_usd"], "USD", relative(REPORTS_DIR / "model_metrics.csv"), "source, test, Overall, random_forest"],
            ["naive_test_rmse", "Seasonal Naive test RMSE", overall_metrics.loc[("test", "seasonal_naive"), "rmse_usd"], "USD", relative(REPORTS_DIR / "model_metrics.csv"), "source, test, Overall, seasonal_naive"],
            ["dota_pearson", "Dota 2 Twitch-hours vs prize Pearson", pearson.loc["Dota 2", "hours_vs_pool"], "correlation", relative(release / "eda_correlations_descriptive.csv"), "Dota 2, pearson"],
            ["country_coverage", "Overall country money coverage", country_pct, "percent", relative(release / "country_coverage.csv"), "weighted overall"],
            ["q4_error_share", "Q4 share of Random Forest absolute error", q4_share, "percent", relative(REPORTS_DIR / "storytelling_error_analysis.csv"), "source random_forest validation+test"],
            ["dota_error_share", "Dota 2 share of Random Forest absolute error", dota_share, "percent", relative(REPORTS_DIR / "storytelling_error_analysis.csv"), "source random_forest validation+test"],
        ],
        columns=["claim_id", "claim", "value", "unit", "source_file", "filter_or_scope"],
    )
    traceability["value"] = traceability.apply(
        lambda row: round(row["value"], 0)
        if row["unit"] == "rows"
        else round(row["value"], 2)
        if row["unit"] == "USD"
        else round(row["value"], 6),
        axis=1,
    )

    results = pd.DataFrame(checks)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    results.to_csv(
        REPORTS_DIR / "final_validation_results.csv", index=False, encoding="utf-8-sig"
    )
    traceability.to_csv(
        REPORTS_DIR / "report_traceability.csv", index=False, encoding="utf-8-sig"
    )

    failed = results[results["status"].eq("FAIL")]
    summary_lines = [
        "# Final validation summary",
        "",
        f"- Release: `{release.name}`.",
        f"- Checks passed: **{int((results['status'] == 'PASS').sum())}/{len(results)}**.",
        f"- Checks failed: **{len(failed)}**.",
        "- Tableau workbook checks remain manual and are tracked in `final_integration_checklist.md`.",
        "",
        "## Results",
        "",
        "| Check | Category | Status | Detail |",
        "|---|---|---|---|",
    ]
    for row in results.itertuples():
        detail = str(row.detail).replace("|", "/")
        summary_lines.append(
            f"| {row.check_id} | {row.category} | {row.status} | {detail} |"
        )
    (REPORTS_DIR / "final_validation_summary.md").write_text(
        "\n".join(summary_lines) + "\n", encoding="utf-8"
    )

    print(f"Release: {release.name}")
    print(f"Checks passed: {(results['status'] == 'PASS').sum()}/{len(results)}")
    if len(failed):
        print("Failed checks:")
        for row in failed.itertuples():
            print(f"- {row.check_id}: {row.detail}")
        raise SystemExit(1)
    print("All automated deliverable checks passed.")


if __name__ == "__main__":
    main()

# Final validation summary

- Release: `analysis_release_v1_20261005T194400349609Z`.
- Checks passed: **15/15**.
- Checks failed: **0**.
- Tableau workbook checks remain manual and are tracked in `final_integration_checklist.md`.

## Results

| Check | Category | Status | Detail |
|---|---|---|---|
| release_stage | source | PASS | analysis_release_v1_policy_clean_not_source_verified |
| release_files | source | PASS | all required release files present |
| pipeline_outputs | output | PASS | all pipeline outputs present |
| quarterly_key | grain | PASS | rows=224 |
| model_prediction_key | grain | PASS | rows=64; expected=64 |
| tableau_prediction_key | grain | PASS | rows=192; expected=192 |
| tableau_summary_key | grain | PASS | rows=60; expected=60 |
| missing_target_policy | missing | PASS | missing=[('League of Legends', '2025Q4'), ('Valorant', '2025Q2'), ('Valorant', '2025Q4')] |
| nonnegative_predictions | model | PASS | all model predictions present and non-negative |
| actual_reconciliation | reconciliation | PASS | Tableau actual values reconcile to quarterly targets for both policies |
| metric_reconciliation | reconciliation | PASS | matched_rows=60; expected=60 |
| source_test_coverage | evaluation | PASS | source + random_forest + test expects 13 evaluated of 16 periods |
| figure_inventory | figure | PASS | figures=13; dpi_failures=[] |
| report_package | documentation | PASS | all report/demo documents present |
| placeholder_scan | documentation | PASS | no placeholder tokens |

# Day 2 model evaluation notes

## Scope and protocol

- Release: `analysis_release_v1_20261005T194400349609Z`.
- Target grain: game family–quarter.
- Train: through 2023. Validation: 2024. Test: 2025.
- Protocol: rolling one-step. Earlier observed validation/test targets may become lag features for later quarters in the same split.
- Predictions are clipped at zero because prize pools cannot be negative.
- The primary model is selected by overall source-target validation RMSE before inspecting the test score.

## Source-target performance (USD)

| Model | Validation MAE | Validation RMSE | Test MAE | Test RMSE |
|---|---:|---:|---:|---:|
| Seasonal naive (t-4) | 1,303,145 | 2,194,181 | 1,845,569 | 2,410,869 |
| Linear regression | 2,014,934 | 2,980,558 | 2,925,854 | 3,995,387 |
| Random forest | 1,419,040 | 1,976,568 | 1,818,034 | 2,511,323 |

Selected primary model: **Random forest**. Validation RMSE is **1,976,568 USD** and test RMSE on observed rows is **2,511,323 USD**.

The selected random-forest setting for the source target is `max_depth=4`, `min_samples_leaf=1` and `max_features=sqrt`. The random forest is still reported even when another benchmark wins validation.

## Missing target and coverage

The source-target test score uses **13 of 16** available family-quarter rows. Missing test targets remain blank and are excluded from all metrics: Valorant 2025Q2, League of Legends 2025Q4, Valorant 2025Q4. Their predictions are retained for Tableau with `evaluation_status=target_missing_prediction_only`.

## Interpretation limits

- This release is policy-clean but source coverage is not fully verified. A forecast error can reflect source completeness as well as market behavior.
- Seasonal naive, linear regression and random forest use only lagged prize data, rolling statistics, time and quarter/family indicators. Current-quarter tournament count, placements, prize fields and Twitch values are excluded to prevent leakage.
- The strict-quality target is a sensitivity analysis, not a substitute for source verification.
- R² is diagnostic only and is blank for family-level groups with fewer than four evaluated rows.
- Impurity importance can favor continuous variables and does not establish causality.

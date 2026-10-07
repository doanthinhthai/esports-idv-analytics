# Tableau forecast handoff

## Files and grain

### `data/processed/tableau_forecast_predictions.csv`

- Row grain: `game_family + quarter + target_policy + model`.
- Rows: 192.
- Default dashboard filters: `target_policy = source`, `model = random_forest`.
- Within one selected target policy and model, the visible grain is one row per family-quarter.
- `actual_prize_pool_usd` remains blank when the target is missing; `predicted_prize_pool_usd` is still available.

### `data/processed/tableau_forecast_summary.csv`

- Row grain: `target_policy + split + game_family + model`.
- Rows: 60.
- Includes family rows and `Overall` rows for KPI cards.
- `predicted_prize_pool_usd_evaluated` uses only periods with an actual target; `predicted_prize_pool_usd_all_periods` also includes prediction-only periods.

Both files come from `analysis_release_v1_20261005T194400349609Z` and Day-2 model outputs.

## Relationship design

Use the prediction export as a standalone fact table for the forecast sheets. If a quarter or game dimension is available, relate it many-to-one on `game_family + quarter`. Do not physically join predictions to placements, tournaments or country rows. Those are one-to-many tables and would repeat actual and predicted prize values.

Keep the country map on its reconciled country data source. Use dashboard filters or a shared game-family dimension to coordinate views instead of joining forecast rows to player-country rows.

## Required filters

1. `target_policy`: single value. Default `source`; expose `strict_quality` as sensitivity.
2. `model`: single value. Default `random_forest`; allow comparison with `seasonal_naive` and `linear_regression`.
3. `split`: validation or test.
4. `game_family`: optional multi-select.

If users select several models, actual values repeat once per model. Keep the model filter single-select for KPI totals. For a comparison view, use `MIN(actual_prize_pool_usd)` at family-quarter-policy grain or a FIXED LOD instead of summing actual across models.

## Field definitions

| Field | Definition | Tableau use |
|---|---|---|
| `actual_prize_pool_usd` | Observed target for the selected policy | Line, point or tooltip; keep missing as null |
| `predicted_prize_pool_usd` | Model prediction, clipped at zero | Forecast line or scatter axis |
| `residual_usd` | Actual minus predicted | Positive means underprediction; negative means overprediction |
| `absolute_error_usd` | Absolute residual | Error magnitude |
| `evaluation_available` | Actual exists for scoring | Filter metrics to `True` |
| `evaluation_status` | `evaluated` or `target_missing_prediction_only` | Missing-target warning |
| `coverage_pct` | Evaluated periods divided by total periods | KPI context |
| `is_primary_model` | Random Forest flag | Default model selection |

## Recommended sheets

### Actual vs predicted trend

- Columns: `period_start` as continuous quarter.
- Rows: Measure Values for actual and predicted.
- Color: Measure Names.
- Detail or small multiples: `game_family`.
- Show validation and test through `split`; retain null actual marks as prediction-only.

### Actual vs predicted scatter

- Columns: `actual_prize_pool_usd`.
- Rows: `predicted_prize_pool_usd`.
- Color: `game_family`.
- Filter: `evaluation_available = True`.
- Add a reference line `y = x`.

### Residual review

- Columns: `period_start`.
- Rows: `residual_usd`.
- Color: `error_direction`.
- Add a zero reference line.
- Tooltip: family, quarter, actual, predicted, residual, policy, model and evaluation status.

### KPI cards

Use `tableau_forecast_summary.csv` and show MAE, RMSE, coverage and evaluated periods. Do not average family RMSE values to create Overall RMSE; use the supplied `Overall` row.

## Missing-target treatment

For the source target, the test view evaluates 13 of 16 family-quarter rows. League of Legends 2025Q4, Valorant 2025Q2 and Valorant 2025Q4 have predictions but no actual target. Display them as `Prediction only — target missing`; do not convert null actual or residual to zero.

## Validation checklist

- Prediction key is unique at `game_family + quarter + target_policy + model`.
- With filters `source + random_forest + test`, expect 16 rows, 13 evaluated rows and three prediction-only rows.
- Actual totals must be checked with one model selected.
- Never sum actual or predicted values after joining to tournament, placement or country detail.
- Label country fields as player country and show country-money coverage.
- Recommendations may describe sponsorship-priority signals or pilot allocation, not ROI.

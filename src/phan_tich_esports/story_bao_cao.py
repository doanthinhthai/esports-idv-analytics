"""Ghi insight và hướng dẫn kỹ thuật bàn giao Tableau."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from phan_tich_esports.cau_hinh import FAMILIES, REPORTS_DIR


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Chuyển danh sách dữ liệu sang bảng Markdown."""
    output = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] + ["---:"] * (len(headers) - 1)) + "|",
    ]
    output.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(output)


def write_storytelling_insights(
    release: Path,
    quarterly: pd.DataFrame,
    panel: pd.DataFrame,
    correlations: pd.DataFrame,
    top_countries: pd.DataFrame,
    coverage_summary: pd.DataFrame,
    errors: pd.DataFrame,
) -> None:
    """Ghi ba câu chuyện dữ liệu, giới hạn và hành động đề xuất."""
    totals = quarterly.groupby("game_family")["target_prize_pool_usd"].sum()
    peaks = quarterly.loc[quarterly.groupby("game_family")["target_prize_pool_usd"].idxmax()].set_index("game_family")
    prize_rows = [
        [family, f"{totals[family] / 1_000_000:,.2f}", str(peaks.loc[family, "quarter"]), f"{peaks.loc[family, 'target_prize_pool_usd'] / 1_000_000:,.2f}"]
        for family in FAMILIES
    ]

    pearson = correlations[correlations["method"].eq("pearson")].set_index("game_family")
    twitch = panel.groupby("game_family")["hours_watched"].agg(["count", "median"])
    twitch_rows = [
        [family, str(int(pearson.loc[family, "n"])), f"{pearson.loc[family, 'hours_vs_pool']:.3f}", f"{twitch.loc[family, 'median'] / 1_000_000:,.1f}"]
        for family in FAMILIES
    ]

    top_one = top_countries.groupby("game_family", sort=False).head(1).set_index("game_family")
    coverage = coverage_summary.set_index("game_family")
    country_rows = [
        [family, str(top_one.loc[family, "country_name"]), f"{top_one.loc[family, 'prize_cents'] / 100 / 1_000_000:,.2f}", f"{top_one.loc[family, 'share_of_family_reconciled_pct']:.1f}%", f"{coverage.loc[family, 'country_money_coverage_pct']:.1f}%"]
        for family in FAMILIES
    ]

    error_rows = [
        [str(row.game_family), str(row.quarter), str(row.split), f"{row.actual_prize_pool_usd / 1_000_000:,.2f}", f"{row.predicted_prize_pool_usd / 1_000_000:,.2f}", f"{row.residual_usd / 1_000_000:,.2f}"]
        for row in errors.head(8).itertuples()
    ]
    q4_share = 100 * errors.loc[errors["quarter_of_year"].eq("Q4"), "absolute_error_usd"].sum() / errors["absolute_error_usd"].sum()
    dota_share = 100 * errors.loc[errors["game_family"].eq("Dota 2"), "absolute_error_usd"].sum() / errors["absolute_error_usd"].sum()
    overall_coverage = 100 * coverage_summary["reconciled_pool_cents"].sum() / coverage_summary["source_pool_cents"].sum()

    content = f"""# Storytelling insights and actions

## Scope

Evidence comes from `{release.name}` and the Day-2 rolling one-step model outputs. The release is policy-clean but source coverage is not fully verified. All prize values are nominal USD.

## Forecast error analysis

{markdown_table(["Family", "Quarter", "Split", "Actual (USD M)", "Random Forest (USD M)", "Residual (USD M)"], error_rows)}

Residual is actual minus predicted. Negative values mean overprediction. The largest errors cluster around sudden reversals: Dota 2 2024Q3 was overpredicted by about 5.68 million USD, Counter-Strike 2025Q4 by 5.59 million USD and Dota 2 2025Q4 by 5.54 million USD. Q4 accounts for {q4_share:.1f}% of total Random-Forest absolute error across evaluated validation and test rows; Dota 2 accounts for {dota_share:.1f}%.

**Interpretation.** Lag-based models react slowly when a high-prize seasonal pattern is followed by a sharp decline. The source coverage of 2025 is still unverified, so a large residual can reflect collection coverage as well as a real market change.

**Action.** Use the forecast as a quarterly planning range and keep a manual review flag for Dota 2 and Q4. Do not turn the point forecast into a guaranteed sponsorship budget.

Supporting figure: `reports/figures/story_04_forecast_error_concentration.png`.

## Story 1 — Prize-pool scale and seasonality

{markdown_table(["Family", "Observed total (USD M)", "Peak quarter", "Peak prize (USD M)"], prize_rows)}

Dota 2 has the largest observed prize pool, about {totals['Dota 2'] / 1_000_000:,.2f} million USD, and the largest quarterly spike: {peaks.loc['Dota 2', 'quarter']} at {peaks.loc['Dota 2', 'target_prize_pool_usd'] / 1_000_000:,.2f} million USD. In train data, Dota 2 also has its strongest median seasonal level in Q3. Counter-Strike has a smaller total but a less extreme quarterly scale.

**Limit.** The low 2025 counts must not be presented as evidence that the E-sports market contracted. The release does not certify complete source coverage for 2025.

**Action.** Treat Dota 2 as a high-scale, high-volatility sponsorship signal. Use staged budget approval around major-event quarters. Use Counter-Strike as a separate, steadier comparison rather than pooling both into one budget rule.

Supporting figure: `reports/figures/story_01_prize_structure.png`.

## Story 2 — Twitch attention and prize pools move differently

{markdown_table(["Family", "Matched months", "Pearson r", "Median Twitch hours (M)"], twitch_rows)}

Dota 2 has the strongest descriptive association between monthly Twitch hours and prize pools, with Pearson `r={pearson.loc['Dota 2', 'hours_vs_pool']:.3f}`. The equivalent correlations for Counter-Strike, League of Legends and Valorant are close to zero. League of Legends has the highest median monthly Twitch hours, about {twitch.loc['League of Legends', 'median'] / 1_000_000:,.1f} million, even though its prize-pool total is below Dota 2 and Counter-Strike.

**Limit.** Twitch data is the main game category, not tournament-only viewing, ends in September 2024 and excludes YouTube. Correlation does not establish that higher prize money causes more viewing.

**Action.** Use Twitch attention and prize scale as separate screening dimensions. For a pilot allocation, compare audience reach, prize volatility and data coverage before negotiating campaign cost. Do not call this an ROI calculation.

Supporting figure: `reports/figures/story_02_twitch_prize_relationship.png`.

## Story 3 — Player-country prize concentration

{markdown_table(["Family", "Top player country", "Prize (USD M)", "Share of reconciled family prize", "Money coverage"], country_rows)}

The top player countries differ by family: Denmark for Counter-Strike, China for Dota 2, Korea for League of Legends and the United States for Valorant. Country tables reconcile {overall_coverage:.2f}% of source prize money overall, but family coverage ranges from {coverage_summary['country_money_coverage_pct'].min():.1f}% to {coverage_summary['country_money_coverage_pct'].max():.1f}%.

**Limit.** Country refers to player country in reconciled prize records. It does not represent audience location, tournament location or the complete global market.

**Action.** Use this view to localize player-led content or shortlist ambassador markets. Always show the coverage percentage in the same dashboard view and validate audience geography separately before buying regional media.

Supporting figure: `reports/figures/story_03_country_distribution.png`.

## Permitted recommendation language

- Use `sponsorship-priority signal`, `pilot allocation` or `market for further validation`.
- State the target policy, model, evaluation coverage and source-coverage warning beside the recommendation.
- Do not state ROI, causal impact or guaranteed market growth because revenue, sponsorship cost and profit are not in the dataset.
"""
    (REPORTS_DIR / "storytelling_insights.md").write_text(content, encoding="utf-8")


def write_tableau_handoff(
    release: Path, export: pd.DataFrame, summary: pd.DataFrame
) -> None:
    """Ghi grain, relationship, filter và quy tắc kiểm tra Tableau."""
    source_test = export[
        export["target_policy"].eq("source")
        & export["model"].eq("random_forest")
        & export["split"].eq("test")
    ]
    content = f"""# Tableau forecast handoff

## Files and grain

### `data/processed/tableau_forecast_predictions.csv`

- Row grain: `game_family + quarter + target_policy + model`.
- Rows: {len(export):,}.
- Default dashboard filters: `target_policy = source`, `model = random_forest`.
- Within one selected target policy and model, the visible grain is one row per family-quarter.
- `actual_prize_pool_usd` remains blank when the target is missing; `predicted_prize_pool_usd` is still available.

### `data/processed/tableau_forecast_summary.csv`

- Row grain: `target_policy + split + game_family + model`.
- Rows: {len(summary):,}.
- Includes family rows and `Overall` rows for KPI cards.
- `predicted_prize_pool_usd_evaluated` uses only periods with an actual target; `predicted_prize_pool_usd_all_periods` also includes prediction-only periods.

Both files come from `{release.name}` and Day-2 model outputs.

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

For the source target, the test view evaluates {int(source_test['evaluation_available'].sum())} of {len(source_test)} family-quarter rows. League of Legends 2025Q4, Valorant 2025Q2 and Valorant 2025Q4 have predictions but no actual target. Display them as `Prediction only — target missing`; do not convert null actual or residual to zero.

## Validation checklist

- Prediction key is unique at `game_family + quarter + target_policy + model`.
- With filters `source + random_forest + test`, expect 16 rows, 13 evaluated rows and three prediction-only rows.
- Actual totals must be checked with one model selected.
- Never sum actual or predicted values after joining to tournament, placement or country detail.
- Label country fields as player country and show country-money coverage.
- Recommendations may describe sponsorship-priority signals or pilot allocation, not ROI.
"""
    (REPORTS_DIR / "tableau_forecast_handoff.md").write_text(content, encoding="utf-8")


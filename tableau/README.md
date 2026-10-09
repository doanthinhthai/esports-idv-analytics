# Esports Analytics Tableau Dashboards

This directory contains the production Tableau workbook and documentation for the Esports Analytics project.

- **Primary Workbook:** `EsportAnalyst (FullVersion).twbx` (Compatible with Tableau Desktop and Tableau Public).
- **Embedded Data Sources:** `analytics_rows.csv`, `tableau_forecast_timeline.csv`, `tableau_backtest_metrics.csv`.

---

## 1. Dashboards Overview

The workbook contains three dedicated dashboards providing descriptive, diagnostic, and predictive insights:

### Dashboard 1: Executive Overview
* **Audience:** C-Level Executives, Portfolio Managers, and Head of Sponsorships.
* **Core Views:**
  * **KPI Cards:** Strict-quality Tournament Count (~11.6k), Total Prize Pool (~$745.1M observed total / ~$600.3M strict), Total Twitch Hours Watched, Active Player Countries.
  * **Tournament Prize Trend:** Annual worldwide prize money trajectory (2012–2025).
  * **Total Prize by Country (Choropleth Map):** Geographical distribution of player-country reconciled prize earnings.
  * **Top Tournaments by Prize:** Leaderboard of historical mega-events (e.g., The International editions, PGL Majors, Worlds).
  * **Genre Prize Share:** Breakdown between MOBA and Tactical FPS titles.
* **Interactivity:** Country, Year, and Game filters cross-filter connected views.

### Dashboard 2: Regional & Game Deep-Dive
* **Audience:** Tournament Organizers, Regional Expansion Teams, and Esports Data Analysts.
* **Core Views:**
  * **Game Prize Leaderboard & Volume Bars:** Comparative breakdown of tournament count and prize pool across the four game families (*Counter-Strike*, *Dota 2*, *League of Legends*, *Valorant*).
  * **Game Share Treemap:** Hierarchical visualization of game dominance within genre clusters.
  * **Game Trends over Years:** Multi-year growth and stabilization patterns across title lifecycles.
  * **Regional Game Heatmap:** Regional tournament concentration across global competitive zones.
* **Interactivity:** Dynamic click-to-filter actions across genre, game, and region dimensions.

### Dashboard 3: Predictive Simulator
* **Audience:** Strategic Planners, Budget Committees, and Data Science Evaluators.
* **Core Views:**
  * **Forecast Timeline & Interval:** Continuous quarterly timeline (2012–2025 historical actuals) connected to the 4-quarter rolling out-of-sample forecast (2026Q1–2026Q4) produced by trained ML pipelines. Features an **80% Prediction Interval Band** (Gantt Bar overlay on dual axis).
  * **Next Quarter KPI Card:** Point estimate for the upcoming immediate quarter (2026Q1) with model status.
  * **Full Year Forecast Pool Card:** Aggregate 4-quarter projected prize pool with 80% reference range.
  * **Holdout RMSE Card:** Out-of-sample backtest root-mean-squared error evaluated strictly on holdout quarters (`horizon_quarters = 0`, `evaluation_phase = holdout`).
  * **Model Evaluation Benchmark:** Multi-model comparative horizontal bar chart comparing *Random Forest* (primary model), *Seasonal Naive* (baseline), and *Linear Regression*.
  * **Scenario Simulator Card:** Interactive scenario planning card driven by user-adjusted multipliers.
* **Parameters & Interactive Controls:**
  * `Prize Multiplier`: Slider (`0.5x` to `2.0x`, step `0.1`, default `1.0x`) for scenario stress-testing.
  * `Horizon_Quarters`: Parameter selector (`1`, `2`, `4` quarters) controlling forecast visibility.
  * `Model Selection`: Single-select selector (`random_forest`, `linear_regression`, `seasonal_naive`).
  * `Game Family Filter`: Single-select dropdown coordinating all simulator cards and timelines.

---

## 2. Data Architecture & `Record Type` Integrity

The primary data source `analytics_rows.csv` is a consolidated analytical export. To prevent severe row duplication and metric distortion, each dashboard sheet applies strict **`Record Type`** filtering:

| Record Type | Rows in Source | Total Prize USD in Source | Dashboard Usage |
|---|---:|---:|---|
| **`Tournament`** | 14,082 | **$745,131,235** | **Mandatory for all prize, tournament count, and ranking views** (Dashboards 1 & 2). Prevents duplicate row aggregation. |
| **`Country Prize`** | 3,203 | $727,753,426 | **World Map (Choropleth)** only. Contains reconciled player-country codes. |
| **`Twitch Monthly`** | 369 | $0 | **Twitch Viewership views**. Captures monthly game-category hours and average viewers. |
| **`Quarterly Forecast`** | 191 | $745,131,235 | Quarterly aggregation table. |
| **`Radial`** | 76 | $11,095,595,745 | Geometry/polygon rows used strictly for circular coordinate calculations. |
| **`Boxplot`** | 4 | $0 | Precomputed summary statistics for distributional reference. |
| **`Correlation`** | 16 | $0 | Descriptive Pearson/Spearman coefficient matrix. |

> [!CAUTION]
> Summing the unpartitioned `Prize USD` column without filtering `Record Type = Tournament` results in a distorted aggregate of **$13.31 Billion**. All production worksheets in this workbook are partitioned with explicit record-type boundaries.

---

## 3. Calculations, LODs & Parameter Implementation

The workbook incorporates custom Tableau Level of Detail (LOD) and business calculations:

### Forecasting & Intervals (`tableau_forecast_timeline.csv`)
* **`[Band_Size_80]`**:
  ```tableau
  IF [record_type] = "forecast" THEN
      [upper_80_usd] - [lower_80_usd]
  ELSE
      NULL
  END
  ```
  *Mapped to the Size shelf of `SUM(lower_80_usd)` (Mark type: Gantt Bar) on a synchronized dual axis, ensuring prediction bounds only render across the 4 forecast quarters.*
* **`[Filter_Horizon_View]`**:
  ```tableau
  [record_type] <> "forecast" OR [horizon_quarters] <= [Horizon_Quarters]
  ```

### Scenario Simulator
* **`[Baseline Quarterly Prize]`**:
  ```tableau
  { FIXED [game_family] : AVG(
      IF [record_type] = "historical" AND NOT ISNULL([actual_prize_pool_usd]) 
      THEN [actual_prize_pool_usd] 
      END
  ) }
  ```
* **`[Simulated Quarterly Prize]`**:
  ```tableau
  [Baseline Quarterly Prize] * [Prize Multiplier]
  ```
* **`[Scenario Delta]`**:
  ```tableau
  [Simulated Quarterly Prize] - [Baseline Quarterly Prize]
  ```
  *Aggregated via `AVG` rather than `SUM` to guarantee idempotency across replicated dimension rows.*

### Evaluation Metrics (`tableau_backtest_metrics.csv`)
* Evaluated at `evaluation_phase = "holdout"` and `horizon_quarters = 0` (aggregate 4-quarter holdout window).
* Aggregated via `AVG(rmse_usd)` and `AVG(interval_coverage_pct)` for individual games or filtered to `game_family = "Overall"` for global benchmarks.

---

## 4. Benchmark Validation Reference

For quality verification when auditing the workbook, verified benchmark values are:

### Counter-Strike (CS / CS2)
* **Next Quarter (2026Q1):** `$5,392,377 USD`
* **Full Year 2026 Forecast (Sum 4 Quarters):** `$18,603,620.48 USD`
* **80% Interval Range (Full Year Sum):** `$9,119,571 – $28,087,670 USD`
* **Holdout RMSE (Random Forest):** `$2,816,869 USD` (Coverage: `75.0%`)

### Overall (All Games Combined)
* **Next Quarter 2026Q1 (Sum 4 Games):** `$16,018,724 USD`
* **Holdout Benchmark RMSE (Overall Row):**
  * *Random Forest:* `$2,514,241 USD`
  * *Seasonal Naive:* `$2,410,869 USD`
  * *Linear Regression:* `$3,920,547 USD`

---

## 5. Methodological Notes & Analytical Boundaries

1. **Non-Causal Interpretation:** Correlation between monthly Twitch watch hours and quarterly prize pools is purely descriptive (*Dota 2* $r = 0.698$, *CS* $r = 0.042$, *LoL* $r = 0.050$, *Valorant* $r = 0.024$). Prize pool expansions do not mechanically cause viewership growth.
2. **Grain Separation:** Twitch metrics represent entire game categories on Twitch (including variety and casual streamers), not tournament-exclusive airtime. Per-tournament viewership or ROI calculation is strictly unsupported by the dataset grain.
3. **Player Country vs. Audience Country:** Choropleth maps represent the verified nationality of prizewinning players, not spectator geography or tournament host cities.
4. **Coverage Caveat:** Data for 2025 is policy-cleaned but reflects partial annual collection at source cutoff; missing quarters are preserved as `NULL` without synthetic zero-imputation.

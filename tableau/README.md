# Esports analytics Tableau dashboards

Open `Esports_Analytics_Dashboards.twbx` in Tableau Desktop or Tableau Public. The workbook embeds its CSV data source.

## Dashboards

- **Executive Summary** — strict-quality tournament count and prize pool, annual worldwide strict tournament prize trend, Twitch monthly reach, country prize choropleth, and genre prize donut. Selecting a country or genre on the map filters the other views where the shared fields match.
- **Regional & Game Deep-dive** — grouped prize bars, a Twitch views/hours scatter, game prize treemap, native Tableau box-and-whisker plot by game, event-level prize distribution, tournament-count bars by game, and Pearson correlation matrix. Click genre/game marks to filter and use the `Genre → Game → Tournament` hierarchy to drill to events.
- **Predictive Simulator** — baseline quarterly prize predictions versus held-out targets, plus a scenario card. Select a game on the forecast chart and adjust the prize and audience multipliers.

The grouped game bar includes a **Viz in Tooltip** with the selected game's annual prize history.

## Measures and assumptions

The workbook includes these Tableau LOD calculations:

- `Tournament Prize LOD` fixes the tournament prize at Genre, Game, and Tournament.
- `Game Prize LOD` fixes total tournament prize at Genre and Game.
- `Historical Avg Prize per Tournament` fixes average tournament pool at Game.
- `Baseline Avg Viewers` fixes historical monthly average viewers at Game.

The scenario card estimates a new event as the selected game's historical average tournament prize and monthly average viewers, each multiplied by the dashboard parameter. These are adjustable baseline scenarios, not a trained event-level forecast. The forecast line uses the supplied quarterly baseline predictions and observed targets.

## Data notes

The workbook uses the `analysis_release_v1_20261005T194400349609Z` release under `data/processed/`. The tournament KPI and prize visuals use records flagged `strict_quality`; the world map uses the release's reconciled country-year prize table; the correlation matrix uses the release's Pearson descriptive coefficients. Genre groups are derived from game family (MOBA or Tactical FPS). Regions use an ISO-code grouping; tournament regions are populated only when the last location component resolves to a country in the country-year data.

The release manifest says final source coverage is not verified. Treat its figures as an analysis release, not a fully source-verified census.

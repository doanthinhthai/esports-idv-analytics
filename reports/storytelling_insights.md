# Storytelling insights and actions

## Scope

Evidence comes from `analysis_release_v1_20261005T194400349609Z` and the Day-2 rolling one-step model outputs. The release is policy-clean but source coverage is not fully verified. All prize values are nominal USD.

## Forecast error analysis

| Family | Quarter | Split | Actual (USD M) | Random Forest (USD M) | Residual (USD M) |
|---|---:|---:|---:|---:|---:|
| Dota 2 | 2024Q3 | validation | 9.50 | 15.19 | -5.68 |
| Counter-Strike | 2025Q4 | test | 0.66 | 6.24 | -5.59 |
| Dota 2 | 2025Q4 | test | 1.00 | 6.54 | -5.54 |
| League of Legends | 2024Q4 | validation | 0.52 | 3.29 | -2.77 |
| League of Legends | 2025Q1 | test | 1.27 | 3.85 | -2.59 |
| Dota 2 | 2024Q2 | validation | 3.80 | 6.35 | -2.56 |
| Dota 2 | 2025Q3 | test | 5.88 | 8.02 | -2.14 |
| Valorant | 2024Q4 | validation | 0.78 | 2.60 | -1.82 |

Residual is actual minus predicted. Negative values mean overprediction. The largest errors cluster around sudden reversals: Dota 2 2024Q3 was overpredicted by about 5.68 million USD, Counter-Strike 2025Q4 by 5.59 million USD and Dota 2 2025Q4 by 5.54 million USD. Q4 accounts for 36.6% of total Random-Forest absolute error across evaluated validation and test rows; Dota 2 accounts for 42.3%.

**Interpretation.** Lag-based models react slowly when a high-prize seasonal pattern is followed by a sharp decline. The source coverage of 2025 is still unverified, so a large residual can reflect collection coverage as well as a real market change.

**Action.** Use the forecast as a quarterly planning range and keep a manual review flag for Dota 2 and Q4. Do not turn the point forecast into a guaranteed sponsorship budget.

Supporting figure: `reports/figures/story_04_forecast_error_concentration.png`.

## Story 1 — Prize-pool scale and seasonality

| Family | Observed total (USD M) | Peak quarter | Peak prize (USD M) |
|---|---:|---:|---:|
| Counter-Strike | 208.57 | 2021Q4 | 7.91 |
| Dota 2 | 380.57 | 2021Q4 | 42.19 |
| League of Legends | 121.38 | 2018Q4 | 7.15 |
| Valorant | 34.61 | 2023Q3 | 2.77 |

Dota 2 has the largest observed prize pool, about 380.57 million USD, and the largest quarterly spike: 2021Q4 at 42.19 million USD. In train data, Dota 2 also has its strongest median seasonal level in Q3. Counter-Strike has a smaller total but a less extreme quarterly scale.

**Limit.** The low 2025 counts must not be presented as evidence that the E-sports market contracted. The release does not certify complete source coverage for 2025.

**Action.** Treat Dota 2 as a high-scale, high-volatility sponsorship signal. Use staged budget approval around major-event quarters. Use Counter-Strike as a separate, steadier comparison rather than pooling both into one budget rule.

Supporting figure: `reports/figures/story_01_prize_structure.png`.

## Story 2 — Twitch attention and prize pools move differently

| Family | Matched months | Pearson r | Median Twitch hours (M) |
|---|---:|---:|---:|
| Counter-Strike | 105 | 0.042 | 47.3 |
| Dota 2 | 105 | 0.698 | 41.2 |
| League of Legends | 105 | 0.050 | 99.0 |
| Valorant | 53 | 0.024 | 83.8 |

Dota 2 has the strongest descriptive association between monthly Twitch hours and prize pools, with Pearson `r=0.698`. The equivalent correlations for Counter-Strike, League of Legends and Valorant are close to zero. League of Legends has the highest median monthly Twitch hours, about 99.0 million, even though its prize-pool total is below Dota 2 and Counter-Strike.

**Limit.** Twitch data is the main game category, not tournament-only viewing, ends in September 2024 and excludes YouTube. Correlation does not establish that higher prize money causes more viewing.

**Action.** Use Twitch attention and prize scale as separate screening dimensions. For a pilot allocation, compare audience reach, prize volatility and data coverage before negotiating campaign cost. Do not call this an ROI calculation.

Supporting figure: `reports/figures/story_02_twitch_prize_relationship.png`.

## Story 3 — Player-country prize concentration

| Family | Top player country | Prize (USD M) | Share of reconciled family prize | Money coverage |
|---|---:|---:|---:|---:|
| Counter-Strike | Denmark | 25.95 | 12.7% | 97.6% |
| Dota 2 | China | 86.11 | 22.8% | 99.2% |
| League of Legends | Korea, Republic of | 40.41 | 35.9% | 92.9% |
| Valorant | United States | 5.80 | 17.1% | 98.2% |

The top player countries differ by family: Denmark for Counter-Strike, China for Dota 2, Korea for League of Legends and the United States for Valorant. Country tables reconcile 97.67% of source prize money overall, but family coverage ranges from 92.9% to 99.2%.

**Limit.** Country refers to player country in reconciled prize records. It does not represent audience location, tournament location or the complete global market.

**Action.** Use this view to localize player-led content or shortlist ambassador markets. Always show the coverage percentage in the same dashboard view and validate audience geography separately before buying regional media.

Supporting figure: `reports/figures/story_03_country_distribution.png`.

## Permitted recommendation language

- Use `sponsorship-priority signal`, `pilot allocation` or `market for further validation`.
- State the target policy, model, evaluation coverage and source-coverage warning beside the recommendation.
- Do not state ROI, causal impact or guaranteed market growth because revenue, sponsorship cost and profit are not in the dataset.

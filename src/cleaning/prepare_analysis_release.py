"""Offline, reproducible analysis release and descriptive EDA."""
import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

from lxml import html
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def money(value):
    n = Decimal(str(value).replace("$", "").replace(",", "").strip()) * 100
    if not n.is_finite() or n < 0 or n != n.to_integral_value():
        raise ValueError("invalid_money")
    return int(n)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--earnings", type=Path, required=True)
    parser.add_argument("--twitch", type=Path, required=True)
    parser.add_argument("--panel", type=Path, required=True)
    args = parser.parse_args()
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = ROOT / "data/processed" / ("analysis_release_v1_" + run)
    out.mkdir(parents=True, exist_ok=False)
    eda = out / "eda"
    eda.mkdir()
    sources = [args.earnings / "tournaments_clean.csv", args.earnings / "placements_clean.csv",
               args.twitch / "game_monthly_primary.csv", args.panel / "game_monthly_panel.csv"]
    t, p, w, panel = [pd.read_csv(f, encoding="utf-8-sig") for f in sources]
    checks = []
    def require(name, condition):
        checks.append({"check": name, "passed": bool(condition)})
        if not condition:
            raise ValueError(name)
    def save(name, frame):
        frame.to_csv(out / name, index=False, encoding="utf-8-sig")
    require("tournament_key", t.tournament_id.notna().all() and t.tournament_id.is_unique)
    require("placement_key", p.placement_id.notna().all() and p.placement_id.is_unique)
    require("placement_parent", p.tournament_id.isin(t.tournament_id).all())
    require("twitch_key", not w.duplicated(["game_family", "month_start"]).any())
    require("panel_key_count", len(panel) == len(w) and not panel.duplicated(["game_family", "month_start"]).any())
    t["pool_cents"] = t.prize_pool_usd.map(money)
    p["prize_cents"] = p.prize_money_usd.map(money)
    t["start_date"] = pd.to_datetime(t.start_date, errors="raise")
    ends = pd.to_datetime(t.end_date, errors="raise")
    require("dates", t.start_date.le(ends).all() and t.start_date.between("2012-01-01", "2025-12-31").all())
    require("families", set(t.game_family) == set(w.game_family))
    t["strict_quality"] = t.quality_note.fillna("").eq("") & t.eligible_for_placement_prize_analysis.eq(True)
    t["month_start"] = t.start_date.dt.strftime("%Y-%m-01")
    t["quarter"] = t.start_date.dt.to_period("Q").astype(str)
    totals = p.groupby("tournament_id").prize_cents.sum()
    reconciled = t[t.eligible_for_placement_prize_analysis]
    require("placement_totals", ((reconciled.tournament_id.map(totals) - reconciled.pool_cents).abs() <= 2).all())
    p = p.merge(t[["tournament_id", "strict_quality"]], on="tournament_id", validate="many_to_one")
    save("tournaments.csv", t)
    save("placements.csv", p)
    save("twitch_monthly.csv", w)
    save("game_monthly_panel.csv", panel)
    for name in ["quarantine.csv", "out_of_scope.csv"]:
        save("earnings_" + name, pd.read_csv(args.earnings / name, encoding="utf-8-sig"))
    save("twitch_quarantine.csv", pd.read_csv(args.twitch / "quarantine.csv", encoding="utf-8-sig"))
    save("twitch_supplementary.csv", pd.read_csv(args.twitch / "counter_strike_supplementary.csv", encoding="utf-8-sig"))

    # Full cached country audit. Identity is player-country, never viewer-country.
    country_rows, country_audit, country_candidates = [], [], []
    raw_root = (ROOT / "data/raw/esportsearnings").resolve()
    def load_cached(row):
        path = (raw_root / row.source_html_file).resolve()
        try:
            if not path.is_relative_to(raw_root):
                raise ValueError("unsafe_html_path")
            return path, path.read_bytes(), None
        except (ValueError, OSError) as exc:
            return path, None, str(exc)
    def prefetched_rows():
        # Bounded queue: at most 32 HTML documents retained, no network requests.
        iterator = iter(t.itertuples())
        with ThreadPoolExecutor(max_workers=8) as executor:
            pending = deque()
            for _ in range(32):
                row = next(iterator, None)
                if row is None:
                    break
                pending.append((row, executor.submit(load_cached, row)))
            while pending:
                row, future = pending.popleft()
                yield row, future.result()
                next_row = next(iterator, None)
                if next_row is not None:
                    pending.append((next_row, executor.submit(load_cached, next_row)))
    for i, (r, loaded) in enumerate(prefetched_rows(), 1):
        path, payload, read_error = loaded
        records = []
        status, error = "unavailable", ""
        try:
            if read_error:
                raise ValueError(read_error)
            tree = html.fromstring(payload)
            headers = tree.xpath('//main//h2[normalize-space(.)="Prize Money By Country"]')
            if len(headers) != 1:
                raise ValueError("missing_or_ambiguous_country_heading")
            for sibling in headers[0].itersiblings():
                if sibling.tag == "h2":
                    break
                for row in sibling.xpath('.//tr[contains(concat(" ",normalize-space(@class)," ")," format_row ")]'):
                    cells = row.xpath('./td')
                    if len(cells) != 4:
                        raise ValueError("country_table_structure")
                    links = cells[1].xpath('.//a[starts-with(@href,"/countries/")]')
                    if not links:
                        raise ValueError("country_link_missing")
                    code = links[0].get("href").rstrip("/").split("/")[-1].upper()
                    if not re.fullmatch(r"[A-Z]{2}", code):
                        raise ValueError("country_code_invalid")
                    count = re.fullmatch(r"(\d+)\s+Players?", cells[3].text_content().strip())
                    if not count:
                        raise ValueError("player_count_invalid")
                    records.append({"tournament_id": r.tournament_id, "game_family": r.game_family,
                                    "game_version": r.game_version, "year": r.year,
                                    "country_code": code, "country_name": cells[1].text_content().strip(),
                                    "prize_cents": money(cells[2].text_content()),
                                    "source_player_count": int(count[1]), "source_url": r.source_url})
            if not records or len({x["country_code"] for x in records}) != len(records):
                raise ValueError("empty_or_duplicate_country_rows")
            diff = sum(x["prize_cents"] for x in records) - r.pool_cents
            status = "reconciled" if abs(diff) <= 2 else "total_mismatch"
            if status == "reconciled":
                country_rows.extend(records)
        except (ValueError, OSError, ArithmeticError) as exc:
            error = str(exc)
        country_audit.append({"tournament_id": r.tournament_id, "game_family": r.game_family,
                              "year": r.year, "status": status, "error": error,
                              "source_html_file": r.source_html_file,
                              "html_sha256": hashlib.sha256(payload).hexdigest() if payload else None,
                              "country_row_count": len(records), "pool_cents": r.pool_cents,
                              "country_total_cents": sum(x["prize_cents"] for x in records) if records else None})
        country_candidates.extend([{**item, "table_status": status} for item in records])
        if i % 500 == 0:
            print(f"Quốc gia: {i}/{len(t)}", flush=True)
    countries = pd.DataFrame(country_rows)
    audit = pd.DataFrame(country_audit)
    require("country_key", not countries.duplicated(["tournament_id", "country_code"]).any())
    save("country_prizes.csv", countries)
    save("country_audit.csv", audit)
    save("country_quarantine.csv", audit[audit.status != "reconciled"])
    save("country_candidate_rows_review_only.csv", pd.DataFrame(country_candidates))
    coverage = audit.groupby(["game_family", "year"]).agg(tournament_count=("status", "size"),
        reconciled_count=("status", lambda s: s.eq("reconciled").sum()), source_pool_cents=("pool_cents", "sum")).reset_index()
    accepted = audit[audit.status == "reconciled"].groupby(["game_family", "year"]).pool_cents.sum()
    coverage["reconciled_pool_cents"] = [int(accepted.get((r.game_family, r.year), 0)) for r in coverage.itertuples()]
    coverage["country_money_coverage_pct"] = coverage.reconciled_pool_cents / coverage.source_pool_cents * 100
    save("country_coverage.csv", coverage)
    country_year = countries.groupby(["game_family", "year", "country_code", "country_name"], as_index=False).prize_cents.sum()
    country_year["share_of_reconciled_country_prize_pct"] = country_year.prize_cents / country_year.groupby(["game_family", "year"]).prize_cents.transform("sum") * 100
    save("country_year.csv", country_year)

    # Complete quarterly grid; missing observations stay null (not zero).
    grid = pd.MultiIndex.from_product([sorted(t.game_family.unique()), pd.period_range("2012Q1", "2025Q4", freq="Q").astype(str)], names=["game_family", "quarter"])
    q = t.groupby(["game_family", "quarter"]).agg(observed_tournament_count=("tournament_id", "size"), pool_cents=("pool_cents", "sum"), strict_count=("strict_quality", "sum")).reindex(grid).reset_index()
    strict = t[t.strict_quality].groupby(["game_family", "quarter"]).pool_cents.sum()
    q["strict_pool_cents"] = [strict.get((r.game_family, r.quarter), None) for r in q.itertuples()]
    q["target_prize_pool_usd"] = q.pool_cents / 100
    q["strict_target_prize_pool_usd"] = q.strict_pool_cents / 100
    q["period_observed"] = q.observed_tournament_count.notna()
    q["split"] = q.quarter.map(lambda x: "train" if x[:4] <= "2023" else "validation" if x[:4] == "2024" else "test")
    q["period_start"] = pd.PeriodIndex(q.quarter, freq="Q").start_time.strftime("%Y-%m-%d")
    save("forecast_prize_quarterly.csv", q)
    wm = w.copy()
    wm["split"] = wm.month_start.map(lambda x: "train" if x[:4] <= "2022" else "validation" if x[:4] == "2023" else "test")
    save("forecast_twitch_monthly.csv", wm)
    baseline = []
    for family, group in q.groupby("game_family"):
        group = group.sort_values("quarter").copy()
        group["prediction"] = group.target_prize_pool_usd.shift(4)
        group["evaluation"] = "rolling_one_step_seasonal_naive"
        baseline.append(group)
    baseline = pd.concat(baseline, ignore_index=True)
    save("forecast_baseline_predictions.csv", baseline)
    scores = []
    for (family, split), group in baseline[baseline.split != "train"].groupby(["game_family", "split"]):
        valid = group.dropna(subset=["prediction", "target_prize_pool_usd"])
        scores.append({"game_family": family, "split": split, "evaluation_rows": len(valid),
                       "MAE_usd": (valid.prediction - valid.target_prize_pool_usd).abs().mean(),
                       "evaluation": "rolling_one_step; earlier observed test targets allowed as lag"})
    save("forecast_baseline_scores.csv", pd.DataFrame(scores))
    save("eda_missingness.csv", pd.concat([pd.DataFrame({"table": name, "column": frame.columns,
        "missing_count": frame.isna().sum().values, "missing_pct": frame.isna().mean().values * 100})
        for name, frame in [("tournaments", t), ("placements", p), ("twitch", w), ("panel", panel)]], ignore_index=True))
    save("eda_twitch_descriptive.csv", w.groupby("game_family")[["hours_watched", "avg_viewers", "peak_viewers"]].describe().stack(level=0).reset_index())
    outlier_cols = [c for c in w if c.endswith("_iqr_flag")]
    save("eda_flagged_months.csv", w[w[outlier_cols].any(axis=1)])
    growth = w.sort_values(["game_family", "month_start"]).copy()
    growth["hours_watched_mom_pct"] = growth.groupby("game_family").hours_watched.pct_change(fill_method=None) * 100
    save("eda_monthly_growth.csv", growth)
    corr = []
    for family, group in panel.groupby("game_family"):
        for method in ["pearson", "spearman"]:
            sample = group[["hours_watched", "source_prize_pool_usd", "observed_tournament_count"]].dropna()
            matrix = sample.corr(method=method)
            corr.append({"game_family": family, "method": method, "n": len(sample),
                         "hours_vs_pool": matrix.loc["hours_watched", "source_prize_pool_usd"],
                         "hours_vs_tournaments": matrix.loc["hours_watched", "observed_tournament_count"]})
    save("eda_correlations_descriptive.csv", pd.DataFrame(corr))
    train = w[w.month_start < "2023-01-01"].copy()
    train["calendar_month"] = pd.to_datetime(train.month_start).dt.month
    save("eda_twitch_train_seasonality.csv", train.groupby(["game_family", "calendar_month"], as_index=False).hours_watched.mean())
    for filename, frame, x, y, ylabel in [
        ("01_twitch_hours.png", w, "month_start", "hours_watched", "Hours watched (game category)"),
        ("02_twitch_average.png", w, "month_start", "avg_viewers", "Average concurrent viewers"),
        ("03_quarterly_prize.png", q, "period_start", "target_prize_pool_usd", "Source prize pool USD"),
        ("04_twitch_share.png", panel, "month_start", "game_hours_share_of_twitch_pct", "% of all Twitch hours"),
        ("05_country_coverage.png", coverage.assign(date=coverage.year.astype(str)+"-01-01"), "date", "country_money_coverage_pct", "% prize covered by reconciled country tables")]:
        fig, ax = plt.subplots(figsize=(12, 5))
        for family, group in frame.groupby("game_family"):
            group = group.sort_values(x)
            ax.plot(pd.to_datetime(group[x]), group[y], label=family)
        ax.set_ylabel(ylabel)
        ax.legend()
        ax.grid(alpha=.2)
        fig.tight_layout()
        fig.savefig(eda / filename, dpi=150)
        plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, (family, group) in zip(axes.flat, panel.groupby("game_family")):
        ax.scatter(group.source_prize_pool_usd, group.hours_watched, alpha=.5)
        ax.set_title(family)
        ax.set_xlabel("Source monthly prize USD")
        ax.set_ylabel("Twitch hours watched")
    fig.tight_layout()
    fig.savefig(eda / "06_prize_vs_hours.png", dpi=150)
    plt.close(fig)
    manifest = {"stage": "analysis_release_v1_policy_clean_not_source_verified", "created_at": run,
                "tournaments": len(t), "placements": len(p), "twitch_rows": len(w),
                "strict_tournaments": int(t.strict_quality.sum()), "country_rows": len(countries),
                "country_statuses": audit.status.value_counts().to_dict(),
                "country_prize_coverage_pct": float(countries.prize_cents.sum() / t.pool_cents.sum() * 100),
                "checks": checks, "final_source_coverage_verified": False,
                "inputs": {str(f.resolve()): hashlib.sha256(f.read_bytes()).hexdigest() for f in sources}}
    manifest["outputs_sha256"] = {str(f.relative_to(out)): hashlib.sha256(f.read_bytes()).hexdigest() for f in out.rglob("*") if f.is_file()}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print("Bộ bàn giao:", out)


if __name__ == "__main__":
    main()

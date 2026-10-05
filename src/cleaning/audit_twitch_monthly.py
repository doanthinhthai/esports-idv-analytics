"""Audit saved Twitch tables without changing source or cleaned data."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from clean_twitch_monthly import ROOT, CATEGORY_MAP, normalize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    folder = args.input.resolve()
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    tables = {name: pd.read_csv(folder / f"{name}.csv", encoding="utf-8-sig")
              for name in ["all_categories_normalized", "target_categories",
                           "game_monthly_primary", "counter_strike_supplementary",
                           "platform_monthly", "quarantine"]}
    checks = []

    def check(name, function):
        try:
            function()
            checks.append({"check": name, "passed": True})
        except (AssertionError, ValueError, KeyError, OSError) as exc:
            checks.append({"check": name, "passed": False, "detail": str(exc)[:1500]})

    def require(condition):
        assert condition, "Điều kiện kiểm tra không đạt."

    def equal_rows(actual, expected, columns):
        left = actual.sort_values("source_row_number")[columns].reset_index(drop=True)
        right = expected.sort_values("source_row_number")[columns].reset_index(drop=True)
        assert_frame_equal(left, right, check_dtype=False, check_exact=True)

    games = tables["all_categories_normalized"]
    target = tables["target_categories"]
    primary = tables["game_monthly_primary"]
    extra = tables["counter_strike_supplementary"]
    global_data = tables["platform_monthly"]
    quarantine = tables["quarantine"]
    count_fields = {"all_categories_normalized": "raw_game_rows",
                    "target_categories": "target_category_rows",
                    "game_monthly_primary": "primary_rows",
                    "counter_strike_supplementary": "supplementary_rows",
                    "platform_monthly": "global_rows", "quarantine": "quarantine_rows"}
    for name, table in tables.items():
        check(f"row_count:{name}", lambda t=table, n=name: require(len(t) == summary[count_fields[n]]))
        check(f"source_row_unique:{name}", lambda t=table: require(t.source_row_number.notna().all() and t.source_row_number.is_unique))
        def verify_source(t=table, n=name):
            paths = t.source_file.dropna().unique()
            require(len(paths) == 1)
            path = Path(paths[0])
            require(hashlib.sha256(path.read_bytes()).hexdigest() == summary["input_sha256"][path.name])
            encoding = summary["encoding"]["global" if n == "platform_monthly" else "games"]
            raw = pd.read_csv(path, encoding=encoding)
            expected = normalize(raw)
            expected["month_start"] = expected.month_start.dt.strftime("%Y-%m-%d")
            require(t.source_row_number.isin(expected.source_row_number).all())
            expected = expected[expected.source_row_number.isin(t.source_row_number)]
            equal_rows(t, expected, list(expected.columns))
        check(f"raw_values_unchanged:{name}", verify_source)

    check("target_selection", lambda: equal_rows(target, games[games.source_category.isin(CATEGORY_MAP)], list(games.columns)))
    check("primary_partition", lambda: equal_rows(primary, target[target.analysis_role == "main"], list(target.columns)))
    check("supplementary_partition", lambda: equal_rows(extra, target[target.analysis_role == "supplementary"], list(target.columns)))
    check("quarantine_partition", lambda: equal_rows(quarantine, games[games.quality_status != "usable"], list(games.columns)))
    check("primary_game_month_unique", lambda: require(not primary.duplicated(["game_family", "month_start"]).any()))
    check("global_month_unique", lambda: require(global_data.month_start.is_unique))
    check("global_month_coverage", lambda: require(primary.month_start.isin(global_data.month_start).all()))
    check("target_quality", lambda: require(target.quality_status.eq("usable").all()))
    check("category_mapping", lambda: require(all((r.game_family, r.analysis_role) == CATEGORY_MAP[r.source_category] for r in target.itertuples())))

    def verify_coverage():
        for item in summary["coverage"]:
            group = primary[primary.game_family == item["game_family"]]
            dates = pd.DatetimeIndex(pd.to_datetime(group.month_start))
            require(len(group) == item["row_count"])
            require(dates.min().strftime("%Y-%m") == item["first_month"])
            require(dates.max().strftime("%Y-%m") == item["last_month"])
            missing = pd.date_range(dates.min(), dates.max(), freq="MS").difference(dates)
            require([d.strftime("%Y-%m") for d in missing] == item["missing_months"])
        require(set(primary.game_family) == {x["game_family"] for x in summary["coverage"]})
    check("coverage_summary", verify_coverage)

    for metric in ["hours_watched", "avg_viewers", "peak_viewers"]:
        def verify_flags(m=metric):
            flag = f"{m}_iqr_flag"
            require(primary[flag].isin([True, False]).all())
            for _, group in primary.groupby("game_family"):
                q1, q3 = group[m].quantile([0.25, 0.75])
                expected = (group[m] < q1 - 1.5 * (q3 - q1)) | (group[m] > q3 + 1.5 * (q3 - q1))
                require(primary.loc[group.index, flag].eq(expected).all())
            require(int(primary[flag].sum()) == summary["iqr_flag_counts"][flag])
        check(f"iqr_flags:{metric}", verify_flags)

    failed = [item for item in checks if not item["passed"]]
    report = {"input_folder": str(folder), "check_count": len(checks),
              "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "structural_checks_passed": not failed, "final_dataset_verified": False,
              "note": "Đối chiếu với CSV gốc; không xác minh độ chính xác nguồn. Twitch là game–tháng, không phải từng giải.",
              "checks": checks}
    output = ROOT / "reports/data_quality" / ("twitch_monthly_audit_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}, ensure_ascii=False, indent=2))
    print("Kiểm tra không đạt:", json.dumps(failed, ensure_ascii=False, indent=2))
    print("Báo cáo:", output)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

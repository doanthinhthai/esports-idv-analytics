from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import argparse
import json

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[2]
REPORT_ROOT = PROJECT_DIR / "reports/data_quality"


def load_csv(path, required):
    frame = pd.read_csv(
        path, dtype=str, keep_default_na=False
    )
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name} thiếu cột: {sorted(missing)}")
    return frame


def decimal_money(value):
    if not value:
        raise ValueError("missing_money")

    number = Decimal(value)
    if not number.is_finite() or number < 0:
        raise ValueError("invalid_money")
    if number != number.quantize(Decimal("0.01")):
        raise ValueError("money_not_normalized_to_cents")
    return number


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    folder = Path(args.input).resolve()
    source_summary = json.loads(
        (folder / "summary.json").read_text(encoding="utf-8")
    )
    scope = json.loads(
        (folder / "scope_snapshot.json").read_text(encoding="utf-8")
    )

    tournaments = load_csv(folder / "tournaments_clean.csv", [
        "tournament_id", "source_tournament_id",
        "game_slug", "game_family", "game_version",
        "start_date", "end_date", "year", "quarter",
        "prize_pool_usd", "date_validation_status",
        "crawler_status", "eligible_for_placement_prize_analysis",
    ])
    placements = load_csv(folder / "placements_clean.csv", [
        "placement_id", "tournament_id", "source_tournament_id",
        "game_slug", "game_family", "game_version", "team_name",
        "source_team_id", "source_team_id_raw",
        "team_identity_status", "placement_key_basis",
        "start_date", "year", "quarter", "prize_money_usd",
        "validation_status", "tournament_prize_difference_usd",
    ])
    quarantine = load_csv(folder / "quarantine.csv", [
        "tournament_id", "reason", "affected_table",
    ])
    outside = load_csv(folder / "out_of_scope.csv", [
        "tournament_id", "reason",
    ])

    checks = []

    def check(name, passed, detail=None):
        checks.append({
            "check": name,
            "passed": bool(passed),
            "detail": detail,
        })

    def no_bad(name, frame, mask, id_column):
        bad = frame.loc[mask]
        check(
            name,
            bad.empty,
            {
                "bad_row_count": len(bad),
                "sample_ids": bad[id_column].head(20).tolist(),
            },
        )

    check(
        "row_counts_match_summary",
        len(tournaments) == source_summary["tournament_count"]
        and len(placements) == source_summary["placement_count"]
        and len(quarantine) == source_summary["quarantine_record_count"]
        and len(outside) == source_summary["out_of_scope_count"],
    )

    no_bad(
        "tournament_ids_nonempty_unique",
        tournaments,
        tournaments["tournament_id"].eq("")
        | tournaments["tournament_id"].duplicated(keep=False),
        "tournament_id",
    )
    no_bad(
        "placement_ids_nonempty_unique",
        placements,
        placements["placement_id"].eq("")
        | placements["placement_id"].duplicated(keep=False),
        "placement_id",
    )

    parent_ids = set(tournaments["tournament_id"])
    no_bad(
        "placements_have_parent",
        placements,
        ~placements["tournament_id"].isin(parent_ids),
        "placement_id",
    )

    for label, frame, id_column in [
        ("tournaments", tournaments, "tournament_id"),
        ("placements", placements, "placement_id"),
    ]:
        no_bad(
            f"{label}_source_id_namespace",
            frame,
            frame["tournament_id"].ne(
                "earnings:" + frame["source_tournament_id"]
            ),
            id_column,
        )
        no_bad(
            f"{label}_games_in_scope",
            frame,
            ~frame["game_slug"].isin(scope["enabled_game_slugs"]),
            id_column,
        )

        dates = pd.to_datetime(
            frame["start_date"],
            format="%Y-%m-%d",
            errors="coerce",
        )
        lower = pd.Timestamp(scope["start_date"])
        upper = pd.Timestamp(scope["end_date"])

        no_bad(
            f"{label}_start_dates_valid_and_in_scope",
            frame,
            ~frame["start_date"].str.fullmatch(r"\d{4}-\d{2}-\d{2}")
            | dates.isna()
            | dates.lt(lower)
            | dates.gt(upper),
            id_column,
        )

        expected_year = dates.dt.strftime("%Y").fillna("")
        expected_quarter = dates.dt.to_period("Q").astype(str)

        no_bad(
            f"{label}_year_quarter_consistent",
            frame,
            frame["year"].ne(expected_year)
            | frame["quarter"].ne(expected_quarter),
            id_column,
        )

    end_dates = pd.to_datetime(
        tournaments["end_date"],
        format="%Y-%m-%d",
        errors="coerce",
    )
    start_dates = pd.to_datetime(
        tournaments["start_date"],
        format="%Y-%m-%d",
        errors="coerce",
    )
    no_bad(
        "tournament_date_ranges_valid",
        tournaments,
        end_dates.isna()
        | start_dates.gt(end_dates)
        | tournaments["date_validation_status"].ne("valid"),
        "tournament_id",
    )

    no_bad(
        "counter_strike_versions_preserved",
        tournaments,
        (
            tournaments["game_slug"].isin(["csgo", "cs2"])
            & tournaments["game_family"].ne("Counter-Strike")
        )
        | (
            tournaments["game_slug"].eq("csgo")
            & tournaments["game_version"].ne(
                "Counter-Strike: Global Offensive"
            )
        )
        | (
            tournaments["game_slug"].eq("cs2")
            & tournaments["game_version"].ne("Counter-Strike 2")
        ),
        "tournament_id",
    )

    no_bad(
        "ambiguous_team_ids_are_null",
        placements,
        placements["team_identity_status"].eq("ambiguous_source_id")
        & (
            placements["source_team_id"].ne("")
            | placements["source_team_id_raw"].eq("")
            | placements["placement_key_basis"].ne(
                "tournament_and_team_name"
            )
        ),
        "placement_id",
    )

    normalized_names = placements["team_name"].str.casefold()
    name_keys = pd.DataFrame({
        "tournament_id": placements["tournament_id"],
        "name": normalized_names,
    })
    no_bad(
        "team_names_nonempty_unique_within_tournament",
        placements,
        placements["team_name"].str.strip().eq("")
        | name_keys.duplicated(keep=False),
        "placement_id",
    )

    no_bad(
        "placement_statuses_allowed",
        placements,
        ~placements["validation_status"].isin(
            ["matched", "rounding_difference"]
        ),
        "placement_id",
    )

    # So sánh thuộc tính của placement với giải cha.
    merged = placements.merge(
        tournaments[[
            "tournament_id", "source_tournament_id",
            "game_slug", "game_family", "game_version",
            "start_date", "year", "quarter", "crawler_status",
            "eligible_for_placement_prize_analysis",
        ]],
        on="tournament_id",
        how="left",
        suffixes=("", "_parent"),
        validate="many_to_one",
    )

    mismatch = pd.Series(False, index=merged.index)
    for column in [
        "source_tournament_id", "game_slug",
        "game_family", "game_version",
        "start_date", "year", "quarter",
    ]:
        mismatch |= merged[column].ne(merged[column + "_parent"])

    mismatch |= merged["validation_status"].ne(
        merged["crawler_status"]
    )
    mismatch |= merged[
        "eligible_for_placement_prize_analysis"
    ].str.lower().ne("true")

    no_bad(
        "placement_attributes_match_parent",
        merged, mismatch, "placement_id",
    )

    eligible_ids = set(tournaments.loc[
        tournaments["eligible_for_placement_prize_analysis"]
        .str.lower().eq("true"),
        "tournament_id",
    ])
    check(
        "eligible_tournaments_have_placements",
        eligible_ids == set(placements["tournament_id"]),
    )

    bad_money = []
    pool_by_id = {}
    totals = {}

    for row in tournaments.to_dict("records"):
        try:
            pool_by_id[row["tournament_id"]] = decimal_money(
                row["prize_pool_usd"]
            )
        except (ValueError, InvalidOperation) as error:
            bad_money.append({
                "table": "tournaments",
                "id": row["tournament_id"],
                "error": str(error),
            })

    for row in placements.to_dict("records"):
        try:
            amount = decimal_money(row["prize_money_usd"])
            totals[row["tournament_id"]] = (
                totals.get(row["tournament_id"], Decimal("0"))
                + amount
            )
        except (ValueError, InvalidOperation) as error:
            bad_money.append({
                "table": "placements",
                "id": row["placement_id"],
                "error": str(error),
            })

    check(
        "money_values_valid",
        not bad_money,
        bad_money[:20],
    )

    bad_reconciliation = []
    parent_lookup = tournaments.set_index("tournament_id")

    for tournament_id, group in placements.groupby("tournament_id"):
        if tournament_id not in pool_by_id:
            bad_reconciliation.append(tournament_id)
            continue

        difference = (
            totals.get(tournament_id, Decimal("0"))
            - pool_by_id[tournament_id]
        )
        status = (
            "matched" if difference == 0
            else "rounding_difference"
            if abs(difference) <= Decimal("0.02")
            else "needs_review"
        )

        try:
            recorded_differences = {
                Decimal(value)
                for value in group["tournament_prize_difference_usd"]
            }
            valid = (
                set(group["validation_status"]) == {status}
                and parent_lookup.loc[
                    tournament_id, "crawler_status"
                ] == status
                and recorded_differences == {difference}
                and status in {"matched", "rounding_difference"}
            )
        except InvalidOperation:
            valid = False

        if not valid:
            bad_reconciliation.append(tournament_id)

    check(
        "prize_totals_and_flags_consistent",
        not bad_reconciliation,
        bad_reconciliation[:20],
    )

    blocked_ids = set(quarantine.loc[
        quarantine["affected_table"].eq("both"),
        "tournament_id",
    ])
    review_ids = set(quarantine.loc[
        quarantine["reason"].eq("prize_allocation_pending_review"),
        "tournament_id",
    ])
    check(
        "blocked_records_not_in_clean_tournaments",
        not blocked_ids.intersection(
            tournaments["source_tournament_id"]
        ),
    )
    check(
        "pending_prize_reviews_not_in_clean_placements",
        not review_ids.intersection(
            placements["source_tournament_id"]
        ),
    )

    clean_ids = set(tournaments["source_tournament_id"])
    outside_ids = set(outside["tournament_id"])
    check(
        "raw_tournament_partition_reconciles",
        not clean_ids.intersection(outside_ids)
        and not clean_ids.intersection(blocked_ids)
        and not outside_ids.intersection(blocked_ids)
        and len(clean_ids | outside_ids | blocked_ids)
        == source_summary["raw_result_count"],
    )

    minimum = scope["minimum_clean_business_rows"]
    check("minimum_business_rows_met", len(placements) >= minimum)

    tournament_coverage = (
        tournaments.groupby(["game_slug", "year"])
        .size().rename("tournament_count")
    )
    placement_coverage = (
        placements.groupby(["game_slug", "year"])
        .size().rename("placement_count")
    )
    coverage = pd.concat(
        [tournament_coverage, placement_coverage], axis=1
    ).fillna(0).astype(int).reset_index()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = REPORT_ROOT / f"clean_v2_audit_{run_id}"
    output.mkdir(parents=True, exist_ok=False)

    coverage.to_csv(
        output / "coverage_verified.csv",
        index=False,
        encoding="utf-8-sig",
    )

    failed = [item for item in checks if not item["passed"]]
    summary = {
        "input_folder": str(folder),
        "check_count": len(checks),
        "passed_count": len(checks) - len(failed),
        "failed_count": len(failed),
        "tournament_count": len(tournaments),
        "placement_count": len(placements),
        "ambiguous_id_placement_count": int(
            placements["team_identity_status"]
            .eq("ambiguous_source_id").sum()
        ),
        "ambiguous_id_tournament_count": int(
            placements.loc[
                placements["team_identity_status"]
                .eq("ambiguous_source_id"),
                "tournament_id",
            ].nunique()
        ),
        "structural_checks_passed": not failed,
        "final_dataset_verified": False,
        "note": (
            "Kiểm tra tính nhất quán của clean V2. "
            "Không chứng minh đủ nguồn hoặc đúng tiền từng đội."
        ),
    }

    (output / "checks.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("KẾT QUẢ AUDIT V2")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\nCÁC KIỂM TRA KHÔNG ĐẠT")
    print(json.dumps(failed, ensure_ascii=False, indent=2))
    print("\nBáo cáo:", output)

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
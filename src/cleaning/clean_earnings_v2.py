from pathlib import Path
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from collections import Counter
import hashlib
import json
import re
import sqlite3
import unicodedata

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = (
    PROJECT_DIR
    / "data/raw/esportsearnings/sqlite_pipeline/crawl.sqlite3"
)
CONFIG_PATH = PROJECT_DIR / "data/config/games_config.csv"
SCOPE_PATH = PROJECT_DIR / "data/config/project_scope.json"
OUTPUT_ROOT = PROJECT_DIR / "data/processed"

CENT = Decimal("0.01")
ACCEPTED_PLACEMENT_STATUSES = {"matched", "rounding_difference"}


def clean_text(value):
    if value is None:
        return None
    text = unicodedata.normalize("NFC", str(value))
    text = " ".join(text.split())
    return text or None


def money(value):
    if value is None:
        raise ValueError("missing_money")

    number = Decimal(str(value))

    if not number.is_finite() or number < 0:
        raise ValueError("invalid_money")

    return number.quantize(CENT, rounding=ROUND_HALF_UP)


def parse_day(value):
    if not isinstance(value, str):
        raise ValueError("missing_date")
    return date.fromisoformat(value)


def rank_number(value):
    if value is None:
        return None
    number = Decimal(str(value))
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError("invalid_rank")
    if number < 1:
        raise ValueError("invalid_rank")
    return int(number)


def write_csv(records, path, empty_columns):
    frame = (
        pd.DataFrame(records)
        if records else pd.DataFrame(columns=empty_columns)
    )
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame


def main():
    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)

    scope = json.loads(SCOPE_PATH.read_text(encoding="utf-8-sig"))

    if (
        scope["date_filter_field"] != "start_date"
        or scope["date_bounds_inclusive"] is not True
        or scope["row_count_table"] != "placements"
    ):
        raise ValueError("Scope không phù hợp với script v1.")

    lower = parse_day(scope["start_date"])
    upper = parse_day(scope["end_date"])
    if lower > upper:
        raise ValueError("Khoảng ngày scope không hợp lệ.")

    enabled_slugs = set(scope["enabled_game_slugs"])
    config = pd.read_csv(
        CONFIG_PATH, dtype=str, keep_default_na=False
    )

    if config["game_slug"].duplicated().any():
        raise ValueError("game_slug bị trùng trong config.")

    games = {
        row["game_slug"]: row
        for row in config.to_dict("records")
        if row["game_slug"] in enabled_slugs
        and row["enabled"].lower() == "true"
    }
    if set(games) != enabled_slugs:
        raise ValueError("Game trong scope/config không khớp.")

    with sqlite3.connect(
        DB_PATH.resolve().as_uri() + "?mode=ro", uri=True
    ) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("""
            SELECT tournament_id, game_slug, source_game_id,
                   source_url, status, error, html_file,
                   tournament_json, placements_json, audit_json
            FROM results
            ORDER BY game_slug, tournament_id
        """).fetchall()

    tournaments = []
    placements = []
    quarantine = []
    out_of_scope = []
    source_statuses = Counter()

    def flag(row, reason, affected_table, tournament, raw_placements):
        quarantine.append({
            "tournament_id": row["tournament_id"],
            "game_slug": row["game_slug"],
            "reason": reason,
            "affected_table": affected_table,
            "crawler_status": row["status"],
            "source_url": row["source_url"],
            "html_file": row["html_file"],
            "crawler_error": row["error"],
            "tournament_raw": tournament,
            "placements_raw": raw_placements,
            "audit_raw": json.loads(row["audit_json"] or "{}"),
        })

    for row in rows:
        slug = row["game_slug"]
        tournament_id = str(row["tournament_id"])
        source_statuses[f"{slug}:{row['status']}"] += 1

        tournament = json.loads(row["tournament_json"] or "{}")
        raw_placements = json.loads(row["placements_json"] or "[]")

        if slug not in games:
            out_of_scope.append({
                "game_slug": slug,
                "tournament_id": tournament_id,
                "reason": "game_outside_scope",
                "source_url": row["source_url"],
            })
            continue

        game = games[slug]

        if row["status"] == "failed" or not tournament:
            flag(
                row,
                "source_page_empty" if tournament_id == "18464"
                else "failed_or_missing_tournament",
                "both", tournament, raw_placements,
            )
            continue

        try:
            if not tournament_id.isdigit():
                raise ValueError("invalid_tournament_id")
            if str(tournament["source_tournament_id"]) != tournament_id:
                raise ValueError("tournament_id_mismatch")
            if (
                str(row["source_game_id"]) != game["earnings_game_id"]
                or str(tournament["source_game_id"])
                != game["earnings_game_id"]
            ):
                raise ValueError("game_id_mismatch")
            if tournament.get("source_url") != row["source_url"]:
                raise ValueError("source_url_mismatch")

            name = clean_text(tournament.get("tournament_name_raw"))
            if not name:
                raise ValueError("missing_tournament_name")

            if tournament.get("date_validation_status") == "invalid_date":
                raise ValueError("invalid_date")

            start = parse_day(tournament.get("start_date"))
            end = parse_day(tournament.get("end_date"))
            if start > end:
                raise ValueError("invalid_date")

            pool = money(tournament.get("prize_pool_usd"))

        except (ValueError, KeyError, ArithmeticError) as error:
            flag(
                row, str(error), "both",
                tournament, raw_placements,
            )
            continue

        if not lower <= start <= upper:
            out_of_scope.append({
                "game_slug": slug,
                "tournament_id": tournament_id,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "reason": "start_date_outside_scope",
                "source_url": row["source_url"],
            })
            continue

        # Giới hạn năm tối thiểu để phát hiện phân loại nguồn đáng ngờ.
        # Không coi kiểm tra này là xác minh phiên bản đầy đủ.
        if (
            (slug == "cs2" and start.year < 2023)
            or (slug == "valorant" and start.year < 2020)
        ):
            flag(
                row, "game_version_date_needs_review", "both",
                tournament, raw_placements,
            )
            continue

        clean_tournament = {
            **tournament,
            "tournament_id": f"earnings:{tournament_id}",
            "game_slug": slug,
            "game_id": game["game_id"],
            "game_family": game["game_family"],
            "game_version": game["game_name"],
            "version_evidence": tournament.get("game_source_url"),
            "tournament_name": name,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "year": start.year,
            "quarter": f"{start.year}Q{(start.month - 1) // 3 + 1}",
            "prize_pool_usd": str(pool),
            "date_validation_status": "valid",
            "crawler_status": row["status"],
            "eligible_for_placement_prize_analysis": False,
            "quality_note": None,
        }

        tournaments.append(clean_tournament)

        if row["status"] not in ACCEPTED_PLACEMENT_STATUSES:
            reason = (
                "prize_allocation_pending_review"
                if row["status"] == "needs_review"
                else "placements_unavailable_or_unapproved"
            )
            clean_tournament["quality_note"] = reason
            flag(row, reason, "placements", tournament, raw_placements)
            continue

        try:
            if not raw_placements:
                raise ValueError("missing_placements")

            prepared = []
            seen_names = set()

            names_by_source_id = {}

            for source_item in raw_placements:
                source_id = clean_text(source_item.get("source_team_id"))
                source_name = clean_text(source_item.get("team_name_raw"))

                if source_id and source_name:
                    names_by_source_id.setdefault(
                        source_id, set()
                    ).add(source_name.casefold())

            ambiguous_ids = {
                source_id
                for source_id, names in names_by_source_id.items()
                if len(names) > 1
            }

            for item in raw_placements:
                if str(item.get("source_tournament_id")) != tournament_id:
                    raise ValueError("placement_tournament_id_mismatch")
                if item.get("source_url") != row["source_url"]:
                    raise ValueError("placement_source_url_mismatch")
                if item.get("game_slug") != slug:
                    raise ValueError("placement_game_mismatch")

                team_name = clean_text(item.get("team_name_raw"))
                if not team_name:
                    raise ValueError("missing_team_name")

                normalized_name = team_name.casefold()
                team_id = clean_text(item.get("source_team_id"))

                normalized_name = team_name.casefold()
                source_team_id_raw = clean_text(
                    item.get("source_team_id")
                )

                if normalized_name in seen_names:
                    raise ValueError("duplicate_team_name")

                seen_names.add(normalized_name)

                if source_team_id_raw in ambiguous_ids:
                    team_id = None
                    identity_status = "ambiguous_source_id"
                elif source_team_id_raw:
                    team_id = source_team_id_raw
                    identity_status = "source_provided_not_verified"
                else:
                    team_id = None
                    identity_status = "source_id_missing"

                # Không tự coi nhóm coaches/subs là một đội độc lập
                # có cùng khoản thưởng với đội chính.
                if re.search(
                    r"\bcoach(?:es)?\b|\bsubstitut(?:e|es)\b",
                    team_name, flags=re.IGNORECASE,
                ):
                    raise ValueError(
                        "supplementary_roster_allocation_needs_review"
                    )

                amount = money(item.get("prize_money_usd"))
                rank_min = rank_number(item.get("rank_min"))
                rank_max = rank_number(item.get("rank_max"))

                if (rank_min is None) != (rank_max is None):
                    raise ValueError("incomplete_rank")
                if rank_min is not None and rank_min > rank_max:
                    raise ValueError("invalid_rank_range")
                if rank_min is None:
                    outcome = clean_text(item.get("result_outcome"))
                    if outcome not in {"WIN", "LOSE"}:
                        raise ValueError("missing_rank_and_outcome")

                team_key = (
                    f"id:{team_id}"
                    if team_id else f"name:{normalized_name}"
                )
                key = f"{tournament_id}|{team_key}"
                placement_id = hashlib.sha256(
                    key.encode("utf-8")
                ).hexdigest()

                prepared.append({
                    **item,
                    "placement_id": placement_id,
                    "tournament_id": clean_tournament["tournament_id"],
                    "game_family": game["game_family"],
                    "game_version": game["game_name"],
                    "team_name": team_name,
                    "source_team_id": team_id,
                    "source_team_id_raw": source_team_id_raw,
                    "team_identity_status": identity_status,
                    "placement_key_basis": (
                        "source_team_id"
                        if team_id else "tournament_and_team_name"
                    ),                    "rank_min": rank_min,
                    "rank_max": rank_max,
                    "prize_money_usd": str(amount),
                    "start_date": start.isoformat(),
                    "year": start.year,
                    "quarter": clean_tournament["quarter"],
                    "date_validation_status": "valid",
                })

            total = sum(
                (money(item["prize_money_usd"]) for item in prepared),
                Decimal("0"),
            )
            difference = total - pool
            recomputed_status = (
                "matched" if difference == 0
                else "rounding_difference"
                if abs(difference) <= Decimal("0.02")
                else "needs_review"
            )

            if recomputed_status != row["status"]:
                raise ValueError("stored_reconciliation_status_mismatch")

            for item in prepared:
                item["validation_status"] = recomputed_status
                item["tournament_prize_difference_usd"] = str(difference)

            placements.extend(prepared)
            clean_tournament[
                "eligible_for_placement_prize_analysis"
            ] = True
            clean_tournament["placements_total_usd"] = str(total)
            if ambiguous_ids:
                clean_tournament["quality_note"] = (
                    "ambiguous_source_team_id"
                )
                flag(
                    row,
                    "ambiguous_source_team_id",
                    "team_identity",
                    tournament,
                    raw_placements,
                )
        except (ValueError, KeyError, ArithmeticError) as error:
            clean_tournament["quality_note"] = str(error)
            flag(
                row, str(error), "placements",
                tournament, raw_placements,
            )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_dir = OUTPUT_ROOT / f"earnings_clean_v2_{run_id}"
    output_dir.mkdir(parents=True, exist_ok=False)

    tournament_frame = write_csv(
        tournaments, output_dir / "tournaments_clean.csv",
        ["tournament_id", "game_slug"],
    )
    placement_frame = write_csv(
        placements, output_dir / "placements_clean.csv",
        ["placement_id", "tournament_id", "game_slug"],
    )
    write_csv(
        out_of_scope, output_dir / "out_of_scope.csv",
        ["game_slug", "tournament_id", "reason"],
    )
    write_csv(
        [
            {key: value for key, value in item.items()
             if key not in {"tournament_raw", "placements_raw", "audit_raw"}}
            for item in quarantine
        ],
        output_dir / "quarantine.csv",
        ["game_slug", "tournament_id", "reason"],
    )

    (output_dir / "quarantine_details.json").write_text(
        json.dumps(quarantine, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "scope_snapshot.json").write_text(
        json.dumps(scope, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if tournament_frame["tournament_id"].duplicated().any():
        raise ValueError("ID giải clean bị trùng.")
    if placement_frame["placement_id"].duplicated().any():
        raise ValueError("ID placement clean bị trùng.")

    parent_ids = set(tournament_frame["tournament_id"])
    if not set(placement_frame["tournament_id"]).issubset(parent_ids):
        raise ValueError("Placements không có giải cha.")

    coverage = []
    for (slug, year), group in tournament_frame.groupby(
        ["game_slug", "year"]
    ):
        relevant = placement_frame.loc[
            placement_frame["game_slug"].eq(slug)
            & placement_frame["year"].eq(year)
        ] if placements else placement_frame

        coverage.append({
            "game_slug": slug,
            "year": int(year),
            "tournament_count": len(group),
            "placement_count": len(relevant),
        })

    write_csv(
        coverage, output_dir / "coverage_by_game_year.csv",
        ["game_slug", "year", "tournament_count", "placement_count"],
    )

    summary = {
        "dataset_stage": "clean_v2_provisional_not_final",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope_start": lower.isoformat(),
        "scope_end": upper.isoformat(),
        "raw_result_count": len(rows),
        "tournament_count": len(tournaments),
        "placement_count": len(placements),
        "tournaments_by_game": dict(Counter(
            item["game_slug"] for item in tournaments
        )),
        "placements_by_game": dict(Counter(
            item["game_slug"] for item in placements
        )),
        "quarantine_record_count": len(quarantine),
        "quarantine_by_reason": dict(Counter(
            item["reason"] for item in quarantine
        )),
        "out_of_scope_count": len(out_of_scope),
        "minimum_business_rows": scope["minimum_clean_business_rows"],
        "minimum_rows_met": (
            len(placements) >= scope["minimum_clean_business_rows"]
        ),
        "notes": [
            "Raw/SQLite không thay đổi.",
            "Matched chỉ là đối chiếu tổng tiền, không xác minh từng khoản.",
            "Tournaments giữ thông tin nguồn, kể cả placements chưa được duyệt.",
            "Không dùng toàn bộ tournaments cho forecast mà chưa chọn chính sách chất lượng.",
            "Quarantine có thể chứa giải vẫn có metadata trong tournaments_clean.",
            "Chưa hoàn tất độ phủ nguồn, viewers hoặc dữ liệu vùng.",
        ],
    }

    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("KẾT QUẢ CLEAN V2")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nThư mục xuất:", output_dir)


if __name__ == "__main__":
    main()
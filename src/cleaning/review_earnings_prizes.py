from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from collections import Counter
import csv
import json
import sqlite3

from bs4 import BeautifulSoup


PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data/raw/esportsearnings"
DB_PATH = RAW_DIR / "sqlite_pipeline/crawl.sqlite3"
REPORT_DIR = PROJECT_DIR / "reports/data_quality"

CENT = Decimal("0.01")


def money(value):
    if value is None:
        raise ValueError("Thiếu số tiền; không tự thay bằng 0.")

    number = Decimal(str(value))

    if not number.is_finite():
        raise ValueError(f"Số tiền không hợp lệ: {value}")

    return number.quantize(CENT, rounding=ROUND_HALF_UP)


def read_html_evidence(html_file):
    result = {
        "html_available": False,
        "html_rank_block_count": None,
        "html_team_element_count": None,
        "html_blocks": [],
    }

    if not html_file:
        return result

    path = RAW_DIR / html_file
    if not path.is_file():
        return result

    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    main = soup.select_one("main")

    if main is None:
        return result

    ranks = main.select(
        ".tournament_medalist_rank, .tournament_participant_rank"
    )
    teams = main.select(
        ".tournament_team_medalist_name, "
        ".tournament_team_participant_name"
    )

    result["html_available"] = True
    result["html_rank_block_count"] = len(ranks)
    result["html_team_element_count"] = len(teams)

    for rank in ranks:
        block = rank.parent
        prize = block.select_one(
            ".tournament_medalist_prize, "
            ".tournament_participant_prize"
        )
        block_teams = block.select(
            ".tournament_team_medalist_name, "
            ".tournament_team_participant_name"
        )

        result["html_blocks"].append({
            "rank_raw": rank.get_text(" ", strip=True),
            "prize_raw": (
                prize.get_text(" ", strip=True)
                if prize is not None else None
            ),
            "team_names": [
                team.get_text(" ", strip=True)
                for team in block_teams
            ],
            "block_text": block.get_text(" ", strip=True),
        })

    return result


def main():
    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)

    connection = sqlite3.connect(
        DB_PATH.resolve().as_uri() + "?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row

    try:
        rows = connection.execute("""
            SELECT tournament_id, game_slug, source_url,
                   html_file, tournament_json,
                   placements_json, audit_json
            FROM results
            WHERE status = 'needs_review'
            ORDER BY game_slug, tournament_id
        """).fetchall()
    finally:
        connection.close()

    if not rows:
        print("Không còn bản ghi needs_review.")
        return

    reviews = []
    details = []

    for row in rows:
        tournament_id = row["tournament_id"]
        tournament = json.loads(row["tournament_json"] or "{}")
        placements = json.loads(row["placements_json"] or "[]")
        audit = json.loads(row["audit_json"] or "{}")

        if not tournament or not placements:
            raise ValueError(
                f"{tournament_id}: thiếu tournament hoặc placements."
            )

        try:
            expected = money(tournament.get("prize_pool_usd"))
            amounts = [
                money(item.get("prize_money_usd"))
                for item in placements
            ]
        except (ValueError, ArithmeticError) as error:
            raise ValueError(
                f"{tournament_id}: {error}"
            ) from error

        total = sum(amounts, Decimal("0"))
        difference = total - expected

        if difference == 0:
            recomputed_status = "matched"
        elif abs(difference) <= Decimal("0.02"):
            recomputed_status = "rounding_difference"
        else:
            recomputed_status = "needs_review"

        percent = (
            abs(difference) / abs(expected) * Decimal("100")
            if expected != 0 else None
        )

        names = [
            item.get("team_name_raw")
            for item in placements
        ]
        duplicates = [
            name for name, count in Counter(names).items()
            if name and count > 1
        ]

        evidence = read_html_evidence(row["html_file"])
        html_team_count = evidence["html_team_element_count"]

        item = {
            "game_slug": row["game_slug"],
            "tournament_id": tournament_id,
            "tournament_name_raw": tournament.get(
                "tournament_name_raw"
            ),
            "start_date": tournament.get("start_date"),
            "end_date": tournament.get("end_date"),
            "prize_pool_raw": tournament.get("prize_pool_raw"),
            "currency_raw": tournament.get("currency_raw"),
            "expected_usd": str(expected),
            "placements_total_usd": str(total),
            "difference_usd": str(difference),
            "absolute_difference_usd": str(abs(difference)),
            "absolute_difference_pct": (
                str(percent.quantize(Decimal("0.0001")))
                if percent is not None else None
            ),
            "direction": (
                "placements_below_pool" if difference < 0 else
                "placements_above_pool" if difference > 0 else
                "equal"
            ),
            "placement_count": len(placements),
            "html_available": evidence["html_available"],
            "html_rank_block_count": evidence[
                "html_rank_block_count"
            ],
            "html_team_element_count": html_team_count,
            "team_count_mismatch": (
                html_team_count != len(placements)
                if html_team_count is not None else None
            ),
            "duplicate_team_names": " | ".join(duplicates),
            "negative_amount_count": sum(
                amount < 0 for amount in amounts
            ),
            "recomputed_status": recomputed_status,
            "source_url": row["source_url"],
            "html_file": row["html_file"],
            "review_decision": "pending",
        }

        reviews.append(item)
        details.append({
            "review": item,
            "tournament": tournament,
            "placements": placements,
            "stored_audit": audit,
            "html_evidence": evidence,
        })

    reviews.sort(
        key=lambda item: Decimal(
            item["absolute_difference_usd"]
        ),
        reverse=True,
    )

    run_id = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    output_dir = REPORT_DIR / f"prize_review_{run_id}"
    output_dir.mkdir(parents=True, exist_ok=False)

    with (output_dir / "review.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(reviews[0]),
        )
        writer.writeheader()
        writer.writerows(reviews)

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "review_count": len(reviews),
        "by_game": dict(Counter(
            item["game_slug"] for item in reviews
        )),
        "by_direction": dict(Counter(
            item["direction"] for item in reviews
        )),
        "by_recomputed_status": dict(Counter(
            item["recomputed_status"] for item in reviews
        )),
        "missing_html_count": sum(
            not item["html_available"] for item in reviews
        ),
        "team_count_mismatch_count": sum(
            item["team_count_mismatch"] is True
            for item in reviews
        ),
        "note": (
            "Chỉ kiểm tra offline. Chênh lệch chưa xác định "
            "nguyên nhân; không sửa dữ liệu nguồn."
        ),
    }

    for filename, data in [
        ("summary.json", summary),
        ("details.json", details),
    ]:
        (output_dir / filename).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print("TÓM TẮT")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n15 GIẢI CHÊNH LỆCH TIỀN LỚN NHẤT")
    for item in reviews[:15]:
        print(
            item["game_slug"],
            item["tournament_id"],
            item["tournament_name_raw"],
            f"pool={item['expected_usd']}",
            f"placements={item['placements_total_usd']}",
            f"diff={item['difference_usd']}",
            f"pct={item['absolute_difference_pct']}%",
            sep=" | ",
        )

    print("\nBáo cáo:", output_dir)
    print("Không thay đổi SQLite; không gửi request lên website.")


if __name__ == "__main__":
    main()
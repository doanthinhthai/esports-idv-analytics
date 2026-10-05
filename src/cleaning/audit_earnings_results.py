from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import json
import sqlite3

PROJECT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = (
    PROJECT_DIR
    / "data/raw/esportsearnings/sqlite_pipeline/crawl.sqlite3"
)
OUTPUT_DIR = PROJECT_DIR / "reports/data_quality"

REVIEW_STATUSES = {"failed", "needs_review", "tournament_only"}


def main():
    if not DB_PATH.is_file():
        raise SystemExit(f"Không thấy SQLite: {DB_PATH}")

    # Mở database chỉ đọc, không thay đổi kết quả crawler.
    connection = sqlite3.connect(
        DB_PATH.resolve().as_uri() + "?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row

    try:
        rows = connection.execute("""
            SELECT
                tournament_id,
                game_slug,
                source_url,
                status,
                error,
                html_file,
                tournament_json,
                audit_json
            FROM results
            ORDER BY game_slug, tournament_id
        """).fetchall()
    finally:
        connection.close()

    summary = {}
    issues = []
    rounding = []

    for row in rows:
        game = row["game_slug"]
        summary.setdefault(game, Counter())
        summary[game][row["status"]] += 1

        if row["status"] not in REVIEW_STATUSES | {"rounding_difference"}:
            continue

        tournament = (
            json.loads(row["tournament_json"])
            if row["tournament_json"]
            else {}
        )
        audit = (
            json.loads(row["audit_json"])
            if row["audit_json"]
            else {}
        )

        item = {
            "game_slug": game,
            "tournament_id": row["tournament_id"],
            "source_url": row["source_url"],
            "status": row["status"],
            "error": row["error"],
            "html_file": row["html_file"],
            "tournament_name_raw": tournament.get(
                "tournament_name_raw"
            ),
            "start_date": tournament.get("start_date"),
            "end_date": tournament.get("end_date"),
            "prize_pool_usd": tournament.get("prize_pool_usd"),
            "audit": audit,
        }

        if row["status"] == "rounding_difference":
            rounding.append(item)
        else:
            issues.append(item)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_dir = OUTPUT_DIR / f"earnings_results_{run_id}"
    output_dir.mkdir(exist_ok=False)

    outputs = {
        "summary.json": {
            game: dict(counts)
            for game, counts in summary.items()
        },
        "issues.json": issues,
        "rounding_differences.json": rounding,
    }

    for filename, data in outputs.items():
        (output_dir / filename).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print("THỐNG KÊ TRẠNG THÁI")
    print(json.dumps(outputs["summary.json"], ensure_ascii=False, indent=2))

    failed = [item for item in issues if item["status"] == "failed"]

    print(f"\nFAILED: {len(failed)}")
    for item in failed:
        print(
            item["game_slug"],
            item["tournament_id"],
            item["error"],
            sep=" | ",
        )

    print("\nBáo cáo:", output_dir)
    print("Chỉ audit dữ liệu thô; chưa cleaning, chưa retry.")


if __name__ == "__main__":
    main()
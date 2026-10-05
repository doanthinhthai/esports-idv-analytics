from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import csv
import json
import re

from bs4 import BeautifulSoup

PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data/raw/esportsearnings"
OUTPUT_DIR = PROJECT_DIR / "reports/data_quality"

GAMES = ["dota2", "lol", "valorant", "cs2"]


def read_csv(path, required_columns):
    if not path.is_file():
        raise FileNotFoundError(f"Chưa có file: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(required_columns) - set(reader.fieldnames or [])

        if missing:
            raise ValueError(f"{path.name}: thiếu cột {sorted(missing)}")

        return list(reader)


def get_ids(rows, column):
    return {
        (row.get(column) or "").strip()
        for row in rows
        if (row.get(column) or "").strip()
    }


def audit_game(game):
    base = RAW_DIR / game
    discovery_dir = base / "event_discovery"

    events = read_csv(
        base / "event_urls.csv",
        ["source_event_id", "source_url"],
    )
    direct = read_csv(
        base / "direct_tournament_urls.csv",
        ["source_tournament_id"],
    )
    tournaments = read_csv(
        discovery_dir / "all_tournament_urls.csv",
        ["source_tournament_id"],
    )

    audit_path = discovery_dir / "discovery_audit.csv"
    audit_rows = (
        read_csv(audit_path, ["source_event_id", "status"])
        if audit_path.is_file()
        else []
    )

    # Nếu có nhiều dòng audit cùng ID, giữ dòng cuối trong file.
    audit_by_id = {
        row["source_event_id"].strip(): row
        for row in audit_rows
        if row["source_event_id"].strip()
    }

    event_ids = get_ids(events, "source_event_id")
    direct_ids = get_ids(direct, "source_tournament_id")
    tournament_ids = get_ids(tournaments, "source_tournament_id")

    pending_ids = sorted(event_ids - set(audit_by_id))
    issues = [
        row
        for event_id, row in audit_by_id.items()
        if event_id in event_ids and row["status"] != "extracted"
    ]
    status_counts = Counter(
        audit_by_id[event_id]["status"]
        for event_id in event_ids
        if event_id in audit_by_id
    )

    html_path = base / "events_index.html"
    soup = BeautifulSoup(html_path.read_bytes(), "html.parser")
    main = soup.find("main")

    if main is None:
        raise ValueError("HTML danh sách không có main.")

    text = main.get_text(" ", strip=True)

    # Chỉ lấy tổng tournaments trước phần danh sách Events.
    header_text = text.split("Browse Events", 1)[0]
    match = re.search(
        r"From\s+([\d,]+)\s+Tournaments",
        header_text,
        re.IGNORECASE,
    )
    source_total = (
        int(match.group(1).replace(",", "")) if match else None
    )

    metadata_path = base / "events_index.json"
    metadata = (
        json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        if metadata_path.is_file()
        else {}
    )

    return {
        "game_slug": game,
        "source_crawled_at": metadata.get("crawled_at"),
        "source_reported_tournaments_all_history": source_total,
        "discovered_unique_tournament_ids": len(tournament_ids),
        "count_difference_discovered_minus_source": (
            len(tournament_ids) - source_total
            if source_total is not None
            else None
        ),
        "listed_unique_event_ids": len(event_ids),
        "event_status_counts": dict(status_counts),
        "pending_event_count": len(pending_ids),
        "pending_events": [
            row for row in events
            if row["source_event_id"].strip() in set(pending_ids)
        ],
        "issue_event_count": len(issues),
        "issue_events": issues,
        "direct_ids_missing_from_discovery": sorted(
            direct_ids - tournament_ids
        ),
        "duplicate_tournament_id_rows": (
            len(tournaments) - len(tournament_ids)
        ),
        "completeness_status": "requires_id_and_coverage_reconciliation",
    }


def main():
    reports = []

    for game in GAMES:
        print(f"\n=== {game} ===")

        try:
            report = audit_game(game)
            reports.append(report)

            print(
                "Tổng tournaments nguồn công bố:",
                report["source_reported_tournaments_all_history"],
            )
            print(
                "URL giải duy nhất đã tìm:",
                report["discovered_unique_tournament_ids"],
            )
            print(
                "Chênh lệch (đã tìm - nguồn):",
                report["count_difference_discovered_minus_source"],
            )
            print(
                "Trạng thái sự kiện:",
                report["event_status_counts"],
            )
            print("Chưa xử lý:", report["pending_event_count"])
            print("Cần kiểm tra:", report["issue_event_count"])
            print(
                "ID giải trực tiếp chưa được hợp nhất:",
                report["direct_ids_missing_from_discovery"],
            )
            print(
                "Số dòng trùng/thiếu ID giải cần kiểm tra:",
                report["duplicate_tournament_id_rows"],
            )

            for row in report["issue_events"][:15]:
                print(
                    "ISSUE:",
                    row.get("source_event_id"),
                    row.get("status"),
                    row.get("error"),
                    row.get("source_url"),
                )

        except Exception as exc:
            reports.append({
                "game_slug": game,
                "error": f"{type(exc).__name__}: {exc}",
            })
            print("Chưa kiểm tra được:", exc)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_path = OUTPUT_DIR / f"discovery_audit_{run_id}.json"

    output_path.write_text(
        json.dumps(reports, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nBáo cáo đầy đủ:", output_path)
    print("So sánh toàn lịch sử trong nguồn, chưa lọc 2012–2025.")
    print("Số lượng bằng nhau không chứng minh các tập ID bằng nhau.")


if __name__ == "__main__":
    main()
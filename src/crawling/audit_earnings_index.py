from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit
from collections import defaultdict
import json
import re

from bs4 import BeautifulSoup

PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data/raw/esportsearnings"
OUTPUT_DIR = PROJECT_DIR / "reports/data_quality"

GAMES = ["dota2", "lol", "valorant", "cs2"]


def audit_game(game):
    base = RAW_DIR / game
    html_path = base / "events_index.html"
    metadata_path = base / "events_index.json"

    if not html_path.is_file():
        raise FileNotFoundError(f"Không thấy HTML: {html_path}")

    metadata = {}
    if metadata_path.is_file():
        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8-sig")
        )

    source_url = metadata.get("source_url")
    if not source_url:
        raise ValueError(f"{game}: thiếu source_url trong metadata.")

    soup = BeautifulSoup(html_path.read_bytes(), "html.parser")
    main = soup.find("main")
    if main is None:
        raise ValueError(f"{game}: không tìm thấy main.")

    heading = main.find("h1")
    by_year = defaultdict(lambda: {
        "event_ids": set(),
        "tournament_ids": set(),
        "row_count": 0,
    })
    current_year = None

    # Hai loại node xuất hiện theo thứ tự trong HTML:
    # tiêu đề năm, rồi các ô tên sự kiện/giải bên dưới.
    for node in main.select(
        ".detail_list_table_header, td.detail_list_tournament"
    ):
        if "detail_list_table_header" in node.get("class", []):
            text = node.get_text(" ", strip=True)
            match = re.fullmatch(r"(?:19|20)\d{2}", text)
            if match:
                current_year = int(text)
                by_year[current_year]
            continue

        bucket = by_year[current_year]
        bucket["row_count"] += 1

        for link in node.select("a[href]"):
            absolute_url = urljoin(source_url, link["href"])
            parts = urlsplit(absolute_url)

            if parts.hostname != "www.esportsearnings.com":
                continue

            match = re.match(
                r"/(events|tournaments)/(\d+)(?:-|/|$)",
                parts.path,
            )
            if match:
                key = (
                    "event_ids"
                    if match.group(1) == "events"
                    else "tournament_ids"
                )
                bucket[key].add(match.group(2))

    all_events = set()
    all_tournaments = set()
    year_rows = []

    for year in sorted(by_year, key=lambda value: (
        value is None,
        value if value is not None else 0,
    )):
        bucket = by_year[year]
        all_events.update(bucket["event_ids"])
        all_tournaments.update(bucket["tournament_ids"])
        year_rows.append({
            "year_section": year,
            "rows_in_html": bucket["row_count"],
            "unique_event_ids": len(bucket["event_ids"]),
            "unique_direct_tournament_ids": len(
                bucket["tournament_ids"]
            ),
        })

    # Chỉ tìm dấu hiệu điều hướng; không tự kết luận có/không phân trang.
    navigation_candidates = set()
    source_parts = urlsplit(source_url)

    for link in main.select("a[href]"):
        absolute_url = urljoin(source_url, link["href"])
        parts = urlsplit(absolute_url)
        label = link.get_text(" ", strip=True)
        rel = {str(value).lower() for value in link.get("rel", [])}

        if parts.hostname != source_parts.hostname:
            continue

        same_list_with_query = (
            parts.path.rstrip("/") == source_parts.path.rstrip("/")
            and bool(parts.query)
        )
        pagination_label = bool(re.search(
            r"\b(next|previous|load more|older|newer)\b",
            label,
            re.IGNORECASE,
        ))
        pagination_rel = bool(rel & {"next", "prev"})

        if same_list_with_query or pagination_label or pagination_rel:
            navigation_candidates.add((label, absolute_url))

    return {
        "game_slug": game,
        "heading": heading.get_text(" ", strip=True) if heading else None,
        "source_url": source_url,
        "source_crawled_at": metadata.get("crawled_at"),
        "html_file": str(html_path),
        "year_sections": [
            row["year_section"]
            for row in year_rows
            if row["year_section"] is not None
        ],
        "unique_event_ids_all_sections": len(all_events),
        "unique_direct_tournament_ids_all_sections": len(all_tournaments),
        "counts_by_year_section": year_rows,
        "navigation_candidates": [
            {"label": label, "url": url}
            for label, url in sorted(navigation_candidates)
        ],
        "completeness_status": "not_yet_verified",
    }


def main():
    reports = []

    for game in GAMES:
        print(f"\n=== {game} ===")
        try:
            report = audit_game(game)
            reports.append(report)

            print("Nguồn:", report["source_url"])
            print("Thời điểm lưu:", report["source_crawled_at"])
            print("Các mục năm:", report["year_sections"])
            print(
                "Sự kiện duy nhất:",
                report["unique_event_ids_all_sections"],
            )
            print(
                "Giải trực tiếp duy nhất:",
                report["unique_direct_tournament_ids_all_sections"],
            )
            print("Năm | Số dòng | Sự kiện | Giải trực tiếp")

            for row in report["counts_by_year_section"]:
                print(
                    row["year_section"],
                    row["rows_in_html"],
                    row["unique_event_ids"],
                    row["unique_direct_tournament_ids"],
                    sep=" | ",
                )

            print(
                "Liên kết cần kiểm tra điều hướng:",
                report["navigation_candidates"],
            )

        except Exception as exc:
            reports.append({
                "game_slug": game,
                "error": f"{type(exc).__name__}: {exc}",
                "completeness_status": "audit_failed",
            })
            print("LỖI:", exc)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_path = OUTPUT_DIR / f"earnings_index_audit_{run_id}.json"

    output_path.write_text(
        json.dumps(reports, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nĐã lưu báo cáo:", output_path)
    print("Chỉ kiểm tra HTML cache; chưa xác nhận đủ toàn website.")


if __name__ == "__main__":
    main()
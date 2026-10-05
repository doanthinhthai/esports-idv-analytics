from pathlib import Path
from datetime import date, datetime, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit
from collections import Counter
import hashlib
import json
import re

import pandas as pd
from bs4 import BeautifulSoup


PROJECT_DIR = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_DIR / "data/raw/escharts/listing_snapshots"
OUTPUT_ROOT = PROJECT_DIR / "data/raw/escharts/url_discovery"

GAMES = {
    "counter_strike": ("csgo", "Counter-Strike"),
    "dota2": ("dota2", "Dota 2"),
    "lol": ("lol", "League of Legends"),
    "valorant": ("valorant", "Valorant"),
}

FILE_PATTERN = re.compile(
    r"^(counter_strike|dota2|lol|valorant)"
    r"_(alltime|20\d{2})_page_(\d+)\.html$"
)


def event_url(href, listing_url, game_path):
    parts = urlsplit(urljoin(listing_url, href))
    segments = parts.path.strip("/").split("/")

    if (
        parts.scheme != "https"
        or parts.hostname != "escharts.com"
        or len(segments) != 3
        or segments[:2] != ["tournaments", game_path]
    ):
        return None

    return urlunsplit((
        "https", "escharts.com", parts.path.rstrip("/"), "", ""
    ))


def read_date_hint(raw):
    tokens = re.findall(
        r"(?<!\d)(\d{2})\.(\d{2})\.(\d{4}|\d{2})(?!\d)", raw
    )
    if not tokens:
        return None

    day, month, year = tokens[0]
    year = int(year)
    if year < 100:
        year += 2000

    try:
        return date(year, int(month), int(day)).isoformat()
    except ValueError:
        return None


def main():
    scope = json.loads(
        (PROJECT_DIR / "data/config/project_scope.json")
        .read_text(encoding="utf-8-sig")
    )
    lower = scope["start_date"]
    upper = scope["end_date"]

    files = [
        path for path in sorted(INPUT_DIR.glob("*.html"))
        if FILE_PATTERN.fullmatch(path.name)
    ]

    if not files:
        raise SystemExit("Không thấy HTML danh sách đúng mẫu tên.")

    observations = []
    audits = []
    seen_page_signatures = {}

    for path in files:
        match = FILE_PATTERN.fullmatch(path.name)
        prefix, filter_hint, page_hint = match.groups()
        game_path, family = GAMES[prefix]
        listing_url = f"https://escharts.com/tournaments/{game_path}"

        html_bytes = path.read_bytes()
        soup = BeautifulSoup(html_bytes, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""

        audit = {
            "snapshot_file": path.name,
            "game_family": family,
            "filter_hint_from_filename": filter_hint,
            "page_hint_from_filename": int(page_hint),
            "page_title": title,
            "html_sha256": hashlib.sha256(html_bytes).hexdigest(),
            "status": "failed",
            "event_count": 0,
            "next_page_urls": [],
            "error": None,
        }

        try:
            if any(marker in title.lower() for marker in [
                "just a moment", "access denied", "attention required"
            ]):
                raise ValueError("HTML là trang kiểm tra truy cập.")

            tables = [
                table for table in soup.select("table")
                if all(label in table.get_text(" ", strip=True)
                       for label in [
                           "Hours Watched", "Peak Viewers", "Event Date"
                       ])
            ]

            if len(tables) != 1:
                raise ValueError(
                    f"Cần đúng một bảng giải; tìm thấy {len(tables)}."
                )

            page_records = {}

            for row in tables[0].select("tbody tr"):
                cells = row.find_all("td", recursive=False)
                if not cells:
                    continue

                # Bỏ qua đúng dòng quảng cáo gộp 7 cột.
                if (
                    len(cells) == 1
                    and str(cells[0].get("colspan")) == "7"
                    and row.select_one("a.meta-tournaments-dashboard")
                ):
                    continue

                if len(cells) != 7:
                    raise ValueError(
                        f"Cấu trúc bảng thay đổi: {len(cells)} cột."
                    )

                candidates = []
                for anchor in cells[0].select("a[href]"):
                    url = event_url(
                        anchor["href"], listing_url, game_path
                    )
                    text = anchor.get_text(" ", strip=True)
                    if url and text:
                        candidates.append((anchor, url))

                distinct_urls = {url for _, url in candidates}
                if len(distinct_urls) != 1:
                    raise ValueError(
                        "Một dòng không có đúng một URL giải cùng game."
                    )

                anchor, url = candidates[0]
                date_raw = cells[-1].get_text(" ", strip=True)
                start_hint = read_date_hint(date_raw)

                scope_hint = (
                    "unknown_date" if start_hint is None
                    else "in_scope"
                    if lower <= start_hint <= upper
                    else "outside_scope"
                )

                if url in page_records:
                    raise ValueError("URL giải lặp trong cùng bảng.")

                page_records[url] = {
                    "source_site": "escharts",
                    "game_family": family,
                    "source_url": url,
                    "tournament_name_hint": (
                        anchor.get("title")
                        or anchor.get_text(" ", strip=True)
                    ),
                    "date_raw": date_raw,
                    "start_date_hint": start_hint,
                    "scope_hint": scope_hint,
                    "snapshot_file": path.name,
                    "snapshot_sha256": audit["html_sha256"],
                    "mapping_status": "unmatched",
                }

            if not page_records:
                raise ValueError("Không lấy được URL giải trong bảng.")

            next_urls = set()
            for anchor in soup.select(
                'a[rel~="next"][href], a.meta-next-page[href]'
            ):
                url = urljoin(listing_url, anchor["href"])
                parts = urlsplit(url)

                if (
                    parts.scheme == "https"
                    and parts.hostname == "escharts.com"
                    and parts.path.rstrip("/")
                    == f"/tournaments/{game_path}"
                ):
                    next_urls.add(url)

            signature = (
                family, tuple(sorted(page_records))
            )
            if signature in seen_page_signatures:
                audit["same_event_set_as"] = seen_page_signatures[signature]
            else:
                seen_page_signatures[signature] = path.name

            observations.extend(page_records.values())
            audit["status"] = "parsed"
            audit["event_count"] = len(page_records)
            audit["next_page_urls"] = sorted(next_urls)

        except ValueError as error:
            audit["error"] = str(error)

        audits.append(audit)

    # Giữ mọi quan sát; danh sách URL tổng hợp không lặp.
    grouped = {}
    for item in observations:
        grouped.setdefault(item["source_url"], []).append(item)

    urls = []
    for url, records in sorted(grouped.items()):
        hints = {
            (item["start_date_hint"], item["scope_hint"])
            for item in records
        }
        item = dict(records[0])
        item["snapshot_files"] = " | ".join(sorted({
            record["snapshot_file"] for record in records
        }))
        item["listing_metadata_conflict"] = len(hints) > 1
        if len(hints) > 1:
            item["scope_hint"] = "needs_metadata_review"
        urls.append(item)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = OUTPUT_ROOT / run_id
    output.mkdir(parents=True, exist_ok=False)

    for filename, records in [
        ("listing_observations.csv", observations),
        ("tournament_urls.csv", urls),
    ]:
        pd.DataFrame(records).to_csv(
            output / filename, index=False, encoding="utf-8-sig"
        )

    parsed_families = {
        item["game_family"] for item in audits
        if item["status"] == "parsed"
    }

    summary = {
        "dataset_stage": "saved_listing_discovery_not_full_coverage",
        "snapshot_count": len(files),
        "parsed_snapshot_count": sum(
            item["status"] == "parsed" for item in audits
        ),
        "failed_snapshot_count": sum(
            item["status"] == "failed" for item in audits
        ),
        "unique_url_count": len(urls),
        "urls_by_family": dict(Counter(
            item["game_family"] for item in urls
        )),
        "urls_by_scope_hint": dict(Counter(
            item["scope_hint"] for item in urls
        )),
        "missing_families": sorted(
            {family for _, family in GAMES.values()}
            - parsed_families
        ),
        "note": (
            "Chỉ đọc bảng trong HTML đã lưu, không lấy link từ menu/FAQ. "
            "Ngày mới là gợi ý từ danh sách; chưa xác nhận trang chi tiết. "
            "Có link trang tiếp theo không có nghĩa trang đó đã được thu thập."
        ),
    }

    for filename, data in [
        ("summary.json", summary),
        ("listing_audit.json", audits),
    ]:
        (output / filename).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print("KẾT QUẢ DISCOVERY CHARTS OFFLINE")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\nTỪNG FILE")
    for item in audits:
        print(
            item["snapshot_file"],
            item["status"],
            f"events={item['event_count']}",
            f"next={item['next_page_urls']}",
            item["error"] or "",
            sep=" | ",
        )

    print("\nThư mục xuất:", output)
    print("Không gửi request, không sửa dữ liệu Earnings.")


if __name__ == "__main__":
    main()
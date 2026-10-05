from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin
import json
import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw" / "esportsearnings"

GAME_ID = "245"
MAX_EVENTS = 1797
DELAY_SECONDS = 5

OUTPUT_DIR = RAW_DIR / "245_event_discovery"
HTML_DIR = OUTPUT_DIR / "html"
HTML_DIR.mkdir(parents=True, exist_ok=True)

COLUMNS = [
    "source_game_id",
    "source_tournament_id",
    "tournament_name",
    "source_url",
    "discovered_from_url",
    "source_html_file",
]


def extract_tournaments(html_bytes, event_url, html_filename):
    soup = BeautifulSoup(html_bytes, "html.parser")
    records = []

    for row in soup.select("main tr"):
        tournament_link = row.select_one(
            'td.detail_list_tournament a[href^="/tournaments/"]'
        )
        game_link = row.select_one(
            'td.detail_list_game a[href^="/games/"]'
        )

        if tournament_link is None or game_link is None:
            continue

        game_match = re.match(
            r"/games/(\d+)(?:-|/|$)", game_link["href"]
        )
        if not game_match or game_match.group(1) != GAME_ID:
            continue

        url = urljoin(event_url, tournament_link["href"])
        tournament_match = re.search(r"/tournaments/(\d+)", url)
        if not tournament_match:
            continue

        records.append({
            "source_game_id": GAME_ID,
            "source_tournament_id": tournament_match.group(1),
            "tournament_name": tournament_link.get_text(" ", strip=True),
            "source_url": url,
            "discovered_from_url": event_url,
            "source_html_file": html_filename,
        })

    return pd.DataFrame(records, columns=COLUMNS).drop_duplicates(
        subset=["source_tournament_id"]
    )


def merge_saved_results():
    frames = [
        pd.read_csv(
            RAW_DIR / "245_direct_tournament_urls.csv",
            dtype=str,
        )
    ]

    for path in sorted(OUTPUT_DIR.glob("*_tournament_urls.csv")):
        frames.append(pd.read_csv(path, dtype=str))

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(
        subset=["source_game_id", "source_tournament_id"]
    )

    combined.to_csv(
        OUTPUT_DIR / "245_all_tournament_urls.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return len(combined)


def main():
    events = pd.read_csv(
        RAW_DIR / "245_event_urls.csv", dtype=str
    ).drop_duplicates(subset=["source_event_id"]).head(MAX_EVENTS)

    audit = []

    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "Esports-IDV-Student-Research/1.0"
        })

        for position, (_, event) in enumerate(events.iterrows(), start=1):
            event_id = event["source_event_id"]
            event_url = event["source_url"]
            html_path = HTML_DIR / f"{event_id}.html"

            print(f"\n[{position}/{len(events)}] {event_url}")

            record = {
                "source_event_id": event_id,
                "source_url": event_url,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "status": "",
                "tournament_count": 0,
                "error": "",
            }
            stop = False

            try:
                if not re.fullmatch(r"\d+", event_id):
                    raise ValueError("ID sự kiện không hợp lệ.")

                if not event_url.startswith(
                    "https://www.esportsearnings.com/events/"
                ):
                    raise ValueError("URL không đúng nguồn sự kiện.")

                if html_path.exists():
                    html_bytes = html_path.read_bytes()
                    print("Đọc HTML đã lưu.")
                else:
                    time.sleep(DELAY_SECONDS)
                    response = session.get(
                        event_url,
                        timeout=30,
                        allow_redirects=False,
                    )

                    record["http_status"] = response.status_code

                    if response.status_code in (403, 429):
                        stop = True

                    response.raise_for_status()

                    if response.status_code != 200:
                        raise ValueError(
                            "Trang chuyển hướng hoặc phản hồi không phải 200."
                        )

                    html_bytes = response.content
                    soup = BeautifulSoup(html_bytes, "html.parser")
                    if soup.select_one("main h1") is None:
                        raise ValueError(
                            "HTML không có cấu trúc trang dự kiến."
                        )

                    html_path.write_bytes(html_bytes)
                    html_path.with_suffix(".json").write_text(
                        json.dumps({
                            "source_url": event_url,
                            "source_event_id": event_id,
                            "crawled_at": datetime.now(
                                timezone.utc
                            ).isoformat(),
                            "http_status": response.status_code,
                            "source_html_file": html_path.name,
                        }, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

                tournaments = extract_tournaments(
                    html_bytes,
                    event_url,
                    html_path.relative_to(RAW_DIR).as_posix(),
                )

                tournaments.to_csv(
                    OUTPUT_DIR / f"{event_id}_tournament_urls.csv",
                    index=False,
                    encoding="utf-8-sig",
                )

                record["tournament_count"] = len(tournaments)
                record["status"] = (
                    "extracted" if len(tournaments) else "needs_review"
                )
                print(
                    f"Tìm được {len(tournaments)} URL giải CS:GO "
                    f"| {record['status']}"
                )

            except (requests.RequestException, ValueError, OSError) as exc:
                record["status"] = "failed"
                record["error"] = str(exc)
                print("Không hoàn thành:", exc)

            audit.append(record)

            pd.DataFrame(audit).to_csv(
                OUTPUT_DIR / "discovery_audit_latest.csv",
                index=False,
                encoding="utf-8-sig",
            )

            total = merge_saved_results()
            print(f"Tổng URL giải duy nhất hiện có: {total}")

            if stop:
                print("Dừng vì HTTP 403/429. Không tiếp tục gửi yêu cầu.")
                break

    print("\nKết quả nằm tại:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
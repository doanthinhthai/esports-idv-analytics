from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import argparse
import json
import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup


PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_DIR / "data" / "config" / "games_config.csv"
RAW_DIR = PROJECT_DIR / "data" / "raw" / "esportsearnings"


def main():
    parser = argparse.ArgumentParser(
        description="Lấy danh sách URL từ cấu hình game."
    )
    parser.add_argument("--game", required=True, help="Ví dụ: dota2 hoặc lol")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Chỉ đọc HTML đã lưu, không tải trang.",
    )
    args = parser.parse_args()

    config = pd.read_csv(CONFIG_PATH, dtype=str).fillna("")
    selected = config.loc[config["game_slug"].eq(args.game)]

    if len(selected) != 1:
        raise ValueError(f"Không tìm thấy một cấu hình duy nhất: {args.game}")

    game = selected.iloc[0]

    if game["enabled"].lower() != "true":
        raise ValueError("Game này chưa được bật trong cấu hình.")

    game_id = game["earnings_game_id"]
    source_url = game["earnings_events_url"]

    if not re.fullmatch(r"\d+", game_id):
        raise ValueError("earnings_game_id chưa hợp lệ.")

    parsed_url = urlparse(source_url)

    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "www.esportsearnings.com"
        or not parsed_url.path.startswith(f"/games/{game_id}-")
        or not parsed_url.path.endswith("/events")
    ):
        raise ValueError("URL Browse Events không khớp cấu hình game.")

    # Dùng slug từ dòng cấu hình và kiểm tra trước khi tạo đường dẫn.
    game_slug = game["game_slug"]

    if not re.fullmatch(r"[a-z0-9_]+", game_slug):
        raise ValueError("game_slug chỉ được chứa chữ thường, số và dấu _.")

    output_dir = RAW_DIR / game_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path = output_dir / "events_index.html"
    metadata_path = output_dir / "events_index.json"

    if html_path.exists():
        html_bytes = html_path.read_bytes()
        print("Đọc HTML đã lưu:", html_path)

    elif args.offline:
        raise FileNotFoundError(
            f"Chưa có HTML để đọc offline: {html_path}"
        )

    else:
        time.sleep(3)

        with requests.Session() as session:
            session.headers.update({
                "User-Agent": "Esports-IDV-Student-Research/1.0"
            })

            response = session.get(
                source_url,
                timeout=30,
                allow_redirects=False,
            )

            if response.status_code in {403, 429}:
                raise RuntimeError(
                    f"Website trả HTTP {response.status_code}; dừng tải."
                )

            response.raise_for_status()

            if response.status_code != 200:
                raise ValueError("Phản hồi không phải HTTP 200.")

            html_bytes = response.content
            soup_check = BeautifulSoup(html_bytes, "html.parser")

            if soup_check.select_one("main h1") is None:
                raise ValueError(
                    "HTML không có cấu trúc dự kiến; chưa lưu làm dữ liệu."
                )

            html_path.write_bytes(html_bytes)
            metadata_path.write_text(
                json.dumps({
                    "source_site": "esportsearnings",
                    "source_game_id": game_id,
                    "source_url": source_url,
                    "crawled_at": datetime.now(timezone.utc).isoformat(),
                    "http_status": response.status_code,
                    "source_html_file": html_path.name,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    soup = BeautifulSoup(html_bytes, "html.parser")
    tournament_records = []
    event_records = []

    for link in soup.select("main td.detail_list_tournament a[href]"):
        url = urljoin(source_url, link["href"])
        parsed_link = urlparse(url)

        if parsed_link.hostname != "www.esportsearnings.com":
            continue

        name = link.get_text(" ", strip=True)

        tournament_match = re.match(
            r"/tournaments/(\d+)(?:-|/|$)", parsed_link.path
        )
        event_match = re.match(
            r"/events/(\d+)(?:-|/|$)", parsed_link.path
        )

        common = {
            "source_game_id": game_id,
            "source_url": url,
            "discovered_from_url": source_url,
            "source_html_file": html_path.relative_to(RAW_DIR).as_posix(),
        }

        if tournament_match:
            tournament_records.append({
                **common,
                "source_tournament_id": tournament_match.group(1),
                "tournament_name": name,
            })

        elif event_match:
            event_records.append({
                **common,
                "source_event_id": event_match.group(1),
                "event_name": name,
            })

    tournament_columns = [
        "source_game_id",
        "source_tournament_id",
        "tournament_name",
        "source_url",
        "discovered_from_url",
        "source_html_file",
    ]
    event_columns = [
        "source_game_id",
        "source_event_id",
        "event_name",
        "source_url",
        "discovered_from_url",
        "source_html_file",
    ]

    tournaments = pd.DataFrame(
        tournament_records, columns=tournament_columns
    ).drop_duplicates(subset=["source_tournament_id"])

    events = pd.DataFrame(
        event_records, columns=event_columns
    ).drop_duplicates(subset=["source_event_id"])

    if tournaments.empty and events.empty:
        raise ValueError(
            "Không tìm được URL; cần kiểm tra HTML và selector."
        )

    tournaments.to_csv(
        output_dir / "direct_tournament_urls.csv",
        index=False,
        encoding="utf-8-sig",
    )
    events.to_csv(
        output_dir / "event_urls.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(f"\nGame: {game['game_name']} | ID nguồn: {game_id}")
    print(f"URL giải trực tiếp: {len(tournaments):,}")
    print(f"URL sự kiện cần mở tiếp: {len(events):,}")
    print("Kết quả:", output_dir)


if __name__ == "__main__":
    main()
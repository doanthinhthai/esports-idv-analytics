from pathlib import Path
from urllib.parse import urljoin
import re

import pandas as pd
from bs4 import BeautifulSoup

PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw" / "esportsearnings"

HTML_PATH = RAW_DIR / "245_csgo_events.html"
SOURCE_URL = (
    "https://www.esportsearnings.com/games/"
    "245-counter-strike-global-offensive/events"
)


def main():
    soup = BeautifulSoup(HTML_PATH.read_bytes(), "html.parser")

    tournament_records = []
    event_records = []

    for link in soup.select("main td.detail_list_tournament a[href]"):
        url = urljoin(SOURCE_URL, link["href"])
        name = link.get_text(" ", strip=True)

        tournament_match = re.search(r"/tournaments/(\+?\d+)", url)
        event_match = re.search(r"/events/(\d+)", url)

        if tournament_match:
            tournament_records.append({
                "source_game_id": "245",
                "source_tournament_id": tournament_match.group(1),
                "tournament_name": name,
                "source_url": url,
                "discovered_from_url": SOURCE_URL,
                "source_html_file": HTML_PATH.name,
            })

        elif event_match:
            event_records.append({
                "source_game_id": "245",
                "source_event_id": event_match.group(1),
                "event_name": name,
                "source_url": url,
                "discovered_from_url": SOURCE_URL,
                "source_html_file": HTML_PATH.name,
            })

    tournaments = pd.DataFrame(tournament_records)
    events = pd.DataFrame(event_records)

    if not tournaments.empty:
        tournaments = tournaments.drop_duplicates(
            subset=["source_tournament_id"]
        )

    if not events.empty:
        events = events.drop_duplicates(subset=["source_event_id"])

    tournaments_path = RAW_DIR / "245_direct_tournament_urls.csv"
    events_path = RAW_DIR / "245_event_urls.csv"

    tournaments.to_csv(
        tournaments_path, index=False, encoding="utf-8-sig"
    )
    events.to_csv(
        events_path, index=False, encoding="utf-8-sig"
    )

    print(f"Số URL giải đấu trực tiếp: {len(tournaments):,}")
    print(f"Số URL sự kiện cần mở tiếp: {len(events):,}")
    print("Đã lưu:", tournaments_path)
    print("Đã lưu:", events_path)

    print("\n5 giải đầu tiên:")
    print(tournaments.head().to_string(index=False))


if __name__ == "__main__":
    main()
from pathlib import Path
from urllib.parse import urljoin
import re

import pandas as pd
from bs4 import BeautifulSoup

PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw" / "esportsearnings"

HTML_PATH = RAW_DIR / "9449_mesa_league_csgo.html"
EVENT_URL = "https://www.esportsearnings.com/events/9449-mesa-league-csgo"
GAME_ID = "245"


def main():
    soup = BeautifulSoup(HTML_PATH.read_bytes(), "html.parser")
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

        game_match = re.match(r"/games/(\d+)(?:-|/|$)", game_link["href"])

        # Chỉ lấy giải thuộc CS:GO, tránh lẫn game khác.
        if not game_match or game_match.group(1) != GAME_ID:
            continue

        url = urljoin(EVENT_URL, tournament_link["href"])
        tournament_match = re.search(r"/tournaments/(\d+)", url)

        if tournament_match is None:
            continue

        records.append({
            "source_game_id": GAME_ID,
            "source_tournament_id": tournament_match.group(1),
            "tournament_name": tournament_link.get_text(" ", strip=True),
            "source_url": url,
            "discovered_from_url": EVENT_URL,
            "source_html_file": HTML_PATH.name,
        })

    if not records:
        raise ValueError("Không tìm thấy URL giải con thuộc CS:GO.")

    children = pd.DataFrame(records).drop_duplicates(
        subset=["source_tournament_id"]
    )

    children_path = RAW_DIR / "9449_tournament_urls.csv"
    children.to_csv(children_path, index=False, encoding="utf-8-sig")

    direct = pd.read_csv(
        RAW_DIR / "245_direct_tournament_urls.csv",
        dtype=str,
    )

    combined = pd.concat([direct, children], ignore_index=True)
    combined = combined.drop_duplicates(
        subset=["source_tournament_id"]
    )

    combined_path = RAW_DIR / "245_tournament_urls_pilot.csv"
    combined.to_csv(combined_path, index=False, encoding="utf-8-sig")

    print(children[["source_tournament_id", "tournament_name"]]
          .to_string(index=False))
    print(f"\nSố giải con tìm được: {len(children)}")
    print(f"Số URL trực tiếp ban đầu: {len(direct)}")
    print(f"Số URL sau khi gộp, loại trùng: {len(combined)}")
    print(f"Số URL mới bổ sung: {len(combined) - len(direct)}")
    print("Đã lưu:", children_path)
    print("Đã lưu:", combined_path)


if __name__ == "__main__":
    main()
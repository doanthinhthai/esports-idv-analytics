from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup


PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw" / "esportsearnings"

BASE_URL = "https://www.esportsearnings.com"


def main():
    html_path = RAW_DIR / "sample_tournament.html"
    soup = BeautifulSoup(html_path.read_bytes(), "html.parser")

    heading = next(
        (
            h for h in soup.select("h2.detail_box_title")
            if h.get_text(" ", strip=True) == "Similar Tournaments"
        ),
        None,
    )

    if heading is None:
        raise ValueError("Không tìm thấy Similar Tournaments.")

    container = heading.parent
    records = []

    for link in container.select('a[href^="/tournaments/"]'):
        records.append({
            "tournament_name": link.get_text(" ", strip=True),
            "source_url": urljoin(BASE_URL, link["href"]),
        })

    df = pd.DataFrame(
        records,
        columns=["tournament_name", "source_url"],
    ).drop_duplicates(subset=["source_url"])

    if df.empty:
        raise ValueError("Không lấy được URL giải nào.")

    output_path = RAW_DIR / "candidate_tournament_urls.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(df.to_string(index=False))
    print(f"\nĐã lưu {len(df)} URL vào: {output_path}")


if __name__ == "__main__":
    main()
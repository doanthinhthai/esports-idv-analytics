from pathlib import Path
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

PROJECT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_DIR / "data" / "raw" / "esportsearnings"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://www.esportsearnings.com/events/9449-mesa-league-csgo"

def main():
    response = requests.get(
        URL,
        headers={"User-Agent": "Esports-IDV-Student-Research/1.0"},
        timeout=30,
    )

    print("HTTP status:", response.status_code)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    print("Page title:", title)

    html_path = OUTPUT_DIR / "9449_mesa_league_csgo.html"
    html_path.write_bytes(response.content)

    print("Saved HTML:", html_path)
    print("Crawled at:", datetime.now(timezone.utc).isoformat())

    print("\nFIRST 50 TEXT LINES:")
    lines = soup.get_text("\n", strip=True).splitlines()
    for line in lines[:50]:
        print(line)


if __name__ == "__main__":
    main()
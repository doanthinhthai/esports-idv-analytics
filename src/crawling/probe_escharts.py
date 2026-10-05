from pathlib import Path
from datetime import datetime, timezone
from urllib.robotparser import RobotFileParser
import json
import re
import time

import requests
from bs4 import BeautifulSoup


PROJECT_DIR = Path(__file__).resolve().parents[2]

URL = (
    "https://escharts.com/tournaments/csgo/"
    "blasttv-paris-major-2023"
)
ROBOTS_URL = "https://escharts.com/robots.txt"
USER_AGENT = "Esports-IDV-Student-Research/1.0"

METRIC_LABELS = {
    "peak_viewers": ["peak viewers"],
    "average_viewers": ["average viewers"],
    "hours_watched": ["hours watched"],
    "airtime": ["airtime", "air time"],
}


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    run_id = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    output = (
        PROJECT_DIR / "data" / "raw"
        / "escharts" / "probes" / run_id
    )
    output.mkdir(parents=True, exist_ok=False)

    with requests.Session() as session:
        session.headers["User-Agent"] = USER_AGENT

        # Kiểm tra robots trước. Không tự thử lại nếu gặp lỗi.
        try:
            robots_response = session.get(
                ROBOTS_URL,
                timeout=30,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            print(f"Không đọc được robots.txt: {error}")
            print("Dừng test. Kiểm tra bằng trình duyệt trước.")
            return

        (output / "robots.txt").write_bytes(
            robots_response.content
        )
        print("robots.txt HTTP:", robots_response.status_code)

        if robots_response.status_code != 200:
            print("Chưa xác minh được robots. Không tải trang giải.")
            print("Thư mục kiểm tra:", output)
            return

        robots = RobotFileParser()
        robots.set_url(ROBOTS_URL)
        robots.parse(robots_response.text.splitlines())

        if not robots.can_fetch(USER_AGENT, URL):
            print("robots.txt không cho phép bot này lấy URL mẫu.")
            print("Dừng; không tìm cách vượt hạn chế.")
            return

        wait_seconds = max(
            2,
            robots.crawl_delay(USER_AGENT) or 0,
        )
        time.sleep(wait_seconds)

        try:
            response = session.get(
                URL,
                timeout=30,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            print(f"Lỗi tải trang mẫu: {error}")
            return

    (output / "page.html").write_bytes(response.content)

    metadata = {
        "source_site": "escharts",
        "requested_url": URL,
        "response_url": response.url,
        "crawled_at": now(),
        "http_status": response.status_code,
        "content_type": response.headers.get("Content-Type"),
        "retry_after": response.headers.get("Retry-After"),
        "redirect_location": response.headers.get("Location"),
        "response_bytes": len(response.content),
    }

    print("Trang giải HTTP:", response.status_code)
    print("Kích thước phản hồi:", len(response.content), "bytes")

    if response.status_code != 200:
        (output / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("Không parse phản hồi không phải HTTP 200.")
        print("Không tự retry hoặc vượt chặn.")
        print("Thư mục kiểm tra:", output)
        return

    soup = BeautifulSoup(response.content, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    metadata["page_title"] = title
    print("Tiêu đề:", title)

    # Loại script/style khỏi bản text dùng để kiểm tra.
    # page.html gốc vẫn được giữ nguyên.
    for element in soup(["script", "style", "noscript"]):
        element.decompose()

    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    (output / "page_text.txt").write_text(
        text,
        encoding="utf-8",
    )

    challenge_title = any(
        marker in title.lower()
        for marker in [
            "just a moment",
            "access denied",
            "attention required",
        ]
    )
    metadata["possible_challenge"] = challenge_title

    if challenge_title:
        print("Có dấu hiệu trang kiểm tra truy cập, không phải dữ liệu giải.")
    else:
        print("\nKIỂM TRA NHÃN CHỈ SỐ")
        lower_text = text.lower()

        for field, labels in METRIC_LABELS.items():
            positions = [
                lower_text.find(label)
                for label in labels
                if lower_text.find(label) >= 0
            ]

            if not positions:
                print(f"{field}: chưa thấy nhãn trong HTML text")
                continue

            position = min(positions)
            snippet = text[
                max(0, position - 60): position + 220
            ]
            print(f"\n{field}: tìm thấy nhãn")
            print(snippet)

    (output / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nĐã lưu tại:", output)
    print("Đây là kiểm tra truy cập, chưa phải parser người xem.")


if __name__ == "__main__":
    main()
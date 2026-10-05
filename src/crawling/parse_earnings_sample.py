from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin
import re

import pandas as pd
from bs4 import BeautifulSoup


PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw" / "esportsearnings"

HTML_PATH = RAW_DIR / "52807_pgl_antwerp_2022.html"
CSV_PATH = RAW_DIR / "52807_tournament_sample.csv"

SOURCE_URL = (
    "https://www.esportsearnings.com/tournaments/"
    "52807-pgl-major-antwerp-2022.html"
)


def parse_tournament(html_bytes,
    source_url=SOURCE_URL,
    html_filename=HTML_PATH.name,
    *,
    allow_invalid_dates=False,
):
    soup = BeautifulSoup(html_bytes, "html.parser")

    title = soup.select_one("main h1.info_box_title")
    if title is None:
        raise ValueError("Không tìm thấy tên giải trong HTML.")

    info_box = title.find_parent("div", class_="info_box")
    if info_box is None:
        raise ValueError("Không tìm thấy khối thông tin giải.")

    # Đọc từng cặp nhãn–giá trị trong khối thông tin chính.
    fields = {}
    field_elements = {}

    for row in info_box.select(".format_row"):
        label = row.select_one(".info_text_header")
        value = row.select_one(".info_text_value")

        if label is None or value is None:
            continue

        key = label.get_text(" ", strip=True).rstrip(":")
        fields[key] = value.get_text(" ", strip=True)
        field_elements[key] = value

    required = ["Date", "Game", "Prize Pool", "Currency"]
    missing = [key for key in required if not fields.get(key)]

    if missing:
        raise ValueError(f"Thiếu thông tin bắt buộc: {missing}")

    # Giữ ngày nguyên bản và tách ngày bắt đầu/kết thúc.
    date_raw = fields["Date"]
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", date_raw)

    if not dates:
        raise ValueError(f"Không đọc được ngày: {date_raw}")

    source_start_date = dates[0]
    source_end_date = dates[-1]
    start_date = source_start_date
    end_date = source_end_date
    date_validation_status = "valid"

    if source_start_date > source_end_date:
        if not allow_invalid_dates:
            raise ValueError("Ngày bắt đầu lớn hơn ngày kết thúc.")

        # Giữ ngày nguồn để kiểm tra, không tự đảo hoặc sửa ngày.
        start_date = None
        end_date = None
        date_validation_status = "invalid_date"

    # Giữ nguyên văn bản tiền thưởng từ nguồn.
    prize_raw = fields["Prize Pool"]
    currency_raw = fields["Currency"]

    # Ví dụ: "$350,000.00 ($3,444.00 USD)"
    # Nếu nguồn đã cung cấp giá trị USD trong ngoặc, lấy giá trị đó.
    usd_match = re.search(
        r"\(\s*\$\s*([\d,]+(?:\.\d+)?)\s+USD\s*\)",
        prize_raw,
        flags=re.IGNORECASE,
    )

    if usd_match is not None:
        prize_pool_usd = float(
            usd_match.group(1).replace(",", "")
        )

    elif currency_raw.upper().startswith("USD"):
        # Ví dụ: "$10,000.00"
        prize_value = (
            prize_raw
            .replace("$", "")
            .replace(",", "")
            .strip()
        )
        prize_pool_usd = float(prize_value)

    else:
        # Không tự coi tiền ngoại tệ là USD.
        raise ValueError(
            "Nguồn không cung cấp giá trị USD đọc được: "
            f"currency={currency_raw}; prize={prize_raw}"
        )

    if prize_pool_usd < 0:
        raise ValueError("Tiền thưởng âm.")

        game_link = field_elements["Game"].select_one("a[href]")
        game_url = (
            urljoin(source_url, game_link["href"])
            if game_link is not None
            else None
        )
    game_link = field_elements["Game"].select_one("a[href]")

    game_url = (
        urljoin(source_url, game_link["href"])
        if game_link is not None
        else None
    )
    tournament_id_match = re.search(r"/tournaments/(\d+)", source_url)
    game_id_match = re.search(r"/games/(\d+)", game_url or "")
    
    return {
        "source_site": "esportsearnings",
        "source_url": source_url,
        "source_tournament_id": tournament_id_match.group(1),
        "tournament_name_raw": title.get_text(" ", strip=True),
        "location_raw": fields.get("Location"),
        "date_raw": date_raw,
        "source_start_date": source_start_date,
        "source_end_date": source_end_date,
        "start_date": start_date,
        "end_date": end_date,
        "date_validation_status": date_validation_status,
        "game_name_raw": fields["Game"],
        "source_game_id": (
            game_id_match.group(1) if game_id_match else None
        ),
        "game_source_url": game_url,
        "prize_pool_raw": prize_raw,
        "prize_pool_usd": prize_pool_usd,
        "currency_raw": fields["Currency"],
        "source_html_file": html_filename,
        "parsed_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    if not HTML_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy HTML: {HTML_PATH}")

    record = parse_tournament(HTML_PATH.read_bytes())

    df = pd.DataFrame([record])
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

    print(df.to_string(index=False))
    print(f"\nĐã xuất {len(df)} giải vào: {CSV_PATH}")


if __name__ == "__main__":
    main()
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin
import re

import pandas as pd
from bs4 import BeautifulSoup

from parse_earnings_sample import parse_tournament


PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw" / "esportsearnings"

HTML_PATH = (
    RAW_DIR
    / "batch_runs"
    / "20261004T170535427493Z"
    / "html"
    / "27168.html"
)

CSV_PATH = RAW_DIR / "27168_placements_recheck.csv"

SOURCE_URL = (
    "https://www.esportsearnings.com/tournaments/"
    "27168-wesg-2017-csgo-male"
)


def parse_placements(html_bytes, source_url=SOURCE_URL, html_filename=HTML_PATH.name,):
    soup = BeautifulSoup(html_bytes, "html.parser")
    main = soup.select_one("main")

    if main is None:
        raise ValueError("Không tìm thấy nội dung chính của trang.")

    tournament_match = re.search(r"/tournaments/(\d+)", source_url)
    if tournament_match is None:
        raise ValueError("Không đọc được ID giải từ URL.")

    tournament_id = tournament_match.group(1)
    parsed_at = datetime.now(timezone.utc).isoformat()

    # Trang mẫu có hai kiểu hiển thị:
    # medalist: các hạng đầu
    # participant: các hạng còn lại
    rank_elements = main.select(
        ".tournament_medalist_rank, "
        ".tournament_participant_rank"
    )

    records = []

    for rank_element in rank_elements:
        # Khối chứa hạng, danh sách đội và tiền thưởng.
        result_block = rank_element.parent
        rank_raw = rank_element.get_text(" ", strip=True)

        prize_element = result_block.select_one(
            ".tournament_medalist_prize, "
            ".tournament_participant_prize"
        )

        if prize_element is None:
            raise ValueError(
                f"Không tìm thấy tiền thưởng cho hạng {rank_raw}."
            )

        prize_raw = prize_element.get_text(" ", strip=True)

        # Ví dụ: "$250,000.00 ($2,460.00 USD)"
        usd_match = re.search(
            r"\(\s*\$\s*([\d,]+(?:\.\d+)?)\s+USD\s*\)",
            prize_raw,
            flags=re.IGNORECASE,
        )

        if usd_match is not None:
            prize_usd = float(
                usd_match.group(1).replace(",", "")
            )

        else:
            # Kiểm tra Currency của giải trước khi đọc số không có nhãn USD.
            title = main.select_one("h1.info_box_title")
            info_box = (
                title.find_parent("div", class_="info_box")
                if title is not None
                else None
            )

            currency_raw = None

            if info_box is not None:
                for row in info_box.select(".format_row"):
                    label = row.select_one(".info_text_header")
                    value = row.select_one(".info_text_value")

                    if label is None or value is None:
                        continue

                    if label.get_text(" ", strip=True).rstrip(":") == "Currency":
                        currency_raw = value.get_text(" ", strip=True)
                        break

            if not currency_raw or not currency_raw.upper().startswith("USD"):
                raise ValueError(
                    "Không tìm thấy tiền thưởng đội quy đổi USD: "
                    f"currency={currency_raw}; prize={prize_raw}"
                )

            prize_usd = float(
                prize_raw.replace("$", "").replace(",", "").strip()
            )

        if prize_usd < 0:
            raise ValueError(f"Tiền thưởng đội âm: {prize_raw}")

        # Chỉ chọn link tên đội, tránh lấy nhầm link tuyển thủ.
        team_elements = result_block.select(
            ".tournament_team_medalist_name, "
            ".tournament_team_participant_name"
        )

        if not team_elements:
            raise ValueError(
                f"Không tìm thấy đội cho hạng {rank_raw}."
            )

        # Giữ cả khoảng hạng: 3rd-4th => 3 và 4.
        rank_numbers = [
            int(value) for value in re.findall(r"\d+", rank_raw)
        ]

        if not rank_numbers:
            label = rank_raw.strip().upper()

            if label not in {"WIN", "LOSE"}:
                raise ValueError(f"Không đọc được hạng: {rank_raw}")

        for team_element in team_elements:
            team_name = team_element.get_text(" ", strip=True)

            if not team_name:
                raise ValueError(f"Tên đội trống tại hạng {rank_raw}.")

            team_link = team_element.select_one('a[href^="/teams/"]')

            # Nguồn có thể không cung cấp link hoặc ID đội.
            team_url = None
            team_id = None

            if team_link is not None:
                team_url = urljoin(source_url, team_link["href"])
                team_match = re.search(r"/teams/(\d+)", team_url)

                if team_match is not None:
                    team_id = team_match.group(1)

            records.append({
                "source_site": "esportsearnings",
                "source_url": source_url,
                "source_tournament_id": tournament_id,
                "source_team_id": team_id,
                "team_name_raw": team_name,
                "team_source_url": team_url,
                "rank_raw": rank_raw,
                "rank_min": min(rank_numbers) if rank_numbers else None,
                "rank_max": max(rank_numbers) if rank_numbers else None,
                "result_outcome": rank_raw.upper() if rank_raw.upper() in {"WIN", "LOSE"} else None,
                "prize_money_raw": prize_raw,
                "prize_money_usd": prize_usd,
                "source_html_file": html_filename,
                "parsed_at": parsed_at,
            })

    if not records:
        raise ValueError("Không lấy được kết quả thi đấu nào.")

    return pd.DataFrame(records)


def main():
    if not HTML_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy HTML: {HTML_PATH}")

    html_bytes = HTML_PATH.read_bytes()
    soup_check = BeautifulSoup(html_bytes, "html.parser")
    title_check = soup_check.select_one("main h1.info_box_title")

    print("Đang đọc HTML:", HTML_PATH)
    print(
        "Tên giải trong HTML:",
        title_check.get_text(" ", strip=True) if title_check else "KHÔNG TÌM THẤY",
    )

    df = parse_placements(HTML_PATH.read_bytes())

    tournament_record = parse_tournament(
        html_bytes,
        source_url=SOURCE_URL,
        html_filename=HTML_PATH.name,
    )

    tournament_df = pd.DataFrame([tournament_record])

    if len(tournament_df) != 1:
        raise ValueError("CSV thông tin mẫu phải chứa đúng một giải.")

    expected_id = tournament_df.iloc[0]["source_tournament_id"]

    if not df["source_tournament_id"].astype(str).eq(expected_id).all():
        raise ValueError("ID giải của placements và thông tin giải không khớp.")

    if df.duplicated(
        subset=["source_tournament_id", "team_name_raw"]
    ).any():
        raise ValueError("Có đội bị lặp trong cùng giải.")

    expected_prize = float(tournament_df.iloc[0]["prize_pool_usd"])
    total_prize = df["prize_money_usd"].sum()
    difference = total_prize - expected_prize

    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

    print(df[
        ["team_name_raw", "rank_raw", "prize_money_usd"]
    ].to_string(index=False))

    print(f"\nSố đội đã lấy: {len(df)}")
    print(f"Tổng thưởng theo thông tin giải: ${expected_prize:,.2f}")
    print(f"Tổng thưởng các đội đã lấy: ${total_prize:,.2f}")
    print(f"Chênh lệch: ${difference:,.2f}")

    if abs(difference) <= 0.01:
        print("Kiểm tra tổng thưởng: KHỚP")
    else:
        print(
            "Kiểm tra tổng thưởng: CHƯA KHỚP. "
            "Cần đối chiếu HTML xem có bỏ sót đội hoặc đọc sai tiền thưởng."
        )

    print(f"Đã lưu: {CSV_PATH}")


if __name__ == "__main__":
    main()

from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from collections import Counter
from urllib.parse import urlparse
import csv
import json
import re
import sqlite3

from bs4 import BeautifulSoup


PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data/raw/esportsearnings"
DB_PATH = RAW_DIR / "sqlite_pipeline/crawl.sqlite3"
REPORT_DIR = PROJECT_DIR / "reports/data_quality"


def money(value):
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("Số tiền không hợp lệ.")
    return number.quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def read_countries(path):
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    main = soup.select_one("main")

    if main is None:
        raise ValueError("Không có main.")

    heading = next(
        (
            tag for tag in main.select("h2")
            if tag.get_text(" ", strip=True)
            == "Prize Money By Country"
        ),
        None,
    )

    if heading is None:
        raise ValueError("Không có bảng Prize Money By Country.")

    records = []

    # Chỉ đọc phần sau tiêu đề quốc gia, trước tiêu đề tiếp theo.
    for sibling in heading.next_siblings:
        if getattr(sibling, "name", None) == "h2":
            break
        if not hasattr(sibling, "select"):
            continue

        for row in sibling.select("tr.format_row"):
            cells = row.find_all("td", recursive=False)
            if len(cells) != 4:
                continue

            links = cells[1].select('a[href^="/countries/"]')
            if not links:
                continue

            code = urlparse(links[0]["href"]).path.rstrip("/").split("/")[-1]
            name = cells[1].get_text(" ", strip=True)
            prize_raw = cells[2].get_text(" ", strip=True)
            count_raw = cells[3].get_text(" ", strip=True)

            if not re.fullmatch(
                r"\$\s*\d[\d,]*(?:\.\d{1,2})?", prize_raw
            ):
                raise ValueError(
                    f"Không đọc được tiền quốc gia: {prize_raw}"
                )

            count_match = re.fullmatch(
                r"(\d+)\s+Players?", count_raw
            )
            if count_match is None:
                raise ValueError(
                    f"Không đọc được số người: {count_raw}"
                )

            records.append({
                "country_code": code,
                "country_name_raw": name,
                "prize_money_raw": prize_raw,
                "prize_money_usd": str(money(
                    prize_raw.replace("$", "").replace(",", "").strip()
                )),
                "source_player_count": int(count_match.group(1)),
            })

    if not records:
        raise ValueError("Bảng quốc gia không có dòng đọc được.")

    codes = [item["country_code"] for item in records]
    if len(codes) != len(set(codes)):
        raise ValueError("Có quốc gia bị lặp; cần kiểm tra HTML.")

    return records


def main():
    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)

    with sqlite3.connect(
        DB_PATH.resolve().as_uri() + "?mode=ro", uri=True
    ) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("""
            SELECT tournament_id, game_slug, source_url,
                   html_file, tournament_json, placements_json
            FROM results
            WHERE status = 'needs_review'
            ORDER BY game_slug, tournament_id
        """).fetchall()

    comparisons = []
    country_rows = []

    for row in rows:
        tournament = json.loads(row["tournament_json"] or "{}")
        placements = json.loads(row["placements_json"] or "[]")
        expected = money(tournament["prize_pool_usd"])
        placement_total = sum(
            (money(item["prize_money_usd"]) for item in placements),
            Decimal("0"),
        )

        item = {
            "game_slug": row["game_slug"],
            "tournament_id": row["tournament_id"],
            "tournament_name_raw": tournament.get("tournament_name_raw"),
            "expected_usd": str(expected),
            "placements_total_usd": str(placement_total),
            "placements_difference_usd": str(placement_total - expected),
            "country_total_usd": None,
            "country_difference_usd": None,
            "country_check": "unavailable",
            "error": None,
            "source_url": row["source_url"],
            "html_file": row["html_file"],
        }

        try:
            if not row["html_file"]:
                raise ValueError("Thiếu đường dẫn HTML.")

            countries = read_countries(RAW_DIR / row["html_file"])
            total = sum(
                (money(country["prize_money_usd"]) for country in countries),
                Decimal("0"),
            )
            difference = total - expected

            item["country_total_usd"] = str(total)
            item["country_difference_usd"] = str(difference)
            item["country_check"] = (
                "matches_pool" if difference == 0
                else "differs_from_pool"
            )

            for country in countries:
                country_rows.append({
                    "game_slug": row["game_slug"],
                    "tournament_id": row["tournament_id"],
                    **country,
                    "source_url": row["source_url"],
                    "html_file": row["html_file"],
                })

        except (ValueError, OSError, ArithmeticError) as error:
            item["error"] = str(error)

        comparisons.append(item)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = REPORT_DIR / f"country_prize_audit_{run_id}"
    output.mkdir(parents=True, exist_ok=False)

    for filename, records in [
        ("comparison.csv", comparisons),
        ("country_rows.csv", country_rows),
    ]:
        if records:
            with (output / filename).open(
                "w", encoding="utf-8-sig", newline=""
            ) as file:
                writer = csv.DictWriter(
                    file, fieldnames=list(records[0])
                )
                writer.writeheader()
                writer.writerows(records)

    summary = {
        "review_count": len(comparisons),
        "country_checks": dict(Counter(
            item["country_check"] for item in comparisons
        )),
        "country_row_count": len(country_rows),
        "note": (
            "Đối chiếu bảng quốc gia trong HTML cache; "
            "không xác minh số tiền từng đội, không sửa SQLite."
        ),
    }

    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("TÓM TẮT")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\nBA GIẢI ĐANG KIỂM TRA")
    for item in comparisons:
        if item["tournament_id"] in {"61725", "48847", "61566"}:
            print(
                item["tournament_id"],
                item["tournament_name_raw"],
                f"pool={item['expected_usd']}",
                f"placements={item['placements_total_usd']}",
                f"countries={item['country_total_usd']}",
                item["country_check"],
                item["error"] or "",
                sep=" | ",
            )

    print("\nBáo cáo:", output)
    print("Offline; không sửa dữ liệu crawler.")


if __name__ == "__main__":
    main()
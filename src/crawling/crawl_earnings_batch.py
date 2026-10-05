from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse
import json
import re
import time
import argparse

import pandas as pd
import requests

from parse_earnings_sample import parse_tournament
from parse_placements_sample import parse_placements
from prize_validation import validate_prizes


PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw" / "esportsearnings"

URL_LIST_PATH = (
    RAW_DIR
    / "245_event_discovery"
    / "245_all_tournament_urls.csv"
)

MAX_URLS = 100
DELAY_SECONDS = 1


def main():
    parser = argparse.ArgumentParser(description="Crawl chi tiết, dùng lại HTML và tiếp tục batch.")
    parser.add_argument("--limit", type=int, default=MAX_URLS, help="0: toàn bộ URL")
    parser.add_argument("--offline", action="store_true", help="Chỉ parse HTML đã lưu")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit phải >= 0")
    url_df = pd.read_csv(URL_LIST_PATH)

    if "source_url" not in url_df.columns:
        raise ValueError("Danh sách URL thiếu cột source_url.")

    urls = (
        url_df["source_url"]
        .dropna()
        .astype(str)
        .str.strip()
        .drop_duplicates()
        .tolist()
    )
    if args.limit:
        urls = urls[:args.limit]

    if not urls:
        raise ValueError("Không có URL để crawl.")

    # Mỗi lần chạy có thư mục riêng, giữ kết quả lần trước.
    run_dir = RAW_DIR / "batch_runs" / "csgo_resumable"
    html_dir = run_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)

    tournaments = []
    placements = []
    audit_records = []
    audit_path = run_dir / "crawl_audit.csv"
    if audit_path.exists():
        audit_records = pd.read_csv(audit_path).where(lambda df: df.notna(), None).to_dict("records")
    if (run_dir / "tournaments.csv").exists():
        tournaments = pd.read_csv(run_dir / "tournaments.csv", dtype={"source_tournament_id": str}).to_dict("records")
    if (run_dir / "placements.csv").exists():
        placements = [pd.read_csv(run_dir / "placements.csv", dtype={"source_tournament_id": str})]
    completed = {row["requested_url"] for row in audit_records if row["status"] != "failed"}
    cached = {}
    for path in sorted((RAW_DIR / "batch_runs").glob("*/html/*.html")):
        if path.with_suffix(".json").exists():
            cached[path.stem] = path

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Esports-IDV-Student-Research/1.0"
    })

    try:
        for index, url in enumerate(urls, start=1):
            if url in completed:
                continue
            print(f"\n[{index}/{len(urls)}] {url}")

            audit = {
                "requested_url": url,
                "status": "failed",
                "error": None,
            }
            stop_requested = False

            try:
                parsed_url = urlparse(url)

                if (
                    parsed_url.scheme != "https"
                    or parsed_url.hostname not in {
                        "www.esportsearnings.com",
                        "esportsearnings.com",
                    }
                ):
                    raise ValueError("URL không thuộc nguồn dự kiến.")

                id_match = re.search(
                    r"/tournaments/(\d+)",
                    parsed_url.path,
                )

                if id_match is None:
                    raise ValueError("URL không phải trang chi tiết giải.")

                tournament_id = id_match.group(1)

                cached_path = cached.get(tournament_id)
                if cached_path is not None:
                    metadata = json.loads(cached_path.with_suffix(".json").read_text(encoding="utf-8"))
                    html_bytes = cached_path.read_bytes()
                    final_url = metadata["final_url"]
                    crawled_at = metadata["crawled_at"]
                    http_status = metadata["http_status"]
                    html_filename = cached_path.relative_to(RAW_DIR).as_posix()
                    print("Đọc HTML đã lưu.")
                elif args.offline:
                    print("Bỏ qua: chưa có HTML; chế độ offline.")
                    continue
                else:
                    time.sleep(DELAY_SECONDS)
                    response = session.get(url, timeout=30)
                    if response.status_code in {403, 429}:
                        stop_requested = True
                    response.raise_for_status()
                    final_url = response.url
                    if urlparse(final_url).hostname not in {"www.esportsearnings.com", "esportsearnings.com"}:
                        raise ValueError("Trang chuyển hướng ra ngoài nguồn.")
                    html_bytes = response.content
                    crawled_at = datetime.now(timezone.utc).isoformat()
                    http_status = response.status_code
                    html_path = html_dir / f"{tournament_id}.html"
                    html_path.write_bytes(html_bytes)
                    html_path.with_suffix(".json").write_text(json.dumps({
                        "requested_url": url, "final_url": final_url,
                        "source_tournament_id": tournament_id,
                        "crawled_at": crawled_at, "http_status": http_status,
                    }, ensure_ascii=False, indent=2), encoding="utf-8")
                    html_filename = html_path.relative_to(RAW_DIR).as_posix()

                audit.update({
                    "http_status": http_status,
                    "final_url": final_url,
                    "crawled_at": crawled_at,
                })

                tournament = parse_tournament(
                    html_bytes,
                    source_url=final_url,
                    html_filename=html_filename,
                )
                tournament["crawled_at"] = crawled_at

                # Giữ thông tin giải dù parser placements gặp lỗi.
                tournament["placements_status"] = "failed"
                tournaments.append(tournament)

                audit["tournament_name"] = tournament[
                    "tournament_name_raw"
                ]
                audit["status"] = "tournament_only"

                team_results = parse_placements(
                    html_bytes,
                    source_url=final_url,
                    html_filename=html_filename,
                )

                if team_results.duplicated(
                    subset=["source_tournament_id", "team_name_raw"]
                ).any():
                    raise ValueError("Đội bị trùng trong cùng giải.")

                expected = float(tournament["prize_pool_usd"])
                extracted, difference, status = validate_prizes(
                    expected, team_results["prize_money_usd"]
                )

                tournament["placements_status"] = status
                team_results["validation_status"] = status
                team_results["crawled_at"] = crawled_at
                placements.append(team_results)

                audit.update({
                    "status": status,
                    "team_count": len(team_results),
                    "expected_prize_usd": expected,
                    "extracted_prize_usd": extracted,
                    "difference_usd": difference,
                })

                print(
                    f"{tournament['tournament_name_raw']} | "
                    f"{len(team_results)} đội | {status}"
                )

            except (
                requests.RequestException,
                OSError,
                ValueError,
                KeyError,
                TypeError,
            ) as error:
                audit["error"] = str(error)
                print(f"CẦN KIỂM TRA: {error}")

            audit_records = [row for row in audit_records if row["requested_url"] != url]
            audit_records.append(audit)

            # Lưu tiến độ sau mỗi URL.
            pd.DataFrame(audit_records).to_csv(
                run_dir / "crawl_audit.csv",
                index=False,
                encoding="utf-8-sig",
            )

            if tournaments:
                pd.DataFrame(tournaments).to_csv(
                    run_dir / "tournaments.csv",
                    index=False,
                    encoding="utf-8-sig",
                )

            if placements:
                pd.concat(placements, ignore_index=True).to_csv(
                    run_dir / "placements.csv",
                    index=False,
                    encoding="utf-8-sig",
                )

            if stop_requested:
                print("Dừng vì website trả về HTTP 403 hoặc 429.")
                break


    finally:
        session.close()

    print(f"\nĐã thử: {len(audit_records)} URL")
    print(f"Đã lấy thông tin: {len(tournaments)} giải")
    print(f"Kết quả lưu tại: {run_dir}")


if __name__ == "__main__":
    main()

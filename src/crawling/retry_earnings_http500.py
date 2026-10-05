import argparse
import json
import sqlite3
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd
import requests

import crawl_games_sqlite as crawler


def main():
    parser = argparse.ArgumentParser(
        description="Retry riêng các bản ghi failed do HTTP 500."
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--delay", type=float, default=2)
    args = parser.parse_args()

    if args.delay < 1:
        parser.error("delay phải >= 1.")

    if not crawler.DB_PATH.is_file():
        raise FileNotFoundError(crawler.DB_PATH)

    connection = sqlite3.connect(
        crawler.DB_PATH.resolve().as_uri() + "?mode=rw",
        uri=True,
    )
    original_load_urls = crawler.load_urls

    try:
        rows = connection.execute("""
            SELECT tournament_id, game_slug, source_game_id,
                   source_url, error, audit_json
            FROM results
            WHERE status = 'failed'
            ORDER BY game_slug, tournament_id
        """).fetchall()

        targets = []

        for tournament_id, slug, game_id, url, error, audit_json in rows:
            audit = json.loads(audit_json or "{}")
            is_http500 = (
                str(audit.get("http_status")) == "500"
                or (error or "").startswith("500 Server Error:")
            )

            if is_http500:
                crawler.validate_url(url, tournament_id)
                targets.append({
                    "game_slug": slug,
                    "source_game_id": game_id,
                    "source_tournament_id": tournament_id,
                    "source_url": url,
                })

        print(f"Số giải HTTP 500 cần retry: {len(targets)}")

        for item in targets:
            print(
                item["game_slug"],
                item["source_tournament_id"],
                item["source_url"],
                sep=" | ",
            )

        if not targets:
            print("Không còn lỗi HTTP 500. Không thay đổi dữ liệu.")
            return

        if not args.apply:
            print("\nChỉ xem danh sách. Thêm --apply để retry.")
            return

        slugs = sorted({item["game_slug"] for item in targets})
        games = crawler.load_games(slugs)

        # Kiểm tra ID game trước khi thay đổi dữ liệu.
        for game in games:
            for item in targets:
                if item["game_slug"] == game["game_slug"]:
                    if item["source_game_id"] != game["earnings_game_id"]:
                        raise ValueError("ID game trong SQLite khác cấu hình.")

        # Backup SQLite an toàn, kể cả khi database dùng WAL.
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_dir = crawler.PIPELINE_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"before_http500_retry_{run_id}.sqlite3"

        with sqlite3.connect(backup_path) as backup_connection:
            connection.backup(backup_connection)

        print("\nĐã backup:", backup_path)

        def selected_urls(game):
            return pd.DataFrame([
                item for item in targets
                if item["game_slug"] == game["game_slug"]
            ])

        # Chỉ thay hàm trong tiến trình này; không sửa file crawler.
        crawler.load_urls = selected_urls

        retry_args = SimpleNamespace(
            limit=0,
            delay=args.delay,
            offline=False,
            retry_errors=True,
        )

        # Cache rỗng để thực sự tải lại các URL lỗi HTTP 500.
        cached = {}

        with requests.Session() as session:
            session.headers.update({
                "User-Agent": "Esports-IDV-Student-Research/1.0"
            })

            for index, game in enumerate(games):
                if index:
                    time.sleep(args.delay)

                completed = crawler.crawl_game(
                    connection, session, game, retry_args, cached
                )

                if not completed:
                    print("Dừng toàn lượt retry do HTTP 403/429.")
                    break

        print("\nTRẠNG THÁI SAU RETRY")
        crawler.print_status(connection)

        # Xuất lại CSV từ SQLite sau khi cập nhật.
        crawler.export_csv(connection)

    except KeyboardInterrupt:
        print("\nĐã dừng. Các kết quả đã commit vẫn được giữ.")

    finally:
        crawler.load_urls = original_load_urls
        connection.close()


if __name__ == "__main__":
    main()
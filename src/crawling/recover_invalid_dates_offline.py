import argparse
import json
import sqlite3
from datetime import datetime, timezone
from functools import partial
from types import SimpleNamespace

import pandas as pd
import requests

import crawl_games_sqlite as crawler


DATE_ERROR = "Ngày bắt đầu lớn hơn ngày kết thúc."


def main():
    parser = argparse.ArgumentParser(
        description="Xử lý offline các giải failed do ngày nguồn bị ngược."
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not crawler.DB_PATH.is_file():
        raise FileNotFoundError(crawler.DB_PATH)

    connection = sqlite3.connect(
        crawler.DB_PATH.resolve().as_uri() + "?mode=rw",
        uri=True,
    )

    original_load_urls = crawler.load_urls
    original_parse = crawler.parse_tournament
    original_save = crawler.save_result

    try:
        rows = connection.execute("""
            SELECT tournament_id, game_slug, source_game_id, source_url
            FROM results
            WHERE status = 'failed' AND error = ?
            ORDER BY game_slug, tournament_id
        """, (DATE_ERROR,)).fetchall()

        targets = [
            {
                "source_tournament_id": str(tournament_id),
                "game_slug": slug,
                "source_game_id": str(game_id),
                "source_url": url,
            }
            for tournament_id, slug, game_id, url in rows
        ]

        print(f"Số giải cần xử lý ngày: {len(targets)}")

        if not targets:
            print("Không còn bản ghi failed thuộc nhóm này.")
            return

        cached = crawler.find_cached_html()

        # Kiểm tra toàn bộ cache trước khi cập nhật SQLite.
        for item in targets:
            tournament_id = item["source_tournament_id"]
            crawler.validate_url(item["source_url"], tournament_id)

            path = cached.get(tournament_id)
            if path is None:
                raise FileNotFoundError(
                    f"Thiếu HTML cache của giải {tournament_id}."
                )

            metadata = json.loads(
                path.with_suffix(".json").read_text(encoding="utf-8")
            )
            cache_url = (
                metadata.get("final_url") or metadata.get("source_url")
            )
            if not cache_url or not metadata.get("crawled_at"):
                raise ValueError(
                    f"Metadata cache không đầy đủ: {tournament_id}"
                )
            crawler.validate_url(cache_url, tournament_id)

            print(
                item["game_slug"],
                tournament_id,
                path,
                sep=" | ",
            )

        slugs = sorted({item["game_slug"] for item in targets})
        games = crawler.load_games(slugs)

        for game in games:
            for item in targets:
                if item["game_slug"] == game["game_slug"]:
                    if item["source_game_id"] != game["earnings_game_id"]:
                        raise ValueError("ID game không khớp cấu hình.")

        if not args.apply:
            print("\nChỉ kiểm tra. Thêm --apply để xử lý offline.")
            return

        run_id = datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
        backup_dir = crawler.PIPELINE_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = (
            backup_dir / f"before_invalid_dates_{run_id}.sqlite3"
        )

        with sqlite3.connect(backup_path) as backup_connection:
            connection.backup(backup_connection)

        print("\nĐã backup:", backup_path)

        def selected_urls(game):
            return pd.DataFrame([
                item for item in targets
                if item["game_slug"] == game["game_slug"]
            ])

        def save_with_date_flag(
            conn, game, tournament_id, url, audit,
            tournament=None, placements=None,
        ):
            if tournament is not None:
                date_status = tournament["date_validation_status"]
                audit["date_validation_status"] = date_status
                audit["date_raw"] = tournament["date_raw"]

                if placements is not None:
                    placements = placements.copy()
                    placements["date_validation_status"] = date_status

            original_save(
                conn, game, tournament_id, url, audit,
                tournament, placements,
            )

        # Các thay đổi chỉ có hiệu lực trong tiến trình này.
        crawler.load_urls = selected_urls
        crawler.parse_tournament = partial(
            original_parse,
            allow_invalid_dates=True,
        )
        crawler.save_result = save_with_date_flag

        offline_args = SimpleNamespace(
            limit=0,
            delay=2,
            offline=True,
            retry_errors=True,
        )

        # offline=True: crawler chỉ đọc cache, không gửi request.
        with requests.Session() as session:
            for game in games:
                crawler.crawl_game(
                    connection, session, game, offline_args, cached
                )

        print("\nKẾT QUẢ CÁC GIẢI VỪA XỬ LÝ")

        for item in targets:
            tournament_id = item["source_tournament_id"]
            row = connection.execute("""
                SELECT status, error, tournament_json
                FROM results WHERE tournament_id = ?
            """, (tournament_id,)).fetchone()

            status, error, tournament_json = row
            record = json.loads(tournament_json or "{}")

            print(
                item["game_slug"],
                tournament_id,
                status,
                record.get("date_validation_status"),
                record.get("date_raw"),
                f"start={record.get('start_date')}",
                f"end={record.get('end_date')}",
                error or "",
                sep=" | ",
            )

        crawler.export_csv(connection)

    except KeyboardInterrupt:
        print("\nĐã dừng. Các kết quả đã commit vẫn được giữ.")

    finally:
        crawler.load_urls = original_load_urls
        crawler.parse_tournament = original_parse
        crawler.save_result = original_save
        connection.close()


if __name__ == "__main__":
    main()
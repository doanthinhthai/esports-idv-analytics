from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse
import argparse
import json
import re
import sqlite3
import time

import pandas as pd
import requests

from parse_earnings_sample import parse_tournament
from parse_placements_sample import parse_placements
from prize_validation import validate_prizes


PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw" / "esportsearnings"
CONFIG_PATH = PROJECT_DIR / "data" / "config" / "games_config.csv"

PIPELINE_DIR = RAW_DIR / "sqlite_pipeline"
DB_PATH = PIPELINE_DIR / "crawl.sqlite3"
CACHE_DIR = PIPELINE_DIR / "html"
EXPORT_DIR = PIPELINE_DIR / "exports"

ALLOWED_HOSTS = {
    "www.esportsearnings.com",
    "esportsearnings.com",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def connect_db():
    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS results (
            tournament_id TEXT PRIMARY KEY,
            game_slug TEXT NOT NULL,
            source_game_id TEXT NOT NULL,
            source_url TEXT NOT NULL,
            status TEXT NOT NULL,
            error TEXT,
            html_file TEXT,
            crawled_at TEXT,
            updated_at TEXT NOT NULL,
            tournament_json TEXT,
            placements_json TEXT,
            audit_json TEXT NOT NULL
        )
    """)
    connection.commit()
    return connection


def load_games(game_slugs):
    config = pd.read_csv(CONFIG_PATH, dtype=str).fillna("")

    if not config["game_slug"].is_unique:
        raise ValueError("game_slug bị trùng trong cấu hình.")

    records = []

    for slug in game_slugs:
        if not re.fullmatch(r"[a-z0-9_]+", slug):
            raise ValueError(f"game_slug không hợp lệ: {slug}")

        selected = config.loc[config["game_slug"].eq(slug)]

        if len(selected) != 1:
            raise ValueError(f"Không tìm thấy cấu hình: {slug}")

        game = selected.iloc[0].to_dict()

        if game["enabled"].lower() != "true":
            raise ValueError(f"Game chưa được bật: {slug}")

        if not re.fullmatch(r"\d+", game["earnings_game_id"]):
            raise ValueError(f"Game chưa có ID Earnings hợp lệ: {slug}")

        records.append(game)

    return records


def load_urls(game):
    slug = game["game_slug"]

    if slug == "csgo":
        path = (
            RAW_DIR
            / "245_event_discovery"
            / "245_all_tournament_urls.csv"
        )
    else:
        path = (
            RAW_DIR
            / slug
            / "event_discovery"
            / "all_tournament_urls.csv"
        )

    if not path.exists():
        raise FileNotFoundError(
            f"Chưa có danh sách giải đầy đủ: {path}\n"
            "Hãy chạy discovery cho game này trước."
        )

    frame = pd.read_csv(path, dtype=str).fillna("")

    required = {"source_game_id", "source_tournament_id", "source_url"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Danh sách URL thiếu cột: {path}")

    if not frame["source_game_id"].eq(game["earnings_game_id"]).all():
        raise ValueError(f"Danh sách chứa ID game khác cấu hình: {path}")

    return frame.drop_duplicates("source_tournament_id")


def find_cached_html():
    """Tìm HTML giải trong cache mới và các batch cũ."""
    cached = {}

    # Chỉ tìm trong thư mục crawl, không quét toàn project.
    roots = [RAW_DIR / "batch_runs", CACHE_DIR]

    for root in roots:
        if not root.exists():
            continue

        for path in sorted(root.rglob("*.html")):
            if path.stem.isdigit() and path.with_suffix(".json").exists():
                cached[path.stem] = path

    return cached


def validate_url(url, tournament_id):
    parsed = urlparse(url)

    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or not re.match(
            rf"/tournaments/{re.escape(tournament_id)}(?:-|/|$)",
            parsed.path,
        )
    ):
        raise ValueError(f"URL không khớp ID giải: {url}")


def save_result(connection, game, tournament_id, url, audit,
                tournament=None, placements=None):
    connection.execute("""
        INSERT INTO results (
            tournament_id, game_slug, source_game_id, source_url,
            status, error, html_file, crawled_at, updated_at,
            tournament_json, placements_json, audit_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(tournament_id) DO UPDATE SET
            game_slug=excluded.game_slug,
            source_game_id=excluded.source_game_id,
            source_url=excluded.source_url,
            status=excluded.status,
            error=excluded.error,
            html_file=excluded.html_file,
            crawled_at=excluded.crawled_at,
            updated_at=excluded.updated_at,
            tournament_json=excluded.tournament_json,
            placements_json=excluded.placements_json,
            audit_json=excluded.audit_json
    """, (
        tournament_id,
        game["game_slug"],
        game["earnings_game_id"],
        url,
        audit["status"],
        audit.get("error"),
        audit.get("html_file"),
        audit.get("crawled_at"),
        now(),
        json.dumps(tournament, ensure_ascii=False)
        if tournament is not None else None,
        placements.to_json(orient="records", force_ascii=False)
        if placements is not None else None,
        json.dumps(audit, ensure_ascii=False),
    ))
    connection.commit()


def crawl_game(connection, session, game, args, cached):
    urls = load_urls(game)

    previous = dict(connection.execute(
        "SELECT tournament_id, status FROM results"
    ).fetchall())

    attempted = 0
    last_request_finished = 0.0

    for position, (_, row) in enumerate(urls.iterrows(), start=1):
        tournament_id = row["source_tournament_id"]
        url = row["source_url"]

        if not re.fullmatch(r"\d+", tournament_id):
            raise ValueError(f"ID giải không hợp lệ: {tournament_id}")

        previous_status = previous.get(tournament_id)

        if previous_status is not None:
            retryable = previous_status in {"failed", "tournament_only"}

            if not args.retry_errors or not retryable:
                continue

        if args.limit and attempted >= args.limit:
            break

        path = cached.get(tournament_id)

        # Offline chỉ xử lý những HTML đã có.
        if args.offline and path is None:
            continue

        attempted += 1
        tournament = None
        placements = None
        stop = False

        audit = {
            "source_tournament_id": tournament_id,
            "game_slug": game["game_slug"],
            "requested_url": url,
            "status": "failed",
            "error": None,
            "checked_at": now(),
        }

        print(
            f"[{game['game_slug']} {position}/{len(urls)}] "
            f"{tournament_id}",
            flush=True,
        )

        try:
            validate_url(url, tournament_id)

            if path is not None:
                metadata = json.loads(
                    path.with_suffix(".json").read_text(encoding="utf-8")
                )
                html_bytes = path.read_bytes()

                source_url = metadata.get("final_url") or metadata.get(
                    "source_url"
                )
                crawled_at = metadata.get("crawled_at")

                if not source_url or not crawled_at:
                    raise ValueError("Metadata cache thiếu URL/thời điểm crawl.")

                validate_url(source_url, tournament_id)
                audit["http_status"] = metadata.get("http_status")
                audit["from_cache"] = True

            else:
                elapsed = time.monotonic() - last_request_finished
                time.sleep(max(0.0, args.delay - elapsed))

                response = session.get(
                    url,
                    timeout=30,
                    allow_redirects=False,
                )
                last_request_finished = time.monotonic()

                audit["http_status"] = response.status_code
                audit["retry_after"] = response.headers.get("Retry-After")

                if response.status_code in {403, 429}:
                    stop = True

                response.raise_for_status()

                if response.status_code != 200:
                    raise ValueError("Phản hồi không phải HTTP 200.")

                html_bytes = response.content
                source_url = url
                crawled_at = now()

                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                path = CACHE_DIR / f"{tournament_id}.html"
                path.write_bytes(html_bytes)

                path.with_suffix(".json").write_text(
                    json.dumps({
                        "requested_url": url,
                        "final_url": source_url,
                        "source_tournament_id": tournament_id,
                        "crawled_at": crawled_at,
                        "http_status": response.status_code,
                    }, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                cached[tournament_id] = path
                audit["from_cache"] = False

            html_filename = path.relative_to(RAW_DIR).as_posix()

            audit.update({
                "html_file": html_filename,
                "crawled_at": crawled_at,
                "final_url": source_url,
            })

            tournament = parse_tournament(
                html_bytes,
                source_url=source_url,
                html_filename=html_filename,
            )

            if tournament["source_game_id"] != game["earnings_game_id"]:
                tournament = None
                raise ValueError("Game trên trang không khớp cấu hình.")

            tournament["game_id"] = game["game_id"]
            tournament["game_slug"] = game["game_slug"]
            tournament["crawled_at"] = crawled_at
            tournament["placements_status"] = "tournament_only"
            audit["status"] = "tournament_only"

            placements = parse_placements(
                html_bytes,
                source_url=source_url,
                html_filename=html_filename,
            )

            if placements.duplicated(
                ["source_tournament_id", "team_name_raw"]
            ).any():
                placements = None
                raise ValueError("Đội bị trùng trong cùng giải.")

            total, difference, status = validate_prizes(
                tournament["prize_pool_usd"],
                placements["prize_money_usd"],
            )

            tournament["placements_status"] = status
            placements["game_id"] = game["game_id"]
            placements["game_slug"] = game["game_slug"]
            placements["crawled_at"] = crawled_at
            placements["validation_status"] = status

            audit.update({
                "status": status,
                "participant_count": len(placements),
                "expected_prize_usd": tournament["prize_pool_usd"],
                "extracted_prize_usd": total,
                "difference_usd": difference,
            })

        except (
            requests.RequestException,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
        ) as error:
            placements = None
            audit["error"] = str(error)

        save_result(
            connection, game, tournament_id, url,
            audit, tournament, placements,
        )

        print(
            f"  {audit['status']} | {audit.get('error') or ''}",
            flush=True,
        )

        if stop:
            print(
                "Dừng do HTTP 403/429. Retry-After:",
                audit.get("retry_after"),
            )
            return False

    print(f"{game['game_slug']}: đã xử lý thêm {attempted} URL.")
    return True


def print_status(connection):
    rows = connection.execute("""
        SELECT game_slug, status, COUNT(*)
        FROM results
        GROUP BY game_slug, status
        ORDER BY game_slug, status
    """).fetchall()

    for slug, status, count in rows:
        print(f"{slug:16} {status:22} {count}")

    if not rows:
        print("SQLite chưa có kết quả.")


def export_csv(connection):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    slugs = [
        row[0] for row in connection.execute(
            "SELECT DISTINCT game_slug FROM results ORDER BY game_slug"
        )
    ]

    for slug in slugs:
        output = EXPORT_DIR / slug
        output.mkdir(parents=True, exist_ok=True)

        tournaments = []
        placements = []
        audits = []

        rows = connection.execute("""
            SELECT tournament_json, placements_json, audit_json
            FROM results WHERE game_slug = ?
            ORDER BY tournament_id
        """, (slug,))

        for tournament_json, placements_json, audit_json in rows:
            if tournament_json:
                tournaments.append(json.loads(tournament_json))
            if placements_json:
                placements.extend(json.loads(placements_json))
            audits.append(json.loads(audit_json))

        pd.DataFrame(tournaments).to_csv(
            output / "tournaments.csv",
            index=False,
            encoding="utf-8-sig",
        )
        pd.DataFrame(placements).to_csv(
            output / "placements.csv",
            index=False,
            encoding="utf-8-sig",
        )
        pd.DataFrame(audits).to_csv(
            output / "crawl_audit.csv",
            index=False,
            encoding="utf-8-sig",
        )

        print(
            f"Xuất {slug}: {len(tournaments)} giải, "
            f"{len(placements)} placements → {output}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", nargs="+")
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Số URL mới xử lý mỗi game; 0: tất cả",
    )
    parser.add_argument("--delay", type=float, default=2)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()

    if args.limit < 0 or args.delay < 1:
        parser.error("limit phải >= 0; delay phải >= 1.")

    if not args.games and not args.status and not args.export:
        parser.error("Cần --games, --status hoặc --export.")

    connection = connect_db()

    try:
        if args.games:
            games = load_games(args.games)
            cached = find_cached_html()

            with requests.Session() as session:
                session.headers.update({
                    "User-Agent": "Esports-IDV-Student-Research/1.0"
                })

                for game in games:
                    if not crawl_game(
                        connection, session, game, args, cached
                    ):
                        break

        if args.status:
            print_status(connection)

        if args.export:
            export_csv(connection)

    except KeyboardInterrupt:
        print(
            "\nĐã dừng. Kết quả đã commit được giữ trong SQLite; "
            "HTML của URL đang xử lý có thể được dùng lại."
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
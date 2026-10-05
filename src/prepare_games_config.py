from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import shutil


PROJECT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_DIR / "data" / "config" / "games_config.csv"

# Chỉ chứa những ID/URL đã được xác minh.
TARGETS = {
    "csgo": {
        "game_id": "G001",
        "game_name": "Counter-Strike: Global Offensive",
        "game_family": "Counter-Strike",
        "genre": "Tactical FPS",
        "platform": "PC",
        "earnings_game_id": "245",
        "earnings_events_url": (
            "https://www.esportsearnings.com/games/"
            "245-counter-strike-global-offensive/events"
        ),
        "escharts_game_url": "https://escharts.com/tournaments/csgo",
        "note": (
            "Analyze with CS2 under Counter-Strike; preserve version; "
            "Charts listing is shared with CS2"
        ),
    },
    "cs2": {
        "game_id": "G002",
        "game_name": "Counter-Strike 2",
        "game_family": "Counter-Strike",
        "genre": "Tactical FPS",
        "platform": "PC",
        "earnings_game_id": "839",
        "earnings_events_url": (
            "https://www.esportsearnings.com/games/"
            "839-counter-strike-2/events"
        ),
        "escharts_game_url": "https://escharts.com/tournaments/cs2",
        "note": (
            "Analyze with CSGO under Counter-Strike; preserve version; "
            "Charts listing is shared with CSGO"
        ),
    },
    "dota2": {
        "game_id": "G003",
        "game_name": "Dota 2",
        "game_family": "Dota 2",
        "genre": "MOBA",
        "platform": "PC",
        "earnings_game_id": "231",
        "earnings_events_url": (
            "https://www.esportsearnings.com/games/231-dota-2/events"
        ),
        "escharts_game_url": "https://escharts.com/tournaments/dota2",
        "note": "Project scope: 2012-2025; use actual source coverage",
    },
    "lol": {
        "game_id": "G004",
        "game_name": "League of Legends",
        "game_family": "League of Legends",
        "genre": "MOBA",
        "platform": "PC",
        "earnings_game_id": "164",
        "earnings_events_url": (
            "https://www.esportsearnings.com/games/"
            "164-league-of-legends/events"
        ),
        "escharts_game_url": "https://escharts.com/tournaments/lol",
        "note": "Project scope: 2012-2025; use actual source coverage",
    },
    "valorant": {
        "game_id": "G005",
        "game_name": "VALORANT",
        "game_family": "Valorant",
        "genre": "Tactical FPS",
        "platform": "PC",
        "earnings_game_id": "646",
        "earnings_events_url": (
            "https://www.esportsearnings.com/games/646-valorant/events"
        ),
        "escharts_game_url": "https://escharts.com/tournaments/valorant",
        "note": "Use actual history; pre-existence years are not missing data",
    },
}


def main():
    parser = argparse.ArgumentParser(
        description="Xem trước hoặc cập nhật cấu hình 4 nhóm game."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Sao lưu và ghi cấu hình; mặc định chỉ xem trước.",
    )
    args = parser.parse_args()

    with CONFIG_PATH.open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        rows = list(reader)

    if not columns:
        raise ValueError("File cấu hình không có header.")

    required = {
        "game_id", "game_slug", "game_name", "game_family",
        "genre", "platform", "enabled", "priority",
        "earnings_game_id", "earnings_events_url", "earnings_status",
        "escharts_game_id", "escharts_game_url", "escharts_status",
        "notes",
    }

    missing = required - set(columns)
    if missing:
        raise ValueError(f"Thiếu cột: {sorted(missing)}")

    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError("Có dòng CSV thừa hoặc thiếu ô. Kiểm tra dấu phẩy.")

    slugs = [row["game_slug"] for row in rows]
    ids = [row["game_id"] for row in rows]

    if len(slugs) != len(set(slugs)) or len(ids) != len(set(ids)):
        raise ValueError("game_slug hoặc game_id bị trùng.")

    missing_games = set(TARGETS) - set(slugs)
    if missing_games:
        raise ValueError(f"Thiếu dòng game: {sorted(missing_games)}")

    for row in rows:
        slug = row["game_slug"]
        row["enabled"] = "true" if slug in TARGETS else "false"

        if slug not in TARGETS:
            continue

        target = TARGETS[slug]

        # Không đổi ID nội bộ đã dùng trong dữ liệu.
        if row["game_id"] != target["game_id"]:
            raise ValueError(
                f"ID nội bộ {slug} khác dự kiến: {row['game_id']}. "
                "Kiểm tra trước khi tiếp tục."
            )

        old_earnings_id = row["earnings_game_id"]

        for key, value in target.items():
            if key != "note":
                row[key] = value

        row["priority"] = "1"

        # Giữ trạng thái tiến độ hiện có nếu ID nguồn không đổi.
        # ready chỉ có nghĩa cấu hình nguồn đã sẵn sàng.
        if (
            old_earnings_id != target["earnings_game_id"]
            or row["earnings_status"] in {"", "not_verified"}
        ):
            row["earnings_status"] = "ready"

        # URL danh sách đã xác minh; chưa test crawler Charts.
        row["escharts_game_id"] = ""
        row["escharts_status"] = "url_verified"

        old_note = row["notes"].strip()
        if target["note"] not in old_note:
            row["notes"] = " | ".join(
                value for value in [old_note, target["note"]] if value
            )

    selected = [row for row in rows if row["enabled"] == "true"]

    if len(selected) != 5:
        raise ValueError("Phải có đúng 5 phiên bản được bật.")

    if len({row["game_family"] for row in selected}) != 4:
        raise ValueError("Phải có đúng 4 nhóm phân tích.")

    print("\nCẤU HÌNH DỰ KIẾN")
    for row in selected:
        print(
            f"{row['game_id']:5} "
            f"{row['game_slug']:10} "
            f"{row['game_family']:20} "
            f"Earnings={row['earnings_game_id']:4} "
            f"status={row['earnings_status']}"
        )

    print(f"\nTổng dòng giữ lại: {len(rows)}")
    print("Bật: 5 phiên bản, 4 nhóm phân tích")
    print(f"Tắt: {len(rows) - len(selected)} game ngoài phạm vi")

    if not args.apply:
        print("\nCHỈ XEM TRƯỚC — chưa thay đổi file.")
        print("Nếu đúng, chạy lại với --apply.")
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = CONFIG_PATH.with_name(
        f"games_config.backup_{timestamp}.csv"
    )
    temporary = CONFIG_PATH.with_name(
        f"games_config.pending_{timestamp}.csv"
    )

    shutil.copy2(CONFIG_PATH, backup)

    with temporary.open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    temporary.replace(CONFIG_PATH)

    print(f"\nĐã lưu: {CONFIG_PATH}")
    print(f"Bản sao lưu: {backup}")


if __name__ == "__main__":
    main()
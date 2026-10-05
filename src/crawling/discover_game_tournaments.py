"""Discover tournament URLs per configured game, reusing saved event HTML."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import json
import re
import time

import pandas as pd
import requests

import collect_event_batch_urls as extractor

PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw" / "esportsearnings"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True)
    parser.add_argument("--limit", type=int, default=20, help="0: tất cả sự kiện")
    parser.add_argument("--delay", type=float, default=3)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if args.limit < 0 or args.delay < 1:
        parser.error("limit >= 0; delay >= 1")
    if not re.fullmatch(r"[a-z0-9_]+", args.game):
        parser.error("game slug không hợp lệ")
    config = pd.read_csv(PROJECT_DIR / "data/config/games_config.csv", dtype=str).fillna("")
    selected = config[config.game_slug.eq(args.game)]
    if len(selected) != 1:
        parser.error("Không tìm được cấu hình game duy nhất")
    game = selected.iloc[0]
    if game.enabled.lower() != "true" or not re.fullmatch(r"\d+", game.earnings_game_id):
        parser.error("Game chưa bật hoặc thiếu ID nguồn")
    extractor.GAME_ID = game.earnings_game_id
    base = RAW_DIR / args.game
    output = base / "event_discovery"
    html_dir = output / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    events = pd.read_csv(base / "event_urls.csv", dtype=str).drop_duplicates("source_event_id")
    if args.limit:
        events = events.head(args.limit)
    frames = [pd.read_csv(base / "direct_tournament_urls.csv", dtype=str)]
    frames.extend(pd.read_csv(p, dtype=str) for p in sorted(output.glob("*_tournament_urls.csv")))
    combined = pd.concat(frames, ignore_index=True).drop_duplicates(["source_game_id", "source_tournament_id"])
    audit_path = output / "discovery_audit.csv"
    audit = pd.read_csv(audit_path, dtype=str).fillna("").to_dict("records") if audit_path.exists() else []
    completed = {r["source_event_id"] for r in audit if r["status"] == "extracted"}
    merged_path = output / "all_tournament_urls.csv"
    combined.to_csv(merged_path, index=False, encoding="utf-8-sig")
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Esports-IDV-Student-Research/1.0"})
        for position, (_, event) in enumerate(events.iterrows(), 1):
            event_id, url = event.source_event_id, event.source_url
            if event_id in completed:
                continue
            record = {"source_event_id": event_id, "source_url": url,
                      "checked_at": datetime.now(timezone.utc).isoformat(),
                      "status": "failed", "tournament_count": 0, "error": ""}
            stop = False
            print(f"[{position}/{len(events)}] {url}")
            try:
                parsed = urlparse(url)
                if (not re.fullmatch(r"\d+", event_id) or parsed.scheme != "https"
                    or parsed.hostname != "www.esportsearnings.com"
                    or not re.match(rf"/events/{event_id}(?:-|/|$)", parsed.path)):
                    raise ValueError("ID hoặc URL sự kiện không hợp lệ")
                path = html_dir / f"{event_id}.html"
                if path.exists():
                    content = path.read_bytes()
                elif args.offline:
                    print("Chưa có HTML, bỏ qua offline.")
                    continue
                else:
                    time.sleep(args.delay)
                    response = session.get(url, timeout=30, allow_redirects=False)
                    record["http_status"] = response.status_code
                    stop = response.status_code in {403, 429}
                    response.raise_for_status()
                    if response.status_code != 200:
                        raise ValueError("Phản hồi không phải 200")
                    content = response.content
                    if extractor.BeautifulSoup(content, "html.parser").select_one("main h1") is None:
                        raise ValueError("HTML không có cấu trúc dự kiến")
                    path.write_bytes(content)
                    path.with_suffix(".json").write_text(json.dumps({
                        "source_url": url, "source_event_id": event_id,
                        "source_game_id": game.earnings_game_id,
                        "crawled_at": datetime.now(timezone.utc).isoformat(),
                        "http_status": response.status_code,
                    }, ensure_ascii=False, indent=2), encoding="utf-8")
                found = extractor.extract_tournaments(content, url, path.relative_to(RAW_DIR).as_posix())
                found.to_csv(output / f"{event_id}_tournament_urls.csv", index=False, encoding="utf-8-sig")
                combined = pd.concat([combined, found], ignore_index=True).drop_duplicates(["source_game_id", "source_tournament_id"])
                record.update(status="extracted" if len(found) else "needs_review", tournament_count=len(found))
            except (requests.RequestException, ValueError, OSError) as exc:
                record["error"] = str(exc)
            audit = [r for r in audit if r["source_event_id"] != event_id] + [record]
            pd.DataFrame(audit).to_csv(audit_path, index=False, encoding="utf-8-sig")
            combined.to_csv(merged_path, index=False, encoding="utf-8-sig")
            print(f"{record['status']} | Tổng URL duy nhất: {len(combined)} | {record['error']}")
            if stop:
                print("Dừng do HTTP 403/429.")
                break
    print("Danh sách giải:", merged_path)


if __name__ == "__main__":
    main()

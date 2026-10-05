from pathlib import Path
import json
import re

import pandas as pd

from parse_earnings_sample import parse_tournament
from parse_placements_sample import parse_placements
from prize_validation import validate_prizes


PROJECT_DIR = Path(__file__).resolve().parents[2]

RUN_DIR = (
    PROJECT_DIR
    / "data"
    / "raw"
    / "esportsearnings"
    / "batch_runs"
    / "20261005T043255771750Z"
)

HTML_DIR = RUN_DIR / "html"
OUTPUT_DIR = RUN_DIR / "reparsed"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tournament_records = []
    placement_frames = []
    audit_records = []

    for html_path in sorted(HTML_DIR.glob("*.html")):
        audit = {
            "html_file": html_path.name,
            "status": "failed",
            "error": None,
        }

        try:
            metadata_path = html_path.with_suffix(".json")
            metadata = json.loads(
                metadata_path.read_text(encoding="utf-8")
            )

            source_url = metadata["final_url"]
            crawled_at = metadata["crawled_at"]

            id_match = re.search(r"/tournaments/(\d+)", source_url)
            if id_match is None:
                raise ValueError("Không đọc được ID từ URL nguồn.")

            expected_id = id_match.group(1)

            if html_path.stem != expected_id:
                raise ValueError("ID tên file và URL nguồn không khớp.")

            html_bytes = html_path.read_bytes()

            tournament = parse_tournament(
                html_bytes,
                source_url=source_url,
                html_filename=html_path.name,
            )

            if str(tournament["source_tournament_id"]) != expected_id:
                raise ValueError("Parser thông tin trả về ID sai.")

            tournament["crawled_at"] = crawled_at
            tournament["placements_status"] = "failed"
            tournament_records.append(tournament)

            audit.update({
                "source_url": source_url,
                "source_tournament_id": expected_id,
                "tournament_name": tournament["tournament_name_raw"],
                "status": "tournament_only",
            })

            placements = parse_placements(
                html_bytes,
                source_url=source_url,
                html_filename=html_path.name,
            )

            if not placements["source_tournament_id"].astype(str).eq(
                expected_id
            ).all():
                raise ValueError("Parser placements trả về ID sai.")

            if placements.duplicated(
                subset=["source_tournament_id", "team_name_raw"]
            ).any():
                raise ValueError("Có đội bị lặp trong cùng giải.")

            expected_prize = float(tournament["prize_pool_usd"])
            extracted_prize, difference, status = validate_prizes(
                expected_prize, placements["prize_money_usd"]
            )

            tournament["placements_status"] = status
            placements["validation_status"] = status
            placements["crawled_at"] = crawled_at
            placement_frames.append(placements)

            audit.update({
                "team_count": len(placements),
                "expected_prize_usd": expected_prize,
                "extracted_prize_usd": extracted_prize,
                "difference_usd": difference,
                "status": status,
            })

            print(
                f"{expected_id} | "
                f"{tournament['tournament_name_raw']} | "
                f"{len(placements)} đội | "
                f"chênh lệch ${difference:,.2f} | {status}"
            )

        except (OSError, ValueError, KeyError, TypeError) as error:
            audit["error"] = str(error)
            print(f"LỖI {html_path.name}: {error}")

        audit_records.append(audit)

    if not audit_records:
        raise ValueError("Không tìm thấy HTML để phân tích.")

    pd.DataFrame(audit_records).to_csv(
        OUTPUT_DIR / "parse_audit.csv",
        index=False,
        encoding="utf-8-sig",
    )

    if tournament_records:
        pd.DataFrame(tournament_records).to_csv(
            OUTPUT_DIR / "tournaments.csv",
            index=False,
            encoding="utf-8-sig",
        )

    if placement_frames:
        pd.concat(placement_frames, ignore_index=True).to_csv(
            OUTPUT_DIR / "placements.csv",
            index=False,
            encoding="utf-8-sig",
        )

    total_placements = sum(len(df) for df in placement_frames)

    print(f"\nSố giải đã lấy thông tin: {len(tournament_records)}")
    print(f"Số kết quả đội: {total_placements}")
    print(f"Kết quả mới: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

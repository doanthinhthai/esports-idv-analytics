from pathlib import Path

import pandas as pd

from parse_earnings_sample import parse_tournament
from parse_placements_sample import parse_placements


PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw" / "esportsearnings"

# Xuất riêng để giữ các file mẫu trước đó.
OUTPUT_DIR = RAW_DIR / "batch_sample"

SAMPLES = [
    {
        "html_filename": "sample_tournament.html",
        "source_url": (
            "https://www.esportsearnings.com/tournaments/"
            "49819-pgl-major-stockholm-2021"
        ),
        "expected_name": "PGL Major Stockholm 2021",
    },
    {
        "html_filename": "52807_pgl_antwerp_2022.html",
        "source_url": (
            "https://www.esportsearnings.com/tournaments/"
            "52807-pgl-major-antwerp-2022"
        ),
        "expected_name": "PGL Major Antwerp 2022",
    },
    {
        "html_filename": "61482_blast_paris_2023.html",
        "source_url": (
            "https://www.esportsearnings.com/tournaments/"
            "61482-blast-tv-paris-major-2023"
        ),
        "expected_name": "BLAST.tv Paris Major 2023",
    },
]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tournaments = []
    placements = []
    audit_records = []

    for sample in SAMPLES:
        filename = sample["html_filename"]
        url = sample["source_url"]

        try:
            html_bytes = (RAW_DIR / filename).read_bytes()

            tournament = parse_tournament(
                html_bytes,
                source_url=url,
                html_filename=filename,
            )

            # Phát hiện trường hợp tên file/URL đúng nhưng HTML sai giải.
            actual_name = tournament["tournament_name_raw"]

            if actual_name != sample["expected_name"]:
                raise ValueError(
                    f"Sai giải trong HTML: {actual_name}"
                )

            team_results = parse_placements(
                html_bytes,
                source_url=url,
                html_filename=filename,
            )

            if team_results.duplicated(
                subset=["source_tournament_id", "team_name_raw"]
            ).any():
                raise ValueError("Có đội trùng trong cùng giải.")

            expected_prize = tournament["prize_pool_usd"]
            extracted_prize = team_results["prize_money_usd"].sum()
            difference = extracted_prize - expected_prize

            matched = abs(difference) <= 0.01
            status = "matched" if matched else "needs_review"

            # Giữ dữ liệu đã trích xuất và ghi trạng thái kiểm tra.
            tournament["validation_status"] = status
            team_results["validation_status"] = status

            tournaments.append(tournament)
            placements.append(team_results)

            audit_records.append({
                "source_url": url,
                "html_filename": filename,
                "tournament_name": actual_name,
                "team_count": len(team_results),
                "expected_prize_usd": expected_prize,
                "extracted_prize_usd": extracted_prize,
                "difference_usd": difference,
                "status": status,
                "error": None,
            })

            print(
                f"{actual_name}: {len(team_results)} đội | "
                f"chênh lệch ${difference:,.2f} | {status}"
            )

        except (OSError, ValueError, KeyError, TypeError) as error:
            audit_records.append({
                "source_url": url,
                "html_filename": filename,
                "status": "failed",
                "error": str(error),
            })
            print(f"LỖI {filename}: {error}")

    pd.DataFrame(audit_records).to_csv(
        OUTPUT_DIR / "parse_audit.csv",
        index=False,
        encoding="utf-8-sig",
    )

    if not tournaments:
        raise ValueError(
            "Không phân tích được giải nào. Xem parse_audit.csv."
        )

    tournament_df = pd.DataFrame(tournaments)

    placement_df = pd.concat(
        placements,
        ignore_index=True,
    )

    tournament_df.to_csv(
        OUTPUT_DIR / "tournaments.csv",
        index=False,
        encoding="utf-8-sig",
    )

    placement_df.to_csv(
        OUTPUT_DIR / "placements.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(f"\nTổng số giải đã đọc: {len(tournament_df)}")
    print(f"Tổng số kết quả đội: {len(placement_df)}")
    print(f"Thư mục kết quả: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
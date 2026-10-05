from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
GAME_INPUT = Path(r"C:\Users\dthin\Downloads\Twitch_game_data.csv")
GLOBAL_INPUT = Path(r"C:\Users\dthin\Downloads\Twitch_global_data.csv")

# Giữ nguyên category nguồn, không suy diễn phiên bản từ tên chung.
CATEGORY_MAP = {
    "League of Legends": ("League of Legends", "main"),
    "Dota 2": ("Dota 2", "main"),
    "VALORANT": ("Valorant", "main"),
    "Counter-Strike: Global Offensive": ("Counter-Strike", "main"),
    "Counter-Strike": ("Counter-Strike", "main"),
    "Counter-Strike 2": ("Counter-Strike", "supplementary"),
    "Counter-Strike 2 Limited Test": ("Counter-Strike", "supplementary"),
}


def read_csv(path):
    try:
        return pd.read_csv(path, encoding="utf-8-sig"), "utf-8-sig"
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="cp1252"), "cp1252"


def normalize(frame):
    result = frame.copy()
    result.columns = [column.lower() for column in result.columns]
    result["source_row_number"] = range(2, len(result) + 2)

    # Kiểm tra số liệu, không tự điền missing bằng 0.
    numeric_columns = [
        column for column in result.columns
        if column not in {"game", "source_row_number"}
    ]
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="raise")

    if result[numeric_columns].isna().any().any():
        raise ValueError("Có số liệu thiếu; cần kiểm tra trước khi xử lý.")

    if (result[numeric_columns] < 0).any().any():
        raise ValueError("Có số liệu âm; cần kiểm tra.")

    for column in ["year", "month"]:
        if (result[column] % 1 != 0).any():
            raise ValueError(f"{column} chứa giá trị không nguyên.")

    result["month_start"] = pd.to_datetime(
        {
            "year": result["year"],
            "month": result["month"],
            "day": 1,
        },
        errors="raise",
    )
    result["platform"] = "Twitch"
    result["measurement_level"] = "game_month" if "game" in result else "platform_month"

    if (result["peak_viewers"] < result["avg_viewers"]).any():
        raise ValueError("Peak viewers nhỏ hơn average viewers.")

    return result


def main():
    games_raw, games_encoding = read_csv(GAME_INPUT)
    global_raw, global_encoding = read_csv(GLOBAL_INPUT)

    games = normalize(games_raw)
    global_data = normalize(global_raw)

    games["source_category_raw"] = games["game"]
    games["source_category"] = games["game"].astype("string").str.strip()
    games["source_file"] = str(GAME_INPUT)
    global_data["source_file"] = str(GLOBAL_INPUT)

    missing_name = (
        games["source_category"].isna()
        | games["source_category"].eq("").fillna(False)
    )
    ambiguous_key = games.duplicated(
        ["source_category", "month_start"], keep=False
    )

    games["quality_status"] = "usable"
    games.loc[ambiguous_key, "quality_status"] = "ambiguous_category_month"
    games.loc[missing_name, "quality_status"] = "missing_category"

    # Giữ đầy đủ các dòng đáng ngờ để kiểm tra; không tự cộng hay xóa.
    quarantine = games[games["quality_status"] != "usable"].copy()

    selected = games[
        games["source_category"].isin(CATEGORY_MAP)
    ].copy()

    if (selected["quality_status"] != "usable").any():
        raise ValueError("Category mục tiêu có lỗi; dừng để kiểm tra.")

    selected["game_family"] = selected["source_category"].map(
        lambda name: CATEGORY_MAP[name][0]
    )
    selected["analysis_role"] = selected["source_category"].map(
        lambda name: CATEGORY_MAP[name][1]
    )

    primary = selected[selected["analysis_role"] == "main"].copy()
    supplementary = selected[
        selected["analysis_role"] == "supplementary"
    ].copy()

    if primary.duplicated(["game_family", "month_start"]).any():
        raise ValueError("Chuỗi chính trùng game–tháng; không tự gộp.")

    if global_data.duplicated(["month_start"]).any():
        raise ValueError("Bảng tổng Twitch trùng tháng.")

    if not primary["month_start"].isin(global_data["month_start"]).all():
        raise ValueError("Có tháng mục tiêu không có trong bảng tổng Twitch.")

    # IQR chỉ gắn cờ, không xóa tháng có tăng trưởng thật.
    for metric in ["hours_watched", "avg_viewers", "peak_viewers"]:
        flag = f"{metric}_iqr_flag"
        primary[flag] = False
        for family, group in primary.groupby("game_family"):
            q1 = group[metric].quantile(0.25)
            q3 = group[metric].quantile(0.75)
            spread = q3 - q1
            primary.loc[group.index, flag] = (
                (group[metric] < q1 - 1.5 * spread)
                | (group[metric] > q3 + 1.5 * spread)
            )

    coverage = []
    for family, group in primary.groupby("game_family"):
        available = pd.DatetimeIndex(group["month_start"])
        expected = pd.date_range(
            available.min(), available.max(), freq="MS"
        )
        coverage.append({
            "game_family": family,
            "row_count": len(group),
            "first_month": available.min().strftime("%Y-%m"),
            "last_month": available.max().strftime("%Y-%m"),
            "missing_months": [
                value.strftime("%Y-%m")
                for value in expected.difference(available)
            ],
        })

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = ROOT / "data/processed" / f"twitch_monthly_v1_{run_id}"
    output.mkdir(parents=True, exist_ok=False)

    tables = {
        "all_categories_normalized.csv": games,
        "target_categories.csv": selected,
        "game_monthly_primary.csv": primary,
        "counter_strike_supplementary.csv": supplementary,
        "platform_monthly.csv": global_data,
        "quarantine.csv": quarantine,
    }

    for filename, frame in tables.items():
        frame.sort_values("month_start").to_csv(
            output / filename,
            index=False,
            encoding="utf-8-sig",
            date_format="%Y-%m-%d",
        )

    summary = {
        "dataset_stage": "twitch_monthly_clean_v1_not_tournament_viewership",
        "raw_game_rows": len(games),
        "global_rows": len(global_data),
        "target_category_rows": len(selected),
        "primary_rows": len(primary),
        "supplementary_rows": len(supplementary),
        "quarantine_rows": len(quarantine),
        "missing_category_rows": int(missing_name.sum()),
        "ambiguous_category_month_rows": int(ambiguous_key.sum()),
        "encoding": {
            "games": games_encoding,
            "global": global_encoding,
        },
        "input_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [GAME_INPUT, GLOBAL_INPUT]
        },
        "coverage": coverage,
        "iqr_flag_counts": {
            column: int(primary[column].sum())
            for column in primary.columns
            if column.endswith("_iqr_flag")
        },
        "notes": [
            "Không sửa file gốc hoặc Earnings.",
            "Người xem game trên Twitch, không phải từng giải.",
            "Chuỗi chính Counter-Strike giữ category nguồn.",
            "Không mặc định category Counter-Strike là riêng CS2.",
            "Các category CS2/Limited Test giữ riêng, chưa cộng vào chuỗi chính.",
            "IQR chỉ gắn cờ, không loại bỏ dữ liệu.",
            "Top 200 category mỗi tháng, không phải toàn bộ Twitch.",
            "Không có dữ liệu quốc gia khán giả.",
        ],
    }

    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("KẾT QUẢ CLEAN TWITCH")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nThư mục xuất:", output)


if __name__ == "__main__":
    main()
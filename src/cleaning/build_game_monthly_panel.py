"""Build a descriptive game-month panel; never infer tournament viewers."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--earnings", type=Path, required=True)
    parser.add_argument("--twitch", type=Path, required=True)
    args = parser.parse_args()
    earnings_path = args.earnings.resolve() / "tournaments_clean.csv"
    twitch_path = args.twitch.resolve() / "game_monthly_primary.csv"
    global_path = args.twitch.resolve() / "platform_monthly.csv"
    earnings = pd.read_csv(earnings_path, encoding="utf-8-sig", dtype={"prize_pool_usd": "string"})
    twitch = pd.read_csv(twitch_path, encoding="utf-8-sig")
    global_data = pd.read_csv(global_path, encoding="utf-8-sig")
    keys = ["game_family", "month_start"]
    assert earnings.tournament_id.notna().all() and earnings.tournament_id.is_unique
    assert not twitch.duplicated(keys).any()
    assert global_data.month_start.is_unique
    assert twitch.analysis_role.eq("main").all()
    assert twitch.quality_status.eq("usable").all()
    earnings["start_date"] = pd.to_datetime(earnings.start_date, errors="coerce")
    earnings["month_start"] = earnings.start_date.dt.strftime("%Y-%m-01")
    available_keys = pd.MultiIndex.from_frame(twitch[keys])
    supported = pd.MultiIndex.from_frame(earnings[keys]).isin(available_keys)
    selected = earnings[supported & earnings.date_validation_status.eq("valid")].copy()
    excluded = earnings[~(supported & earnings.date_validation_status.eq("valid"))].copy()

    def cents(value):
        if pd.isna(value):
            return None
        number = Decimal(str(value)) * 100
        assert number.is_finite() and number >= 0 and number == number.to_integral_value()
        return int(number)

    selected["pool_cents"] = pd.array(selected.prize_pool_usd.map(cents), dtype="Int64")
    eligible = selected.eligible_for_placement_prize_analysis
    assert eligible.isin([True, False]).all()
    selected["reconciled_pool_cents"] = selected.pool_cents.where(eligible)
    selected["quality_flag"] = selected.quality_note.fillna("").ne("")
    selected["placement_reconciled"] = eligible.astype(int)
    rows = []
    for (family, month), group in selected.groupby(keys, sort=True):
        pool = group.pool_cents.sum(min_count=1)
        reconciled_pool = group.reconciled_pool_cents.sum(min_count=1)
        rows.append({"game_family": family, "month_start": month,
                     "observed_tournament_count": len(group),
                     "known_pool_count": int(group.pool_cents.notna().sum()),
                     "source_prize_pool_cents": None if pd.isna(pool) else int(pool),
                     "placement_reconciled_tournament_count": int(group.placement_reconciled.sum()),
                     "placement_reconciled_pool_cents": None if pd.isna(reconciled_pool) else int(reconciled_pool),
                     "quality_flagged_tournament_count": int(group.quality_flag.sum()),
                     "game_versions_present": " | ".join(sorted(group.game_version.dropna().unique()))})
    monthly = pd.DataFrame(rows)
    assert len(monthly), "Không có tháng giao nhau giữa hai nguồn."
    assert int(monthly.observed_tournament_count.sum()) == len(selected)
    assert int(monthly.source_prize_pool_cents.sum()) == int(selected.pool_cents.sum())
    panel = twitch.merge(monthly, on=keys, how="left", validate="one_to_one", indicator="earnings_join")
    panel["earnings_month_observed"] = panel.earnings_join.eq("both")
    panel = panel.drop(columns="earnings_join")
    # No observed tournament is not evidence that the source has complete coverage.
    for col in ["observed_tournament_count", "known_pool_count", "placement_reconciled_tournament_count", "quality_flagged_tournament_count"]:
        panel[col] = panel[col].fillna(0).astype(int)
    for col in ["source_prize_pool_cents", "placement_reconciled_pool_cents"]:
        panel[col] = panel[col].astype("Int64")
        panel[col.replace("_cents", "_usd")] = panel[col].astype("Float64") / 100
    platform = global_data[["month_start", "hours_watched"]].rename(columns={"hours_watched": "twitch_platform_hours_watched"})
    panel = panel.merge(platform, on="month_start", how="left", validate="many_to_one")
    assert panel.twitch_platform_hours_watched.notna().all()
    assert (panel.twitch_platform_hours_watched > 0).all()
    panel["game_hours_share_of_twitch_pct"] = panel.hours_watched / panel.twitch_platform_hours_watched * 100
    assert panel.game_hours_share_of_twitch_pct.between(0, 100).all()
    assert len(panel) == len(twitch) and not panel.duplicated(keys).any()
    assert int(panel.source_prize_pool_cents.sum()) == int(selected.pool_cents.sum())
    output = ROOT / "data/processed" / ("game_monthly_panel_v1_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    output.mkdir(parents=True, exist_ok=False)
    for name, frame in [("game_monthly_panel.csv", panel), ("earnings_monthly.csv", monthly),
                        ("earnings_tournament_membership.csv", selected), ("earnings_excluded_from_panel.csv", excluded)]:
        frame.to_csv(output / name, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    summary = {"dataset_stage": "game_monthly_panel_v1_descriptive_not_tournament_viewership",
               "panel_row_count": len(panel), "rows_by_family": panel.groupby("game_family").size().to_dict(),
               "first_month": panel.month_start.min(), "last_month": panel.month_start.max(),
               "included_earnings_tournaments": len(selected), "excluded_earnings_tournaments": len(excluded),
               "months_without_observed_earnings": int((~panel.earnings_month_observed).sum()),
               "source_prize_pool_cents": int(selected.pool_cents.sum()),
               "checks_passed": True,
               "input_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [earnings_path, twitch_path, global_path]},
               "notes": ["Tiền thưởng phân vào tháng bắt đầu giải; không chia đều theo thời lượng.",
                         "Counter-Strike gộp CS:GO và CS2 ở mức family; vẫn giữ phiên bản trong bảng thành viên.",
                         "Twitch chỉ gồm category chính; CS2/Limited Test bổ sung không được cộng vào.",
                         "Cột source_prize_pool là tổng quỹ thưởng nguồn, không phải tổng tiền placements.",
                         "Placement reconciled chỉ đối chiếu tổng tiền, không xác minh tiền từng đội.",
                         "Các tháng không có giải quan sát giữ tiền thưởng thiếu, không suy diễn bằng 0.",
                         "Tỷ trọng giờ xem dùng toàn Twitch làm mẫu số, không phải chỉ bốn game.",
                         "Không cộng mẫu số toàn Twitch lặp lại giữa các game.",
                         "Chưa chứng minh đủ nguồn. Không dùng bảng này để tính ROI hoặc prize_per_viewer từng giải."]}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "input_sha256"}, ensure_ascii=False, indent=2))
    print("Thư mục xuất:", output)


if __name__ == "__main__":
    main()

"""Additional train-only diagnostics, release audit, and handoff documentation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    folder = args.input.resolve()
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = []
    def check(name, condition):
        checks.append({"check": name, "passed": bool(condition)})
        if not condition:
            raise ValueError(name)
    def save(name, frame):
        frame.to_csv(folder / name, index=False, encoding="utf-8-sig")
    for name, digest in manifest["outputs_sha256"].items():
        check("hash:" + name, hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest)
    for name, digest in manifest["inputs"].items():
        check("input_unchanged:" + name, hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest)
    t = pd.read_csv(folder / "tournaments.csv")
    p = pd.read_csv(folder / "placements.csv")
    countries = pd.read_csv(folder / "country_prizes.csv")
    audit = pd.read_csv(folder / "country_audit.csv")
    w = pd.read_csv(folder / "forecast_twitch_monthly.csv")
    q = pd.read_csv(folder / "forecast_prize_quarterly.csv")
    q["split"] = q.quarter.map(lambda x: "train" if x[:4] <= "2023" else "validation" if x[:4] == "2024" else "test")
    save("forecast_prize_quarterly.csv", q)
    quarterly_predictions = []
    for family, group in q.groupby("game_family"):
        group = group.sort_values("quarter").copy()
        group["prediction"] = group.target_prize_pool_usd.shift(4)
        group["evaluation"] = "rolling_one_step_seasonal_naive"
        quarterly_predictions.append(group)
    quarterly_predictions = pd.concat(quarterly_predictions, ignore_index=True)
    save("forecast_baseline_predictions.csv", quarterly_predictions)
    quarterly_scores = []
    for (family, split), group in quarterly_predictions[quarterly_predictions.split != "train"].groupby(["game_family", "split"]):
        valid = group.dropna(subset=["prediction", "target_prize_pool_usd"])
        error = valid.prediction - valid.target_prize_pool_usd
        quarterly_scores.append({"game_family": family, "split": split, "evaluation_rows": len(valid),
                                 "MAE_usd": error.abs().mean(), "RMSE_usd": error.pow(2).mean() ** .5,
                                 "evaluation": "rolling_one_step; earlier observed test targets allowed as lag"})
    save("forecast_baseline_scores.csv", pd.DataFrame(quarterly_scores))
    check("all_country_tournaments_audited", set(t.tournament_id) == set(audit.tournament_id))
    check("country_audit_unique", audit.tournament_id.is_unique)
    check("countries_only_reconciled", set(countries.tournament_id) == set(audit[audit.status == "reconciled"].tournament_id))
    check("country_totals", (countries.groupby("tournament_id").prize_cents.sum() - t.set_index("tournament_id").pool_cents).dropna().abs().le(2).all())
    check("quarterly_money_conserved", int(q.pool_cents.sum()) == int(t.pool_cents.sum()))
    check("quarterly_count_conserved", int(q.observed_tournament_count.sum()) == len(t))
    check("placement_parent", p.tournament_id.isin(t.tournament_id).all())
    readiness, acfs, scores = [], [], []
    for label, frame, time, target, frequency, lags in [
        ("earnings", q, "period_start", "target_prize_pool_usd", "QS", [1, 4]),
        ("twitch", w, "month_start", "hours_watched", "MS", [1, 12])]:
        for family, group in frame.groupby("game_family"):
            group = group.sort_values(time).copy()
            valid = group[group[target].notna()]
            first = valid[time].min()
            group = group[group[time] >= first]
            expected = pd.date_range(group[time].min(), group[time].max(), freq=frequency)
            dates = pd.DatetimeIndex(pd.to_datetime(group[time]))
            check(f"regular_grid:{label}:{family}", dates.equals(expected))
            train = group[group.split == "train"]
            row = {"dataset": label, "game_family": family, "target": target,
                   "first_observed_period": first, "last_period": group[time].max(),
                   "periods_from_first_observation": len(group), "missing_target_periods": int(group[target].isna().sum()),
                   "zero_target_periods": int(group[target].eq(0).sum()),
                   "forecast_requires_missing_policy": bool(group[target].isna().any()),
                   "train_target_median": train[target].median(), "train_target_p95": train[target].quantile(.95)}
            for split in ["train", "validation", "test"]:
                row[split + "_observed_periods"] = int(group[group.split == split][target].notna().sum())
            readiness.append(row)
            for lag in lags:
                acfs.append({"dataset": label, "game_family": family, "target": target, "lag": lag,
                             "train_only_autocorrelation": train[target].autocorr(lag=lag),
                             "train_observed_periods": int(train[target].notna().sum())})
            if label == "twitch":
                for metric in ["hours_watched", "avg_viewers", "peak_viewers"]:
                    group["prediction"] = group[metric].shift(12)
                    for split in ["validation", "test"]:
                        sample = group[group.split == split].dropna(subset=["prediction", metric])
                        error = sample.prediction - sample[metric]
                        scores.append({"game_family": family, "target": metric, "split": split,
                                       "n": len(sample), "MAE": error.abs().mean(), "RMSE": (error.pow(2).mean()) ** .5,
                                       "evaluation": "rolling_one_step_seasonal_naive_lag12"})
    save("forecast_readiness.csv", pd.DataFrame(readiness))
    annual_counts = t.groupby(["game_family", "year"]).size().rename("observed_tournaments").reset_index()
    save("eda_annual_source_counts.csv", annual_counts)
    missing_quarters = q[q.target_prize_pool_usd.isna()].copy()
    save("forecast_missing_quarters.csv", missing_quarters)
    forecast_status = []
    for family, group in q.groupby("game_family"):
        test = group[group.split == "test"]
        missing = test[test.target_prize_pool_usd.isna()].quarter.tolist()
        forecast_status.append({"game_family": family, "missing_2025_quarters": " | ".join(missing),
                                "full_2025_test_has_observations": not missing,
                                "source_coverage_verified": False,
                                "status": "blocked_full_2025_test_missing_observations" if missing else "structurally_complete_but_source_coverage_unverified"})
    save("forecast_status.csv", pd.DataFrame(forecast_status))
    save("eda_train_autocorrelation.csv", pd.DataFrame(acfs))
    train_quarters = q[q.split == "train"].copy()
    train_quarters["quarter_of_year"] = train_quarters.quarter.str[-1].astype(int)
    save("eda_prize_train_seasonality.csv", train_quarters.groupby(["game_family", "quarter_of_year"], as_index=False).target_prize_pool_usd.agg(["mean", "median", "count"]))
    save("forecast_twitch_baseline_scores.csv", pd.DataFrame(scores))
    save("eda_earnings_descriptive.csv", t.groupby("game_family").pool_cents.describe().reset_index())
    top = t.sort_values("pool_cents", ascending=False).groupby("game_family").head(10)
    save("eda_largest_tournaments.csv", top)
    sensitivity = t.groupby("game_family").agg(all_tournaments=("tournament_id", "size"), all_pool_cents=("pool_cents", "sum"), strict_tournaments=("strict_quality", "sum")).reset_index()
    strict_pool = t[t.strict_quality].groupby("game_family").pool_cents.sum()
    sensitivity["strict_pool_cents"] = sensitivity.game_family.map(strict_pool)
    sensitivity["strict_share_of_source_pool_pct"] = sensitivity.strict_pool_cents / sensitivity.all_pool_cents * 100
    save("eda_quality_sensitivity.csv", sensitivity)
    quality = t.quality_note.fillna("no_flag").replace("", "no_flag").value_counts().rename_axis("quality_note").reset_index(name="tournaments")
    save("eda_quality_flags.csv", quality)
    dictionary = []
    for name in ["tournaments.csv", "placements.csv", "twitch_monthly.csv", "game_monthly_panel.csv", "country_prizes.csv", "country_year.csv", "forecast_prize_quarterly.csv"]:
        table = pd.read_csv(folder / name)
        for column in table:
            dictionary.append({"table": name, "column": column, "inferred_dtype": str(table[column].dtype),
                               "nullable_in_release": bool(table[column].isna().any()),
                               "unit_hint": "USD cents" if column.endswith("cents") else "USD" if column.endswith("usd") else "percent" if column.endswith("pct") else "see handoff/schema source"})
    save("data_dictionary.csv", pd.DataFrame(dictionary))
    shutil.copyfile(ROOT / "docs/ANALYSIS_HANDOFF_V1.md", folder / "README_VI.md")
    pending = audit[audit.status != "reconciled"]
    missing_2025 = q[q.split.eq("test") & q.target_prize_pool_usd.isna()]
    missing_text = "; ".join(f"{family}: {', '.join(group.quarter)}" for family, group in missing_2025.groupby("game_family")) or "không có"
    year_2025_text = "; ".join(f"{r.game_family}: {r.observed_tournaments}" for r in annual_counts[annual_counts.year.eq(2025)].itertuples())
    sensitivity_text = "; ".join(f"{r.game_family}: {r.strict_share_of_source_pool_pct:.2f}%" for r in sensitivity.itertuples())
    correlations = pd.read_csv(folder / "eda_correlations_descriptive.csv")
    correlation_text = "; ".join(f"{r.game_family}: {r.hours_vs_pool:.3f} (n={r.n})" for r in correlations[correlations.method.eq("pearson")].itertuples())
    country_coverage = pd.read_csv(folder / "country_coverage.csv")
    lowest = country_coverage.loc[country_coverage.country_money_coverage_pct.idxmin()]
    report = f"""# Kết quả EDA và mức sẵn sàng bàn giao

- Earnings: {len(t):,} giải, {len(p):,} placements.
- Twitch chính: {len(w)} game–tháng; không phải người xem từng giải.
- Quốc gia: {len(countries):,} dòng; {audit.status.eq('reconciled').sum():,}/{len(audit):,} bảng giải đối chiếu đạt.
- Độ phủ tiền quốc gia: {manifest['country_prize_coverage_pct']:.2f}% tổng quỹ thưởng trong tập Earnings. Không dùng tỷ trọng trên tập đã duyệt để khẳng định toàn thị trường.
- Còn {len(pending):,} bảng quốc gia thiếu hoặc tổng không khớp; đã cách ly, không bịa/hiệu chỉnh tiền.

## Kết luận sử dụng

Dashboard mô tả có thể triển khai theo README_VI.md. Bản đồ phải có bộ lọc/nhãn độ phủ và chỉ gọi là tiền thưởng theo quốc gia tuyển thủ. Chưa có mapping khu vực thi đấu/châu lục được duyệt.

Mục tiêu dự báo chính là tổng quỹ thưởng quý từ nguồn. Xem forecast_readiness.csv trước khi chọn family; kỳ thiếu cần chính sách riêng, không xóa khoảng trống hay tự điền 0. Chia thời gian đã có trong cột split. Baseline đã chuẩn bị; chưa huấn luyện/chọn mô hình cuối.

**Chưa được coi dự báo năm 2025 của cả bốn game là sẵn sàng:** kỳ test không có quan sát: {missing_text}. Xem forecast_status.csv để biết game nào có đủ kỳ quan sát. Độ phủ nguồn vẫn chưa xác minh ngay cả khi có đủ kỳ. Cần bổ sung/kiểm tra nguồn 2025, hoặc được nhóm đồng ý đổi mốc đánh giá; không tự thu hẹp scope dự án.

## Phát hiện quan trọng cho dashboard và mô hình

- Số giải quan sát năm 2025: {year_2025_text}. Xem eda_annual_source_counts.csv để đối chiếu các năm trước; giảm số giải quan sát có thể là cảnh báo độ phủ, không được tự diễn giải là thị trường sụp giảm.
- Bộ lọc nghiêm ngặt giữ quỹ thưởng: {sensitivity_text}. Bỏ mọi giải có cờ chất lượng làm thay đổi target; dùng mục tiêu quỹ thưởng nguồn và báo cáo độ nhạy riêng.
- Tương quan Pearson giờ xem–quỹ thưởng tháng: {correlation_text}. Spearman có trong bảng tương quan. Không hứa mô hình nhiều biến sẽ tốt; cần kiểm soát mùa vụ/xu hướng và dùng lag hợp lệ.
- Quốc gia có độ phủ tiền không đồng đều theo năm: thấp nhất {lowest.game_family}, năm {int(lowest.year)}, {lowest.country_money_coverage_pct:.2f}%. Dashboard phải hiện độ phủ theo bộ lọc, không chỉ một con số toàn tập.
- Twitch không thiếu tháng trong bốn chuỗi chính; Valorant có lịch sử ngắn hơn. Dữ liệu sau 2024-09 không có, không điền thêm các tháng giả để ghép với Earnings 2025.

EDA toàn lịch sử là mô tả, không là bằng chứng nhân quả và không dùng để chọn mô hình theo test. Seasonality/autocorrelation phục vụ mô hình chỉ tính train. IQR giữ nguyên các tháng bùng nổ.

## Tệp nên đọc

- eda_quality_sensitivity.csv: mức thay đổi khi chỉ dùng tập nghiêm ngặt.
- eda_correlations_descriptive.csv: tương quan có n từng family, chưa loại xu hướng/mùa vụ.
- forecast_readiness.csv, eda_train_autocorrelation.csv: số kỳ và cấu trúc thời gian.
- country_coverage.csv: độ phủ bản đồ theo family–năm.
- eda/01–06: xu hướng Twitch, tiền thưởng, tỷ trọng, độ phủ và scatter.

## Giới hạn chưa thể giải quyết bằng cleaning

Chưa xác minh đủ website; quỹ thưởng và phân bổ có thể sai ở nguồn. Thiếu Twitch sau 2024-09, YouTube và quốc gia khán giả. Không có prize_per_viewer giải hay ROI. Bàn giao được theo phạm vi này, không phải cam kết không có trở ngại hay dữ liệu đúng tuyệt đối.
"""
    (folder / "EDA_REPORT_VI.md").write_text(report, encoding="utf-8")
    manifest["release_audit"] = checks
    manifest["outputs_sha256"] = {str(f.relative_to(folder)): hashlib.sha256(f.read_bytes()).hexdigest() for f in folder.rglob("*") if f.is_file() and f != manifest_path}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checks": len(checks), "passed": sum(c["passed"] for c in checks),
                      "country_statuses": manifest["country_statuses"], "forecast_readiness": readiness}, ensure_ascii=False, indent=2))
    print("Bộ bàn giao:", folder)


if __name__ == "__main__":
    main()

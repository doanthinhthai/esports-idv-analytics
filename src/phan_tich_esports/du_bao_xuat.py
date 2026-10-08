"""Xuất dữ liệu Tableau, thông tin lần chạy và ghi chú kết quả dự báo."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from phan_tich_esports.cau_hinh import PROCESSED_DIR, REPORTS_DIR
from phan_tich_esports.du_bao_tuong_lai import FOREST_PARAMS, TARGET
from phan_tich_esports.mo_hinh_core import MODEL_LABELS


def build_timeline(history: pd.DataFrame, forecast: pd.DataFrame, primary: str) -> pd.DataFrame:
    """Một bảng vẽ lịch sử và dự báo; actual được giữ null tại các quý thiếu."""
    parts = []
    for model, label in MODEL_LABELS.items():
        part = history[["game_family", "quarter", "period_start", TARGET]].rename(
            columns={TARGET: "actual_prize_pool_usd"}
        ).copy()
        part["model"] = model
        part["model_label"] = label
        part["target_policy"] = "source"
        part["record_type"] = np.where(part["actual_prize_pool_usd"].notna(), "historical", "historical_missing")
        part["horizon_quarters"] = 0
        # Metadata cùng một lần chạy để Tableau không phải JOIN bảng theo quý.
        for field in ["forecast_origin", "source_release", "generated_at_utc", "source_coverage_verified"]:
            part[field] = forecast.iloc[0][field]
        part["data_warning"] = "source_coverage_unverified" if not forecast.iloc[0]["source_coverage_verified"] else ""
        parts.append(part)
    future = forecast.copy()
    future["record_type"] = "forecast"
    timeline = pd.concat([*parts, future], ignore_index=True)
    timeline["is_primary_model"] = timeline["model"].eq(primary)
    timeline["display_prize_pool_usd"] = timeline["actual_prize_pool_usd"].where(
        timeline["record_type"].ne("forecast"), timeline["predicted_prize_pool_usd"]
    )
    return timeline.sort_values(["model", "game_family", "period_start"]).reset_index(drop=True)


def validate_future_export(forecast: pd.DataFrame, origin: pd.Period) -> None:
    """Chặn nhầm actual, lệch quý hoặc lặp khóa trước khi xuất dữ liệu."""
    keys = ["game_family", "quarter", "target_policy", "model"]
    if len(forecast) != 48 or forecast.duplicated(keys).any():
        raise ValueError("Cần 48 dòng duy nhất: 4 game × 4 quý × 3 model")
    if forecast["actual_prize_pool_usd"].notna().any():
        raise ValueError("Dự báo tương lai không được chứa actual")
    for _, group in forecast.groupby(["game_family", "model"]):
        expected = [str(origin + step) for step in range(1, 5)]
        if group.sort_values("horizon_quarters")["quarter"].tolist() != expected:
            raise ValueError("Dự báo phải bắt đầu sau origin và liên tiếp 4 quý")
    values = forecast["predicted_prize_pool_usd"]
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Dự báo phải hữu hạn, không âm")
    with_interval = forecast.dropna(subset=["lower_80_usd", "upper_80_usd"])
    if not with_interval["predicted_prize_pool_usd"].between(
        with_interval["lower_80_usd"], with_interval["upper_80_usd"]
    ).all():
        raise ValueError("Khoảng dự báo không bao quanh điểm dự báo")


def export_forecasts(release: Path, manifest: dict, history: pd.DataFrame,
                     origin: pd.Period, primary: str, forecast: pd.DataFrame,
                     backtest: pd.DataFrame, metrics: pd.DataFrame) -> None:
    """Xuất 3 bảng cho B và báo cáo kỹ thuật có thể truy vết."""
    generated = pd.Timestamp.now(tz="UTC").isoformat()
    verified = manifest.get("final_source_coverage_verified") is True
    forecast = forecast.copy()
    forecast["actual_prize_pool_usd"] = np.nan
    forecast["evaluation_available"] = False
    forecast["evaluation_status"] = "future_not_evaluated"
    forecast["is_primary_model"] = forecast["model"].eq(primary)
    forecast["source_release"] = release.name
    forecast["generated_at_utc"] = generated
    forecast["source_coverage_verified"] = verified
    forecast["data_warning"] = forecast.apply(
        lambda row: ";".join(filter(None, [
            "source_coverage_unverified" if not verified else "",
            "missing_recent_actual" if row["missing_recent_quarters"] else "",
            "seasonal_fallback" if row["seasonal_fallback_used"] else "",
        ])), axis=1,
    )
    validate_future_export(forecast, origin)
    timeline = build_timeline(history, forecast, primary)
    for frame in [metrics, backtest]:
        frame["source_release"] = release.name
        frame["generated_at_utc"] = generated
        frame["is_primary_model"] = frame["model"].eq(primary)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    forecast.to_csv(PROCESSED_DIR / "tableau_future_forecasts.csv", index=False, encoding="utf-8-sig")
    timeline.to_csv(PROCESSED_DIR / "tableau_forecast_timeline.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(PROCESSED_DIR / "tableau_backtest_metrics.csv", index=False, encoding="utf-8-sig")
    backtest.to_csv(REPORTS_DIR / "future_backtest_predictions.csv", index=False, encoding="utf-8-sig")
    metadata = {
        "source_release": release.name,
        "input_sha256": hashlib.sha256((release / "forecast_prize_quarterly.csv").read_bytes()).hexdigest(),
        "generated_at_utc": generated, "forecast_origin": str(origin),
        "forecast_quarters": [str(origin + h) for h in range(1, 5)],
        "primary_model": primary, "target_policy": "source", "horizon_quarters": 4,
        "selection_rule": "minimum pooled selection RMSE, then MAE, then model name",
        "selection_origins": sorted(backtest.loc[backtest["evaluation_phase"].eq("selection"), "forecast_origin"].unique()),
        "holdout_origin": str(origin - 4), "forest_params": FOREST_PARAMS,
        "source_coverage_verified": verified,
        "interval_method": "exploratory absolute residual quantile by game/model/horizon; minimum 8 samples; not guaranteed 80%",
        "missing_policy": "keep actual null; train-only feature imputation; seasonal median fallback flagged",
    }
    (REPORTS_DIR / "future_forecast_run.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    overall = metrics[metrics["game_family"].eq("Overall") & metrics["horizon_quarters"].eq(0)]
    lines = ["# Kết quả dự báo bốn quý", "",
             f"- Release: `{release.name}`; mốc dữ liệu: **{origin}**.",
             f"- Dự báo: **{origin + 1}–{origin + 4}**; model được chọn: **{MODEL_LABELS[primary]}**.",
             "- Mốc dữ liệu là quý đã kết thúc theo lịch, không phải xác nhận nguồn đã thu thập đầy đủ.",
             "- Chọn model bằng backtest trước holdout, sau đó học lại bằng toàn bộ actual hợp lệ đến mốc dữ liệu.",
             "- Bộ kiểm định one-step cũ và bộ dự báo nhiều bước này có giao thức khác nhau; không so trực tiếp RMSE để kết luận cải thiện.", "",
             "| Giai đoạn | Mô hình | Số mẫu | MAE (USD) | RMSE (USD) |",
             "|---|---|---:|---:|---:|"]
    for row in overall.itertuples():
        lines.append(f"| {row.evaluation_phase} | {row.model_label} | {row.n_evaluated} | {row.mae_usd:,.0f} | {row.rmse_usd:,.0f} |")
    lines.extend(["", "## Giới hạn diễn giải", "",
                  "- Các cửa sổ selection chồng lấn; số dòng dự báo không phải số mẫu độc lập.",
                  "- Khoảng 80% chỉ là dải tham khảo từ sai số selection, cùng tập dùng chọn model; không có bảo đảm xác suất 80%.",
                  "- Xem interval_coverage_pct trên holdout để kiểm tra thực nghiệm; số mẫu holdout ít.",
                  "- Không lấy kết quả tương lai làm actual hay tính MAE/RMSE khi chưa có thực tế.",
                  "- Dữ liệu mới nhất hiện có thể cũ hơn ngày chạy. Các quý dự báo là sau mốc dữ liệu, không nhất thiết sau hôm nay.",
                  "- Thiếu dữ liệu lịch sử giữ nguyên null; cảnh báo missing_recent_quarters và seasonal_fallback_used đi kèm từng dự báo.",
                  "- Cần cập nhật release từ pipeline của A rồi chạy lại; script không crawl dữ liệu và không tự chạy theo lịch.", "",
                  "Hướng dẫn Tableau: `docs/TABLEAU_DU_BAO_TUONG_LAI.md`."])
    (REPORTS_DIR / "future_forecast_notes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

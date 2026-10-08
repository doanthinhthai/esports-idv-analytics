"""Backtest nhiều mốc, chọn mô hình trước holdout và ước lượng dải sai số."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from phan_tich_esports.cau_hinh import FAMILIES
from phan_tich_esports.du_bao_tuong_lai import TARGET, recursive_forecast


def attach_actual(predictions: pd.DataFrame, data: pd.DataFrame, phase: str) -> pd.DataFrame:
    """Chỉ nối actual sau khi dự báo hoàn tất; null không tham gia chấm điểm."""
    actual = data[["game_family", "quarter", TARGET]].rename(columns={TARGET: "actual_prize_pool_usd"})
    result = predictions.merge(actual, on=["game_family", "quarter"], how="left", validate="many_to_one")
    result["evaluation_phase"] = phase
    result["evaluation_available"] = result["actual_prize_pool_usd"].notna()
    result["residual_usd"] = result["actual_prize_pool_usd"] - result["predicted_prize_pool_usd"]
    result["absolute_error_usd"] = result["residual_usd"].abs()
    return result


def summarize_backtest(predictions: pd.DataFrame) -> pd.DataFrame:
    """Xuất cả Overall và từng game; không lấy trung bình các RMSE."""
    frames = [predictions, predictions.assign(game_family="Overall")]
    combined = pd.concat(frames, ignore_index=True)
    combined = pd.concat([combined, combined.assign(horizon_quarters=0)], ignore_index=True)
    keys = ["evaluation_phase", "game_family", "model", "model_label", "horizon_quarters"]
    rows = []
    for key, group in combined.groupby(keys):
        scored = group[group["evaluation_available"]]
        errors = scored["residual_usd"]
        intervals = scored.dropna(subset=["lower_80_usd", "upper_80_usd"]) if "lower_80_usd" in scored else scored.iloc[:0]
        coverage = np.nan
        if len(intervals):
            coverage = 100 * intervals["actual_prize_pool_usd"].between(
                intervals["lower_80_usd"], intervals["upper_80_usd"]
            ).mean()
        rows.append({**dict(zip(keys, key)), "target_policy": "source",
                     "n_predictions": len(group), "n_evaluated": len(scored),
                     "n_origins": group["forecast_origin"].nunique(),
                     "evaluation_coverage_pct": 100 * len(scored) / len(group),
                     "mae_usd": errors.abs().mean(),
                     "rmse_usd": math.sqrt(errors.pow(2).mean()) if len(errors) else np.nan,
                     "n_interval_evaluated": len(intervals), "interval_coverage_pct": coverage,
                     "protocol": "recursive_multi_step"})
    return pd.DataFrame(rows)


def interval_radii(selection: pd.DataFrame) -> pd.DataFrame:
    """Dải 80% tham khảo từ sai số ngoài tập học, riêng game/model/horizon."""
    rows = []
    for key, group in selection.groupby(["game_family", "model", "horizon_quarters"]):
        errors = group["absolute_error_usd"].dropna().sort_values().to_numpy()
        n = len(errors)
        # Dữ liệu thời gian và các cửa sổ chồng lấn: không cam kết coverage 80%.
        rank = min(n, math.ceil((n + 1) * 0.8))
        rows.append({"game_family": key[0], "model": key[1], "horizon_quarters": key[2],
                     "interval_calibration_n": n,
                     "radius_usd": float(errors[rank - 1]) if n >= 8 else np.nan})
    result = pd.DataFrame(rows).sort_values(["game_family", "model", "horizon_quarters"])
    result["radius_usd"] = result.groupby(["game_family", "model"])["radius_usd"].cummax()
    return result


def attach_intervals(predictions: pd.DataFrame, radii: pd.DataFrame) -> pd.DataFrame:
    """Gắn khoảng tham khảo; thiếu mẫu thì để trống, không tự đặt phần trăm."""
    result = predictions.merge(radii, on=["game_family", "model", "horizon_quarters"],
                               how="left", validate="many_to_one")
    result["lower_80_usd"] = (result["predicted_prize_pool_usd"] - result["radius_usd"]).clip(lower=0)
    result["upper_80_usd"] = result["predicted_prize_pool_usd"] + result["radius_usd"]
    result["interval_status"] = np.where(result["radius_usd"].notna(),
                                         "exploratory_80pct_not_guaranteed", "insufficient_calibration")
    return result.drop(columns="radius_usd")


def evaluate_and_select(data: pd.DataFrame, origin: pd.Period, progress=print):
    """Giữ bốn quý cuối làm holdout; chọn model bằng tám mốc sớm hơn."""
    holdout_origin = origin - 4
    # Mọi target dùng chọn model đều <= holdout_origin.
    candidates = pd.period_range(data["period"].min() + 7, holdout_origin - 4, freq="Q")
    valid = []
    for cutoff in candidates:
        history = data[data["period"] <= cutoff]
        counts = history.groupby("game_family")[TARGET].count()
        if all(counts.get(family, 0) >= 8 for family in FAMILIES):
            valid.append(cutoff)
    origins = valid[-8:]
    if len(origins) < 4:
        raise ValueError("Không đủ lịch sử cho tối thiểu 4 mốc chọn model và holdout 4 quý")
    parts = []
    for i, cutoff in enumerate(origins, 1):
        progress(f"Backtest {i}/{len(origins)}: học đến {cutoff}, dự báo 4 quý")
        forecast = recursive_forecast(data, cutoff)
        parts.append(attach_actual(forecast, data, "selection"))
    selection = pd.concat(parts, ignore_index=True)
    metrics = summarize_backtest(selection)
    overall = metrics[metrics["game_family"].eq("Overall") & metrics["horizon_quarters"].eq(0)]
    if overall["n_evaluated"].nunique() != 1 or overall["n_evaluated"].min() == 0:
        raise ValueError("Mô hình phải được so sánh trên cùng các target có thực tế")
    primary = overall.sort_values(["rmse_usd", "mae_usd", "model"]).iloc[0]["model"]
    radii = interval_radii(selection)
    progress(f"Đã chọn {primary}; kiểm tra holdout từ {holdout_origin + 1} đến {origin}")
    holdout = attach_actual(recursive_forecast(data, holdout_origin), data, "holdout")
    holdout = attach_intervals(holdout, radii)
    # Không dùng holdout để chọn lại model hay hiệu chỉnh khoảng dự báo.
    predictions = pd.concat([selection, holdout], ignore_index=True)
    metrics = summarize_backtest(predictions)
    metrics["is_primary_model"] = metrics["model"].eq(primary)
    return str(primary), radii, predictions, metrics

"""Đọc chuỗi quý và dự báo nối tiếp; không sửa giá trị thực tế bị thiếu."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from phan_tich_esports.cau_hinh import FAMILIES, latest_release
from phan_tich_esports.mo_hinh_core import (
    FEATURES, MODEL_LABELS, add_lag_features,
    build_linear_pipeline, build_rf_pipeline, clipped_predict,
)

TARGET = "target_prize_pool_usd"
# Cố định trước backtest, không lấy tham số đã tối ưu bằng các quý tương lai.
FOREST_PARAMS = {"max_depth": 4, "min_samples_leaf": 1, "max_features": "sqrt"}


def prepare_quarterly(data: pd.DataFrame) -> pd.DataFrame:
    """Kiểm tra khóa, ngày và tiền; bổ sung các quý vắng bằng null."""
    required = {"game_family", "quarter", "period_start", TARGET}
    if not required.issubset(data.columns):
        raise ValueError(f"Thiếu cột: {sorted(required.difference(data.columns))}")
    frame = data[list(required)].copy()
    if frame[list(required - {TARGET})].isna().any().any():
        raise ValueError("Khóa game/quý/ngày không được thiếu")
    frame["period_start"] = pd.to_datetime(frame["period_start"], errors="raise")
    frame["period"] = frame["period_start"].dt.to_period("Q")
    if not frame["quarter"].eq(frame["period"].astype(str)).all():
        raise ValueError("quarter không khớp period_start")
    if not frame["period_start"].eq(frame["period"].dt.start_time).all():
        raise ValueError("period_start phải là ngày đầu quý")
    if frame.duplicated(["game_family", "period"]).any():
        raise ValueError("Trùng khóa game_family + quarter")
    if set(frame["game_family"]) != set(FAMILIES):
        raise ValueError("Dữ liệu phải chứa đúng bốn nhóm game của dự án")
    frame[TARGET] = pd.to_numeric(frame[TARGET], errors="raise")
    observed = frame[TARGET].dropna()
    if (observed < 0).any() or not np.isfinite(observed).all():
        raise ValueError("Quỹ thưởng phải hữu hạn, không âm hoặc null")
    parts = []
    for family, group in frame.groupby("game_family", sort=False):
        values = group.set_index("period")[TARGET].reindex(
            pd.period_range(frame["period"].min(), frame["period"].max(), freq="Q")
        )
        part = values.rename_axis("period").reset_index()
        part["game_family"] = family
        part["quarter"] = part["period"].astype(str)
        part["period_start"] = part["period"].dt.start_time
        part["quarter_of_year"] = part["period"].dt.quarter.astype(str)
        parts.append(part)
    return pd.concat(parts, ignore_index=True).sort_values(["game_family", "period"])


def load_future_inputs(release: Path | None = None, as_of: str | None = None):
    """Chọn mốc quý đã kết thúc, độc lập với nhãn train/test 2023–2025 cũ."""
    release = release or latest_release()
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("stage") != "analysis_release_v1_policy_clean_not_source_verified":
        raise ValueError("Stage release không phù hợp; cần rà soát hợp đồng dữ liệu")
    data = prepare_quarterly(pd.read_csv(release / "forecast_prize_quarterly.csv"))
    last_closed = pd.Timestamp.now(tz="Asia/Bangkok").tz_localize(None).to_period("Q") - 1
    observed_closed = data[data[TARGET].notna() & (data["period"] <= last_closed)]
    if observed_closed.empty:
        raise ValueError("Không có quý đã kết thúc với dữ liệu thực tế")
    # Không để các dòng placeholder toàn null đẩy mốc dự báo sang tương lai.
    latest_allowed = observed_closed["period"].max()
    origin = pd.Period(as_of, freq="Q") if as_of else latest_allowed
    if origin > latest_allowed or origin < data["period"].min():
        raise ValueError("Mốc dự báo phải nằm trong dữ liệu và là quý đã kết thúc")
    history = data[data["period"] <= origin].copy()
    for family in FAMILIES:
        if history.loc[history["game_family"].eq(family), TARGET].notna().sum() < 8:
            raise ValueError(f"{family}: cần tối thiểu 8 quý có dữ liệu thực tế")
    return release, manifest, history, origin


def fit_models(history: pd.DataFrame) -> dict:
    """Học từ target quan sát; giá trị thay thế chỉ nằm trong pipeline đặc trưng."""
    featured = add_lag_features(history.sort_values(["game_family", "period"]), TARGET)
    train = featured[featured[TARGET].notna() & featured["lag_4"].notna()]
    if train.empty:
        raise ValueError("Không đủ dữ liệu lag_4 để huấn luyện")
    counts = train.groupby("game_family")[TARGET].count()
    if any(counts.get(family, 0) < 4 for family in FAMILIES):
        raise ValueError("Mỗi game cần tối thiểu 4 dòng huấn luyện có target và lag_4")
    models = {"linear_regression": build_linear_pipeline(),
              "random_forest": build_rf_pipeline(FOREST_PARAMS)}
    for model in models.values():
        model.fit(train[FEATURES], train[TARGET])
    return models


def recursive_forecast(data: pd.DataFrame, origin: pd.Period, horizon: int = 4) -> pd.DataFrame:
    """Cắt dữ liệu tại origin trước khi học; mỗi model có lịch sử dự báo riêng."""
    if horizon not in (1, 2, 3, 4):
        raise ValueError("Chỉ hỗ trợ 1–4 quý đã thiết kế cho backtest")
    history = data[data["period"] <= origin].sort_values(["game_family", "period"]).copy()
    models = fit_models(history)
    rows = []
    for name in MODEL_LABELS:
        working = history.copy()
        for step in range(1, horizon + 1):
            period = origin + step
            new = pd.DataFrame({"game_family": FAMILIES, "period": period,
                                "quarter": str(period), "period_start": period.start_time,
                                "quarter_of_year": str(period.quarter), TARGET: np.nan})
            working = pd.concat([working, new], ignore_index=True).sort_values(["game_family", "period"])
            featured = add_lag_features(working, TARGET)
            future = featured[featured["period"].eq(period)].copy()
            if name == "seasonal_naive":
                # Khi cùng quý năm trước thiếu, chỉ dùng trung vị lịch sử đã biết.
                # Đây là fallback có gắn cờ, không giả mạo target thực tế bằng 0.
                medians = working[working["period"] < period].groupby("game_family")[TARGET].median()
                prediction = future["lag_4"].fillna(future["game_family"].map(medians)).to_numpy()
                fallback = future["lag_4"].isna().to_numpy()
            else:
                prediction = clipped_predict(models[name], future)
                fallback = np.zeros(len(future), dtype=bool)
            if not np.isfinite(prediction).all():
                raise ValueError("Không đủ lịch sử để tạo dự báo hữu hạn")
            for i, (_, item) in enumerate(future.iterrows()):
                family = item["game_family"]
                value = float(prediction[i])
                working.loc[working["game_family"].eq(family) & working["period"].eq(period), TARGET] = value
                observed = history[history["game_family"].eq(family) & history[TARGET].notna()]
                recent = history[history["game_family"].eq(family) & (history["period"] > origin - 4)]
                rows.append({"game_family": family, "quarter": str(period),
                             "period_start": period.start_time, "forecast_origin": str(origin),
                             "horizon_quarters": step, "model": name, "model_label": MODEL_LABELS[name],
                             "target_policy": "source", "predicted_prize_pool_usd": value,
                             "last_observed_quarter": str(observed["period"].max()),
                             "missing_recent_quarters": int(recent[TARGET].isna().sum()),
                             "feature_missing_count": int(item[FEATURES].isna().sum()),
                             "seasonal_fallback_used": bool(fallback[i]),
                             "uses_recursive_predictions": step > 1,
                             "protocol": "recursive_multi_step"})
    return pd.DataFrame(rows)

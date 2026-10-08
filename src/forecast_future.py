# -*- coding: utf-8 -*-
"""Chạy dự báo bốn quý sau mốc dữ liệu và xuất kết quả bàn giao Tableau."""

import argparse
from pathlib import Path

from phan_tich_esports.cau_hinh import configure_console
from phan_tich_esports.du_bao_danh_gia import attach_intervals, evaluate_and_select
from phan_tich_esports.du_bao_tuong_lai import load_future_inputs, recursive_forecast
from phan_tich_esports.du_bao_xuat import export_forecasts


def main() -> None:
    """Dự báo độc lập với bộ kiểm định one-step cũ; không cần chạy lại EDA."""
    configure_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, help="Thư mục release; mặc định bản mới nhất")
    parser.add_argument("--as-of", help="Mốc quý đã kết thúc, ví dụ 2025Q4; mặc định tự chọn")
    args = parser.parse_args()
    release, manifest, history, origin = load_future_inputs(args.release, args.as_of)
    print(f"Release: {release.name}; mốc dữ liệu: {origin}", flush=True)
    primary, radii, backtest, metrics = evaluate_and_select(
        history, origin, progress=lambda message: print(message, flush=True)
    )
    forecast = attach_intervals(recursive_forecast(history, origin), radii)
    export_forecasts(release, manifest, history, origin, primary, forecast, backtest, metrics)
    print(f"Đã xuất {len(forecast)} dự báo ({origin + 1}–{origin + 4}) cho Tableau.")
    print("Hướng dẫn: docs/TABLEAU_DU_BAO_TUONG_LAI.md")


if __name__ == "__main__":
    main()

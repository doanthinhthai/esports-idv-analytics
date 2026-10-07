# -*- coding: utf-8 -*-
"""Điều phối bước EDA trên analysis release mới nhất.

Chạy bằng: ``python src/eda.py``.
"""

from phan_tich_esports.cau_hinh import (
    FIGURES_DIR,
    configure_charts,
    configure_console,
)
from phan_tich_esports.eda_bieu_do import (
    plot_annual_counts,
    plot_country_coverage,
    plot_quality_sensitivity,
    plot_quarterly_prize,
    plot_twitch_hours,
)
from phan_tich_esports.eda_du_lieu import load_release, write_summary


def main() -> None:
    """Đọc dữ liệu, tạo bảng tóm tắt và xuất năm biểu đồ EDA."""
    configure_console()
    configure_charts()
    release, frames, manifest = load_release()
    summary_path = write_summary(release, frames, manifest)
    plot_quarterly_prize(frames["quarterly"])
    plot_twitch_hours(frames["twitch"])
    plot_annual_counts(frames["annual_counts"])
    plot_quality_sensitivity(frames["quality_sensitivity"])
    plot_country_coverage(frames["country_coverage"])

    print(f"EDA hoàn tất từ release: {release.name}")
    print(f"Số giải đấu: {len(frames['tournaments']):,}")
    print(f"Số kết quả xếp hạng: {len(frames['placements']):,}")
    print(f"Bảng tóm tắt: {summary_path}")
    print(f"Thư mục biểu đồ: {FIGURES_DIR}")


if __name__ == "__main__":
    main()

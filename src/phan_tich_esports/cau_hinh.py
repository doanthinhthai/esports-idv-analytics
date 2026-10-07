"""Cấu hình đường dẫn, phạm vi game và định dạng biểu đồ dùng chung."""

from __future__ import annotations

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


PROJECT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
REPORTS_DIR = PROJECT_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

FAMILIES = ["Counter-Strike", "Dota 2", "League of Legends", "Valorant"]
COLORS = {
    "Counter-Strike": "#2F5597",
    "Dota 2": "#C00000",
    "League of Legends": "#D4A017",
    "Valorant": "#D1495B",
}


def latest_release() -> Path:
    """Trả về thư mục analysis release mới nhất có manifest hợp lệ."""
    candidates = sorted(
        path
        for path in PROCESSED_DIR.glob("analysis_release_v1_*")
        if path.is_dir() and (path / "manifest.json").exists()
    )
    if not candidates:
        raise FileNotFoundError(
            f"Không tìm thấy analysis_release_v1_* trong {PROCESSED_DIR}"
        )
    return candidates[-1]


def configure_charts() -> None:
    """Thiết lập kiểu chữ và độ phân giải mặc định cho biểu đồ."""
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlepad": 10,
            "figure.dpi": 120,
        }
    )


def configure_console() -> None:
    """Dùng UTF-8 để thông báo tiếng Việt hiển thị đúng trên Windows."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def style_axis(ax: plt.Axes) -> None:
    """Áp dụng lưới và đường viền thống nhất cho một trục."""
    ax.grid(True, color="#D9D9D9", alpha=0.55, linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)


def save_figure(fig: plt.Figure, filename: str) -> None:
    """Lưu biểu đồ 300 DPI vào thư mục báo cáo rồi giải phóng bộ nhớ."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        FIGURES_DIR / filename,
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)

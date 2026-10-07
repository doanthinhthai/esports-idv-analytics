"""Đọc, kiểm tra và tổng hợp dữ liệu cho bước khám phá dữ liệu."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from phan_tich_esports.cau_hinh import FAMILIES, REPORTS_DIR, latest_release


def load_release() -> tuple[Path, dict[str, pd.DataFrame], dict]:
    """Đọc release mới nhất và kiểm tra khóa, grain, phạm vi, tổng tiền."""
    release = latest_release()
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    required_files = {
        "tournaments": "tournaments.csv",
        "placements": "placements.csv",
        "twitch": "twitch_monthly.csv",
        "panel": "game_monthly_panel.csv",
        "quarterly": "forecast_prize_quarterly.csv",
        "country_coverage": "country_coverage.csv",
        "quality_sensitivity": "eda_quality_sensitivity.csv",
        "correlations": "eda_correlations_descriptive.csv",
        "annual_counts": "eda_annual_source_counts.csv",
        "forecast_status": "forecast_status.csv",
        "country_prizes": "country_prizes.csv",
    }
    missing = [
        filename
        for filename in required_files.values()
        if not (release / filename).exists()
    ]
    if missing:
        raise FileNotFoundError(f"Thiếu file trong release: {missing}")

    frames = {
        name: pd.read_csv(release / filename, encoding="utf-8-sig")
        for name, filename in required_files.items()
    }
    tournaments = frames["tournaments"]
    placements = frames["placements"]
    twitch = frames["twitch"]
    quarterly = frames["quarterly"]
    panel = frames["panel"]

    if manifest.get("stage") != "analysis_release_v1_policy_clean_not_source_verified":
        raise ValueError("Stage của release không đúng chính sách phân tích")
    if not tournaments["tournament_id"].is_unique:
        raise ValueError("tournament_id phải duy nhất")
    if not placements["placement_id"].is_unique:
        raise ValueError("placement_id phải duy nhất")
    if not placements["tournament_id"].isin(tournaments["tournament_id"]).all():
        raise ValueError("Có placement không có tournament cha")
    if twitch.duplicated(["game_family", "month_start"]).any():
        raise ValueError("Trùng khóa game_family + month_start trong Twitch")
    if panel.duplicated(["game_family", "month_start"]).any():
        raise ValueError("Trùng khóa game_family + month_start trong panel")
    if quarterly.duplicated(["game_family", "quarter"]).any():
        raise ValueError("Trùng khóa game_family + quarter")
    if set(tournaments["game_family"].unique()) != set(FAMILIES):
        raise ValueError("Danh sách game của tournaments không đúng phạm vi")
    if set(twitch["game_family"].unique()) != set(FAMILIES):
        raise ValueError("Danh sách game của Twitch không đúng phạm vi")

    starts = pd.to_datetime(tournaments["start_date"], errors="raise")
    ends = pd.to_datetime(tournaments["end_date"], errors="raise")
    if not starts.le(ends).all():
        raise ValueError("Có giải đấu có ngày bắt đầu sau ngày kết thúc")
    if not starts.between("2012-01-01", "2025-12-31").all():
        raise ValueError("Ngày giải đấu nằm ngoài phạm vi 2012-2025")
    if (tournaments["prize_pool_usd"] < 0).any():
        raise ValueError("Quỹ thưởng không được âm")

    money_from_quarters = int(round(quarterly["pool_cents"].sum()))
    money_from_tournaments = int(tournaments["pool_cents"].sum())
    count_from_quarters = int(round(quarterly["observed_tournament_count"].sum()))
    if money_from_quarters != money_from_tournaments:
        raise ValueError("Tổng tiền theo quý không khớp bảng tournaments")
    if count_from_quarters != len(tournaments):
        raise ValueError("Số giải theo quý không khớp bảng tournaments")
    return release, frames, manifest


def write_summary(
    release: Path, frames: dict[str, pd.DataFrame], manifest: dict
) -> Path:
    """Ghi bảng tóm tắt EDA có thể truy vết sang dữ liệu nguồn."""
    tournaments = frames["tournaments"]
    placements = frames["placements"]
    twitch = frames["twitch"]
    sensitivity = frames["quality_sensitivity"].set_index("game_family")
    correlations = frames["correlations"]
    correlations = correlations[correlations["method"] == "pearson"].set_index(
        "game_family"
    )
    coverage = frames["country_coverage"].groupby("game_family")[
        "country_money_coverage_pct"
    ].min()
    annual = frames["annual_counts"]
    statuses = frames["forecast_status"].set_index("game_family")
    rows: list[dict[str, object]] = []

    def add(
        section: str,
        family: str,
        metric: str,
        value: object,
        unit: str,
        note: str,
    ) -> None:
        rows.append(
            {
                "Section": section,
                "Game_Family": family,
                "Metric": metric,
                "Value": value,
                "Unit": unit,
                "Interpretation": note,
            }
        )

    add("Release", "All", "Release folder", release.name, "text", "Newest policy-clean analysis release")
    add("Release", "All", "Release stage", manifest["stage"], "text", "Source coverage is not fully verified")
    add("Scope", "All", "Tournaments", len(tournaments), "rows", "One row per tournament")
    add("Scope", "All", "Placements", len(placements), "rows", "One row per accepted team result")
    add("Scope", "All", "Twitch observations", len(twitch), "game-months", "Main Twitch category; not tournament-level viewers")
    add("Scope", "All", "Country prize observations", len(frames["country_prizes"]), "rows", "Only reconciled tournament-country tables")
    add("Scope", "All", "Total source prize pool", float(tournaments["prize_pool_usd"].sum()), "USD", "Nominal USD; not inflation-adjusted")
    add("Scope", "All", "Earliest tournament", tournaments["start_date"].min(), "date", "Approved scope begins in 2012")
    add("Scope", "All", "Latest tournament", tournaments["start_date"].max(), "date", "2025 source coverage remains unverified")
    strict_pool_share = tournaments.loc[tournaments["strict_quality"], "prize_pool_usd"].sum() / tournaments["prize_pool_usd"].sum() * 100
    add("Quality", "All", "Strict prize pool retained", float(strict_pool_share), "percent", "Sensitivity filter changes the target materially")
    add("Quality", "All", "Country prize coverage", float(manifest["country_prize_coverage_pct"]), "percent", "Coverage of source prize pool, not total market")

    for family in FAMILIES:
        family_tournaments = tournaments[tournaments["game_family"] == family]
        twitch_family = twitch[twitch["game_family"] == family]
        count_2025 = annual.loc[
            (annual["game_family"] == family) & (annual["year"] == 2025),
            "observed_tournaments",
        ]
        missing_quarters = statuses.loc[family, "missing_2025_quarters"]
        missing_text = (
            "No missing quarters"
            if pd.isna(missing_quarters) or str(missing_quarters).strip() == ""
            else str(missing_quarters)
        )
        add("Family", family, "Tournaments", len(family_tournaments), "rows", "Observed tournament metadata")
        add("Family", family, "Source prize pool", float(family_tournaments["prize_pool_usd"].sum()), "USD", "Nominal source total")
        add("Family", family, "Median tournament prize", float(family_tournaments["prize_pool_usd"].median()), "USD", "Robust typical tournament size")
        add("Family", family, "Strict prize pool retained", float(sensitivity.loc[family, "strict_share_of_source_pool_pct"]), "percent", "Sensitivity to quality policy")
        add("Family", family, "Twitch months", len(twitch_family), "months", f"{twitch_family['month_start'].min()} to {twitch_family['month_start'].max()}")
        add("Family", family, "Pearson hours-prize correlation", float(correlations.loc[family, "hours_vs_pool"]), "coefficient", f"Descriptive, n={int(correlations.loc[family, 'n'])}; not causal")
        add("Family", family, "Minimum country coverage", float(coverage.loc[family]), "percent", "Lowest annual reconciled prize coverage")
        add("Family", family, "Observed tournaments in 2025", int(count_2025.iloc[0]), "rows", "May reflect incomplete source coverage")
        add("Forecast", family, "Missing 2025 target quarters", missing_text, "quarters", "Do not impute missing observations as zero")

    summary = pd.DataFrame(rows)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output = REPORTS_DIR / "eda_summary.csv"
    summary.to_csv(output, index=False, encoding="utf-8-sig")
    return output


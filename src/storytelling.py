# -*- coding: utf-8 -*-
"""Điều phối storytelling và xuất dữ liệu bàn giao Tableau.

Chạy bằng: ``python src/storytelling.py``.
"""

from phan_tich_esports.cau_hinh import (
    PROCESSED_DIR,
    REPORTS_DIR,
    configure_console,
)
from phan_tich_esports.story_bao_cao import (
    write_storytelling_insights,
    write_tableau_handoff,
)
from phan_tich_esports.story_bieu_do import (
    plot_country_distribution,
    plot_error_concentration,
    plot_prize_structure,
    plot_twitch_prize_relationship,
)
from phan_tich_esports.story_du_lieu import (
    aggregate_country_evidence,
    build_error_analysis,
    build_evidence,
    build_tableau_predictions,
    build_tableau_summary,
    load_inputs,
    validate_exports,
)


def main() -> None:
    """Tạo bảng Tableau, bằng chứng, biểu đồ và tài liệu storytelling."""
    configure_console()
    release, frames = load_inputs()
    export = build_tableau_predictions(frames["predictions"])
    summary = build_tableau_summary(export)
    errors = build_error_analysis(export)
    top_countries, coverage_summary = aggregate_country_evidence(
        frames["country_year"], frames["country_coverage"]
    )
    evidence = build_evidence(
        frames["quarterly"],
        frames["panel"],
        frames["correlations"],
        top_countries,
        coverage_summary,
        errors,
    )

    validate_exports(frames["predictions"], export, summary)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    export.to_csv(PROCESSED_DIR / "tableau_forecast_predictions.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(PROCESSED_DIR / "tableau_forecast_summary.csv", index=False, encoding="utf-8-sig")
    errors.to_csv(REPORTS_DIR / "storytelling_error_analysis.csv", index=False, encoding="utf-8-sig")
    evidence.to_csv(REPORTS_DIR / "storytelling_evidence.csv", index=False, encoding="utf-8-sig")

    plot_prize_structure(frames["quarterly"], frames["seasonality"])
    plot_twitch_prize_relationship(frames["panel"], frames["correlations"])
    plot_country_distribution(top_countries, coverage_summary)
    plot_error_concentration(errors)
    write_storytelling_insights(
        release,
        frames["quarterly"],
        frames["panel"],
        frames["correlations"],
        top_countries,
        coverage_summary,
        errors,
    )
    write_tableau_handoff(release, export, summary)

    print(f"Release: {release.name}")
    print(f"Số dòng bảng dự báo Tableau: {len(export):,}")
    print(f"Số dòng bảng tổng hợp Tableau: {len(summary):,}")
    print("Đã ghi insight, bàn giao Tableau, bằng chứng và bốn biểu đồ.")


if __name__ == "__main__":
    main()

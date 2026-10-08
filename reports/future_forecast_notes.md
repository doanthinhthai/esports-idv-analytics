# Kết quả dự báo bốn quý

- Release: `analysis_release_v1_20261005T194400349609Z`; mốc dữ liệu: **2025Q4**.
- Dự báo: **2026Q1–2026Q4**; model được chọn: **Random forest**.
- Mốc dữ liệu là quý đã kết thúc theo lịch, không phải xác nhận nguồn đã thu thập đầy đủ.
- Chọn model bằng backtest trước holdout, sau đó học lại bằng toàn bộ actual hợp lệ đến mốc dữ liệu.
- Bộ kiểm định one-step cũ và bộ dự báo nhiều bước này có giao thức khác nhau; không so trực tiếp RMSE để kết luận cải thiện.

| Giai đoạn | Mô hình | Số mẫu | MAE (USD) | RMSE (USD) |
|---|---|---:|---:|---:|
| holdout | Linear regression | 13 | 2,881,416 | 3,920,547 |
| holdout | Random forest | 13 | 1,892,010 | 2,514,241 |
| holdout | Seasonal naive (t-4) | 13 | 1,845,569 | 2,410,869 |
| selection | Linear regression | 128 | 2,268,128 | 3,923,308 |
| selection | Random forest | 128 | 2,138,476 | 3,292,475 |
| selection | Seasonal naive (t-4) | 128 | 2,362,243 | 5,030,508 |

## Giới hạn diễn giải

- Các cửa sổ selection chồng lấn; số dòng dự báo không phải số mẫu độc lập.
- Khoảng 80% chỉ là dải tham khảo từ sai số selection, cùng tập dùng chọn model; không có bảo đảm xác suất 80%.
- Xem interval_coverage_pct trên holdout để kiểm tra thực nghiệm; số mẫu holdout ít.
- Không lấy kết quả tương lai làm actual hay tính MAE/RMSE khi chưa có thực tế.
- Dữ liệu mới nhất hiện có thể cũ hơn ngày chạy. Các quý dự báo là sau mốc dữ liệu, không nhất thiết sau hôm nay.
- Thiếu dữ liệu lịch sử giữ nguyên null; cảnh báo missing_recent_quarters và seasonal_fallback_used đi kèm từng dự báo.
- Cần cập nhật release từ pipeline của A rồi chạy lại; script không crawl dữ liệu và không tự chạy theo lịch.

Hướng dẫn Tableau: `docs/TABLEAU_DU_BAO_TUONG_LAI.md`.

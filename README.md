# Esports Market Analytics (`esports-idv-analytics`)
---

##  1. Mục tiêu & Phạm vi nghiên cứu

* **Mục tiêu:** Thu thập dữ liệu thực tế về giải đấu, quỹ tiền thưởng, thành tích thi đấu của các đội tuyển và số liệu người xem để xây dựng bức tranh toàn cảnh về thị trường thể thao điện tử, phục vụ phân tích xu hướng và dự báo thị trường.
* **Khung thời gian (Scope):** Từ **`2012-01-01`** đến **`2025-12-31`**.
* **4 Dòng game trọng tâm (4 Game Families / 5 Versions):**
  * **Counter-Strike:** Phân tích chung cấp family, nhưng bảo toàn phiên bản độc lập giữa **CS:GO** và **CS2**.
  * **Dota 2** (MOBA - PC).
  * **League of Legends (LoL)** (MOBA - PC).
  * **VALORANT** (Tactical FPS - PC, lịch sử phát hành từ tháng 04/2020).

---

##  2. Nguồn dữ liệu & Tình trạng sử dụng

| Nguồn dữ liệu | Vai trò trong dự án | Trạng thái tích hợp |
|---|---|---|
| **Esports Earnings** | Giải đấu (`tournaments`), kết quả đội (`placements`), phân bổ tiền thưởng theo quốc gia tuyển thủ (`country_prizes`). | **Đã thu thập & sử dụng chính thức** (Lưu trữ SQLite `crawl.sqlite3` 71MB + cache HTML thô). |
| **Twitch (Kaggle Dataset)** | Chỉ số người xem theo tháng giai đoạn `2016-01` đến `2024-09` (Hours Watched, Streamers, Peak/Avg Viewers). | **Đã làm sạch & sử dụng chính thức** (Gắn kết nối với Earnings qua `game_monthly_panel`). |
| **Esports Charts (escharts)** | Chỉ số người xem chi tiết từng giải đấu. | **Kiểm thử thăm dò ban đầu**, chưa đưa vào bản release chính thức do rào cản truy cập/bản quyền. |
| **Hatchet.gg** | Khảo sát nguồn người xem thay thế. | **Đánh giá sơ bộ** (Xem chi tiết tại `reports/data_quality/hatchet_source_assessment.md`). |

---

##  3. Quy mô bộ dữ liệu Release (`analysis_release_v1`)

Bộ dữ liệu phát hành chính thức mới nhất được lưu trữ tại `data/processed/analysis_release_v1_*/` và được bảo chứng tính toàn vẹn (reproducibility) bằng mã băm SHA-256 qua `manifest.json`:

* **`tournaments.csv` (14,082 dòng):** Mỗi dòng là 1 giải đấu có ngày hợp lệ, quỹ thưởng không âm trong giai đoạn 2012–2025.
* **`placements.csv` (52,551 dòng):** Mỗi dòng là 1 kết quả thứ hạng/tiền thưởng của một đội tại một giải.
* **`country_prizes.csv` (57,597 dòng):** Dữ liệu tiền thưởng chia theo quốc tịch tuyển thủ tại các giải đã đối chiếu đạt (độ phủ đạt **97.67%** tổng tiền thưởng nguồn).
* **`twitch_monthly.csv` (369 dòng):** Chuỗi thời gian người xem tháng theo từng game family trên Twitch.
* **`game_monthly_panel.csv` (369 dòng):** Bảng tổng hợp theo tháng kết hợp cả 2 chiều dữ liệu (Giải đấu + Người xem).
* **`earnings_quarantine.csv` & `country_quarantine.csv`:** Tập dữ liệu cách ly các giải thiếu thông tin hoặc tổng tiền lệch ngoài biên độ cho phép, đảm bảo không làm bẩn tập phân tích chính.

---

##  4. Nguyên tắc chất lượng & Phân tích (Data Philosophy)

1. **Bảo toàn dữ liệu thiếu (Null Policy):**
   * Không có giải quan sát trong kỳ $\neq$ thị trường không có giải. Dữ liệu thiếu được **giữ nguyên `null`, tuyệt đối không tự điền `0`**.
   * Thời kỳ trước khi game ra mắt (ví dụ Valorant trước 2020) được định nghĩa là chưa phát hành, không phải chuỗi số 0.
2. **Đối chiếu quỹ thưởng (Prize Reconciliation):**
   * Đối chiếu tổng tiền thưởng các đội với quỹ thưởng công bố của giải trong phạm vi dung sai $\le 0.02$ USD (xử lý sai số làm tròn).
   * Không tự ý sửa tiền hay bịa số để ép khớp dữ liệu.
3. **Cờ chất lượng nghiêm ngặt (`strict_quality`):**
   * Có sẵn cờ boolean `strict_quality` (12,540 giải đạt chuẩn tuyệt đối) phục vụ phân tích độ nhạy (sensitivity analysis).
4. **Quy tắc tính KPI Dashboard (Tránh bẫy dữ liệu):**
   * **Không cộng dồn quỹ thưởng** sau khi JOIN giải đấu với kết quả đội (quan hệ 1-N).
   * **Không cộng dồn Peak Viewers** qua nhiều tháng/game.
   * `hours_streamed` là tổng giờ live của category, không phải thời lượng phát sóng của một giải đấu.
5. **Chống rò rỉ dữ liệu khi dự báo (Forecasting & Leakage Prevention):**
   * Biến mục tiêu chính: `target_prize_pool_usd` theo Quý (Quarterly).
   * Phân chia tập dữ liệu: **Train** ($\le$ 2023), **Validation** (2024), **Test** (2025).
   * Mô hình đối chuẩn có sẵn (Baseline): *Rolling One-Step Seasonal Naive ($t-4$)*.

---

##  5. Cấu trúc thư mục dự án

```text
esports-idv-analytics/
├── data/
│   ├── config/              # Cấu hình game (games_config.csv) & scope dự án (project_scope.json)
│   ├── raw/                 # SQLite pipeline (crawl.sqlite3), raw HTML cache, sitemaps
│   └── processed/           # Các phiên bản clean dữ liệu & analysis_release_v1
├── docs/
│   ├── ANALYSIS_HANDOFF_V1.md # Hướng dẫn bàn giao phân tích, KPI dashboard, quy tắc forecast
│   └── DATA_DICTIONARY.md     # Từ điển dữ liệu chi tiết cho mọi trường và trạng thái
├── notebooks/
│   └── eda/
│       └── 01_data_overview_quality.ipynb # Notebook kiểm toán chất lượng đối chiếu manifest
├── reports/
│   ├── Chuong_1_Thu_thap_va_mo_ta_du_lieu.docx # Báo cáo Chương 1 (chuẩn format học thuật)
│   ├── chuong1_build.py                       # Script tự động build file Word báo cáo Chương 1
│   ├── data_quality/                          # Logs kiểm toán chi tiết từng đợt crawl/clean
│   └── figures/                               # Sơ đồ ERD (erd_schema.png), biểu đồ EDA
├── src/
│   ├── crawling/            # Crawler Esports Earnings, SQLite caching, validation
│   └── cleaning/            # Pipeline làm sạch đa cấp, audit, reconcile & release builder
├── tableau/                 # Không gian triển khai Tableau Dashboard
├── demo/                    # Sản phẩm demo & artifacts
├── requirements.txt         # Thư viện phục vụ crawler & xử lý cốt lõi
└── requirements-analysis.txt# Thư viện bổ sung cho EDA, viz & release pipeline (matplotlib, lxml)
```

## Chạy EDA cho analysis release

Tạo môi trường Python, cài thư viện và chạy:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-analysis.txt
python src\eda.py
```

`src/eda.py` tự chọn thư mục `data/processed/analysis_release_v1_*` mới nhất, kiểm tra khóa và đối chiếu tổng theo quý, sau đó tạo:

- `reports/eda_summary.csv`.
- Năm biểu đồ PNG 300 DPI trong `reports/figures/`.
- Các biểu đồ giữ nguyên quý thiếu và ghi rõ giới hạn độ phủ nguồn năm 2025.

Không dùng các bảng processed cũ nằm ngoài analysis release cho EDA này.

## Chạy mô hình dự báo quỹ thưởng theo quý

Sau khi cài hai tệp requirements ở trên, chạy:

```powershell
python src\model.py
```

`src/model.py` so sánh Seasonal Naive `t-4`, Linear Regression và Random Forest theo giao thức rolling one-step. Dữ liệu đến năm 2023 là train, năm 2024 là validation và năm 2025 là test. Mô hình chính được chọn bằng RMSE trên validation, không chọn bằng kết quả test.

Kết quả gồm:

- `reports/model_predictions.csv`: actual, prediction và residual cho từng family–quý.
- `reports/model_metrics.csv`: MAE, RMSE và R² chẩn đoán theo model, split và family.
- `reports/model_feature_importance.csv` và `reports/model_linear_coefficients.csv`.
- `reports/model_quality_sensitivity.csv` và `reports/model_tuning_results.csv`.
- `reports/model_evaluation_notes.md` và bốn biểu đồ PNG 300 DPI trong `reports/figures/`.

Các target test bị thiếu vẫn được giữ là missing và không được tính vào điểm số.

## Tạo storytelling và bảng bàn giao Tableau

Sau khi chạy EDA và mô hình, chạy:

```powershell
python src\storytelling.py
```

Script đối chiếu actual trong dự báo với bảng quý nguồn, phân tích các kỳ sai số lớn và tạo:

- `data/processed/tableau_forecast_predictions.csv`: bảng dài ở grain `game_family + quarter + target_policy + model`.
- `data/processed/tableau_forecast_summary.csv`: KPI theo family, split, policy và model.
- `reports/storytelling_insights.md`: ba câu chuyện dữ liệu, giới hạn và hành động đề xuất.
- `reports/tableau_forecast_handoff.md`: hướng dẫn relationship, filter, measure và kiểm tra Tableau.
- `reports/storytelling_error_analysis.csv` và `reports/storytelling_evidence.csv` để truy ngược số liệu.
- Bốn hình `reports/figures/story_*.png` ở 300 DPI.

Trong Tableau, đặt `target_policy` và `model` thành bộ lọc một lựa chọn. Không join bảng forecast vào placements hoặc country rows vì sẽ làm lặp actual và prediction.

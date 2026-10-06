```text

esports-idv-analytics/

├── data/

│   ├── raw/                  # 3 bảng dữ liệu thô ban đầu

│   ├── processed/            # Dữ liệu sạch xuất cho Tableau \& ML

│   └── dictionary/           # Từ điển dữ liệu \& sơ đồ ERD

├── src/                      # Mã nguồn Python tiền xử lý và mô hình ML

├── tableau/                  # File Tableau Packaged Workbook (.twbx)

├── reports/                  # Bản thảo báo cáo IEEE theo từng chương

└── demo/                     # Kịch bản demo và link video backup

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

## Kiểm tra gói báo cáo và demo

Sau khi chạy ba bước trên, kiểm tra toàn bộ đầu ra Thành viên C:

```powershell
python src\validate_deliverables.py
```

Kết quả kiểm tra được ghi vào:

- `reports/final_validation_results.csv`.
- `reports/final_validation_summary.md`.
- `reports/report_traceability.csv`.

Gói Ngày 4 gồm:

- `reports/chapters/ch5_modeling.md`.
- `reports/chapters/ch6_implementation.md`.
- `reports/chapters/ch7_conclusion.md`.
- `demo/video_script.md`.
- `demo/defense_faq.md`.
- `reports/final_integration_checklist.md`.

Kiểm tra tự động không thay thế việc mở `.twbx` và kiểm tra tương tác Tableau. Các mục cần Thành viên B bàn giao được ghi riêng trong checklist tích hợp.

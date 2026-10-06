# CHƯƠNG 6. TRIỂN KHAI VÀ TÍCH HỢP

## 6.1. Môi trường thực thi

Pipeline được phát triển bằng Python trên Windows và sử dụng đường dẫn tương đối theo thư mục repository. Các thư viện chính gồm pandas, NumPy, Matplotlib và scikit-learn. Toàn bộ EDA, mô hình và storytelling đọc bản `analysis_release_v1_*` mới nhất trong `data/processed`.

Từ thư mục gốc dự án, tạo môi trường và cài thư viện:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-analysis.txt
```

Cách gọi trực tiếp `.venv\Scripts\python.exe` tránh phụ thuộc vào Execution Policy khi kích hoạt môi trường PowerShell.

## 6.2. Luồng xử lý

```text
analysis_release_v1_*
        ↓
src/eda.py
        ↓
EDA, kiểm tra dữ liệu và đặc tả mô hình
        ↓
src/model.py
        ↓
Predictions, metrics và feature importance
        ↓
src/storytelling.py
        ↓
Insight, Tableau exports và hướng dẫn bàn giao
        ↓
src/validate_deliverables.py
        ↓
Kiểm tra tích hợp cuối
```

Thứ tự chạy:

```powershell
.\.venv\Scripts\python.exe src\eda.py
.\.venv\Scripts\python.exe src\model.py
.\.venv\Scripts\python.exe src\storytelling.py
.\.venv\Scripts\python.exe src\validate_deliverables.py
```

## 6.3. EDA

`src/eda.py` thực hiện các kiểm tra khóa, quan hệ cha–con, grain, phạm vi ngày, tổng tiền và số giải. Script tạo `reports/eda_summary.csv`, đặc tả ML, bản thảo Chương 5 và năm hình 300 DPI.

Script không đọc các bảng processed cũ nằm ngoài analysis release. Các quý thiếu được giữ trống. Bảng tournament không được join với placements trước khi cộng quỹ thưởng.

## 6.4. Mô hình

`src/model.py` tạo feature lag và rolling sau `shift(1)`, huấn luyện Seasonal Naive, Linear Regression và Random Forest, chọn Random Forest bằng validation RMSE, rồi đánh giá test. Target nguồn và target strict-quality được chạy riêng.

Các đầu ra chính:

- `reports/model_predictions.csv`.
- `reports/model_metrics.csv`.
- `reports/model_feature_importance.csv`.
- `reports/model_linear_coefficients.csv`.
- `reports/model_quality_sensitivity.csv`.
- `reports/model_tuning_results.csv`.
- `reports/model_evaluation_notes.md`.
- Bốn hình `reports/figures/model_*.png`.

## 6.5. Storytelling và Tableau exports

`src/storytelling.py` đối chiếu actual trong dự báo với bảng quý nguồn, chuyển predictions từ dạng rộng sang dạng dài, tạo bảng KPI và phân tích residual. Script tạo 192 dòng dự báo Tableau và 60 dòng summary.

### 6.5.1. Bảng dự báo

`data/processed/tableau_forecast_predictions.csv` có grain:

```text
game_family + quarter + target_policy + model
```

Trong một model và target policy được chọn, mỗi family–quarter chỉ có một dòng. Các trường chính gồm actual, predicted, residual, absolute error, trạng thái đánh giá và cờ model chính.

### 6.5.2. Bảng KPI

`data/processed/tableau_forecast_summary.csv` có grain:

```text
target_policy + split + game_family + model
```

Bảng gồm family và `Overall`, số kỳ được đánh giá, coverage, tổng actual, tổng predicted, bias, MAE và RMSE. Dòng `Overall` được tính trực tiếp từ tất cả residual; không lấy trung bình RMSE của các family.

## 6.6. Thiết kế nguồn dữ liệu Tableau

Bảng forecast phải được dùng như fact table độc lập. Nếu có dimension game–quarter, tạo relationship many-to-one bằng `game_family + quarter`. Không physical join forecast với tournaments, placements hoặc country rows vì quan hệ một–nhiều sẽ lặp actual và prediction.

Country map tiếp tục dùng nguồn country đã đối chiếu. Các view phối hợp qua filter `game_family` hoặc dimension dùng chung, không join forecast vào country detail.

Bộ lọc mặc định:

- `target_policy = source`, single-select.
- `model = random_forest`, single-select.
- `split = validation` hoặc `test`.
- `game_family`, có thể multi-select.

Nếu người dùng chọn nhiều model, actual sẽ lặp một lần cho mỗi model. KPI tổng phải giữ model single-select hoặc dùng `MIN(actual_prize_pool_usd)` tại grain family–quarter–policy.

## 6.7. Các sheet dự báo đề xuất

### 6.7.1. Actual vs Predicted Trend

- Columns: `period_start` dạng continuous quarter.
- Rows: actual và predicted.
- Color: Measure Names.
- Small multiple hoặc Detail: `game_family`.
- Giữ các điểm prediction-only và để actual là null.

### 6.7.2. Actual vs Predicted Scatter

- Columns: `actual_prize_pool_usd`.
- Rows: `predicted_prize_pool_usd`.
- Color: `game_family`.
- Filter: `evaluation_available = True`.
- Thêm đường tham chiếu `y = x`.

### 6.7.3. Residual Review

- Columns: `period_start`.
- Rows: `residual_usd`.
- Color: `error_direction`.
- Thêm đường tham chiếu tại 0.
- Tooltip gồm family, quarter, actual, predicted, residual, policy, model và evaluation status.

### 6.7.4. KPI Cards

KPI gồm MAE, RMSE, coverage và số kỳ được đánh giá. KPI sử dụng `tableau_forecast_summary.csv`, lọc đúng một target policy, split, family và model.

## 6.8. Xử lý dữ liệu thiếu trên dashboard

Với source target test, có 16 family–quarter nhưng chỉ 13 kỳ có actual. League of Legends 2025Q4, Valorant 2025Q2 và Valorant 2025Q4 phải hiển thị `Prediction only — target missing`. Không dùng `ZN`, `IFNULL(...,0)` hoặc thay null bằng 0 cho actual và residual.

## 6.9. Kiểm tra tích hợp

`src/validate_deliverables.py` kiểm tra:

- Release và các file đầu vào bắt buộc.
- Khóa predictions và Tableau exports.
- Đối chiếu actual với bảng quý nguồn.
- Đối chiếu MAE/RMSE giữa bảng model và bảng Tableau summary.
- Ba target test thiếu vẫn là null.
- Dự báo không âm.
- Tất cả hình EDA, model và storytelling có DPI gần 300.
- Bộ chương báo cáo, demo, FAQ và checklist tồn tại.

Kết quả được ghi vào `reports/final_validation_results.csv` và `reports/final_validation_summary.md`.

## 6.10. Trạng thái tích hợp Tableau

Phần Python và hai bảng bàn giao Tableau đã hoàn thành. Các mục sau cần Thành viên B cung cấp trước khi khóa bản báo cáo cuối:

- File `.twbx` hoặc link Tableau Public.
- Ảnh chụp dashboard cuối.
- Tên worksheet, filter, parameter và action thực tế.
- Xác nhận Actual vs Predicted có 16 dòng test và 13 dòng được đánh giá khi lọc `source + random_forest`.
- Xác nhận actual không bị cộng lặp khi đổi model hoặc tương tác với country map.

Không tự điền tên sheet, ảnh hoặc link khi chưa nhận bàn giao. Sau khi nhận, nhóm cập nhật phần minh họa và thao tác demo mà không thay đổi định nghĩa dữ liệu.

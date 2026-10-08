# Bàn giao dự báo bốn quý cho thành viên B

## File cần nhận

Ba file CSV cùng một lần chạy, nằm trong `data/processed/`:

| File | Nội dung | Khóa duy nhất |
|---|---|---|
| `tableau_forecast_timeline.csv` | Lịch sử + dự báo, dùng vẽ biểu đồ chính | game_family + quarter + target_policy + model |
| `tableau_future_forecasts.csv` | Chỉ 4 quý sau mốc dữ liệu, dùng KPI/tooltip | game_family + quarter + target_policy + model |
| `tableau_backtest_metrics.csv` | Sai số kiểm tra lịch sử và độ phủ khoảng dự báo | evaluation_phase + game_family + model + horizon_quarters |

Nhận kèm tài liệu này và `reports/future_forecast_notes.md` để biết model được chọn,
mốc dữ liệu và kết quả thật của lần chạy. Không cần PNG để dựng biểu đồ Tableau.
Hai file `tableau_forecast_predictions.csv` và `tableau_forecast_summary.csv` cũ
vẫn dành cho trang kiểm định rolling one-step 2024–2025. Không union chúng với file mới.

File tương lai có **48 dòng = 4 game × 4 quý × 3 mô hình**, chỉ có policy `source`.
Khi chọn một model còn 16 dòng; chọn thêm một game còn 4 dòng.
`strict_quality` vẫn nằm trong phần kiểm định cũ, chưa dùng ở trang tương lai.

## Cách cập nhật dữ liệu

Tại thư mục gốc dự án, sau khi A tạo release mới:

```powershell
.\.venv\Scripts\python.exe src\forecast_future.py
```

Script tự chọn release mới nhất theo tên `analysis_release_v1_*`, tự xác định quý cuối
đã kết thúc theo lịch có actual của ít nhất một game và tạo 4 quý sau đó. Quý đang diễn ra
bị loại khỏi lịch sử; các quý placeholder toàn null không đẩy mốc dự báo về sau.
Nếu biết dữ liệu quý cuối chưa thu thập xong, chọn mốc cũ hơn:

```powershell
.\.venv\Scripts\python.exe src\forecast_future.py --as-of 2025Q3
```

Có thể chỉ định thư mục bằng `--release data/processed/analysis_release_v1_...`.
Script không crawl và không tự chạy theo lịch. Số liệu khác null cũng không chứng minh
nguồn đã đầy đủ. Mốc mặc định của release hiện tại là 2025Q4, kết quả 2026Q1–2026Q4;
đó là tương lai so với dữ liệu, không phải cập nhật theo ngày hôm nay.

B thay ba CSV bằng cùng một lần chạy rồi Refresh trong Tableau; với Extract cần refresh
extract, với workbook đóng gói cần lưu lại bản đóng gói để mang dữ liệu mới theo.
`generated_at_utc` và `source_release` giúp kiểm tra các file có cùng phiên bản.

## Trang dự báo cần bổ sung

### 1. Biểu đồ lịch sử và dự báo theo quý

- Nguồn độc lập: `tableau_forecast_timeline.csv`. Không physical join với tournaments,
  placements, country hoặc bảng forecast khác.
- `period_start`: Date, đưa lên Columns dạng quý liên tục.
- Chọn **một game** và **một model**. Có thể làm small multiples khi muốn nhiều game.
- Rows: Measure Values gồm `actual_prize_pool_usd` và `predicted_prize_pool_usd`.
- Giữ null thành khoảng trống, không dùng ZN() và không nối qua quý lịch sử bị thiếu.
- Dùng màu khác nhau cho actual và forecast, thêm đường phân cách tại đầu quý sau
  `forecast_origin`. Nếu phiên bản Tableau hỗ trợ thì dùng nét đứt cho forecast.
- Hiển thị `forecast_origin`, `last_observed_quarter`, `source_release` trong tooltip/caption.
- Không bật thêm tính năng Forecast tự động của Tableau lên đường dự báo Python.

### 2. Bộ lọc và KPI

- `model`: Single Value; có Seasonal Naive, Linear Regression, Random Forest.
  Đọc `future_forecast_notes.md` hoặc `is_primary_model` để đặt mặc định, không cố định Random Forest.
- Nếu muốn cho người xem đổi model, không khóa `is_primary_model=True` cùng lúc với bộ chọn model.
- Parameter integer `Số quý xem` = 1, 2 hoặc 4, mặc định 4.
- Với timeline, dùng calculated field:

```text
[record_type] <> "forecast" OR [horizon_quarters] <= [Số quý xem]
```

- Với nguồn chỉ chứa tương lai, dùng `[horizon_quarters] <= [Số quý xem]`.
- KPI quý kế tiếp: lọc `horizon_quarters=1`, đúng một model, SUM(predicted_prize_pool_usd).
- Mọi KPI tiền phải lọc một model vì lịch sử/forecast lặp lại theo model.
- Nếu dùng hai nguồn cho biểu đồ và KPI, thiết lập dashboard filter/parameter để game
  và model tác động tới cả hai; kiểm tra bằng cách đổi game/model rồi đối chiếu CSV.

### 3. Dải dự báo tham khảo

- Dùng `lower_80_usd`, `upper_80_usd`. Không gắn nhãn "chắc chắn 80%".
- Có thể tạo worksheet Gantt với điểm bắt đầu `lower_80_usd`, Size là
  `[upper_80_usd] - [lower_80_usd]`, quý trên Columns; đặt bên cạnh đường dự báo,
  hoặc overlay dual-axis đồng bộ trục nếu dựng dải trên cùng sheet.
- Chỉ hiển thị khi `record_type=forecast` và `interval_status=exploratory_80pct_not_guaranteed`.
- Giữ một game + một model khi xem dải. **Không cộng cận các game hoặc các quý**
  để tạo khoảng cho tổng tiền thưởng năm; các sai số có thể phụ thuộc nhau.
- Thiếu mẫu hiệu chỉnh thì cận để null, ghi "Chưa đủ mẫu ước lượng khoảng".
- Nhãn: "Dải tham khảo từ sai số lịch sử; chưa bảo đảm độ phủ 80%".

### 4. Sheet đánh giá mô hình

- Nguồn độc lập: `tableau_backtest_metrics.csv`.
- `evaluation_phase=selection`: dùng chọn model từ nhiều mốc lịch sử.
- `evaluation_phase=holdout`: bốn quý cuối giữ lại để kiểm tra sau khi chọn model.
- `horizon_quarters=1..4`: sai số theo số quý dự báo trước.
- `horizon_quarters=0`: tổng hợp cả bốn khoảng dự báo; không cộng dòng này với 1..4.
- `game_family=Overall`: tổng hợp bốn game; không cộng với dòng từng game.
- Hiển thị MAE, RMSE, `n_evaluated`, `evaluation_coverage_pct` và `interval_coverage_pct`.
- Không SUM/AVG các RMSE để tạo Overall. Dùng đúng dòng Overall được cung cấp.
- Không tính sai số cho dự báo tương lai: actual của chúng chưa có.

## Các cột cần hiểu

| Cột | Ý nghĩa |
|---|---|
| forecast_origin | Quý cuối của lịch sử dùng cho lượt dự báo |
| horizon_quarters | Dự báo trước bao nhiêu quý, từ 1 đến 4; 0 trong metrics là tổng hợp |
| last_observed_quarter | Quý cuối có actual của riêng game; có thể cũ hơn forecast_origin |
| actual_prize_pool_usd | Thực tế; giữ trống ở tương lai hoặc quý lịch sử thiếu |
| predicted_prize_pool_usd | Điểm dự báo USD, đã chặn âm về 0 |
| record_type | historical, historical_missing hoặc forecast (trong timeline) |
| lower_80_usd / upper_80_usd | Cận của dải sai số tham khảo |
| interval_calibration_n | Số sai số dùng ước lượng dải; tối thiểu 8 mới có cận |
| missing_recent_quarters | Số quý thiếu actual trong 4 quý trước mốc dự báo |
| feature_missing_count | Số đặc trưng thiếu trước khi pipeline xử lý |
| seasonal_fallback_used | Seasonal Naive thiếu cùng quý năm trước nên dùng trung vị lịch sử trước đó |
| uses_recursive_predictions | Có dùng dự đoán bước trước làm lịch sử cho bước sau |
| is_primary_model | Model được chọn bằng RMSE selection, không phải holdout |
| evaluation_available | Tương lai luôn False |
| source_coverage_verified | Manifest đã xác minh đầy đủ nguồn hay chưa |
| data_warning | Cảnh báo nguồn chưa xác minh, thiếu quý gần nhất hoặc fallback |

## Quy trình mô hình và giới hạn

So sánh ba model trên tối đa 8 mốc (tối thiểu 4), mỗi mốc học từ lịch sử trước đó rồi
dự báo nối tiếp bốn quý. Không đưa actual của bất kỳ quý nào sau mốc vào đầu vào.
Chọn model theo RMSE gộp các dự báo selection, dùng MAE khi hòa; luôn giữ Linear Regression
để đáp ứng yêu cầu môn học. Tham số Random Forest cố định trước kiểm tra, không lấy tham số
đã tối ưu bằng năm nằm sau mốc kiểm tra.

Bốn quý cuối được giữ làm holdout; mọi target dùng selection đều trước holdout.
Sau đánh giá mới học lại bằng toàn bộ actual hợp lệ để dự báo bốn quý tiếp theo.
Quý thiếu không được coi là 0 hay nhãn huấn luyện. Median imputation chỉ áp dụng cho
đặc trưng của Linear/Forest, fit bằng tập học. Seasonal Naive có fallback gắn cờ.

Dải tham khảo lấy phân vị sai số tuyệt đối theo game/model/horizon từ selection,
với cận dưới chặn tại 0 và bán kính không giảm theo horizon. Các cửa sổ chồng lấn,
ít mẫu và cùng tập dùng chọn model nên không cam kết độ phủ 80%. File metrics có
độ phủ thực nghiệm trên holdout; không đưa số đẹp hơn bằng cách hiệu chỉnh lại trên holdout.

Trang giả lập thanh kéo của B vẫn phải ghi "kịch bản theo giả định". Không coi giá trị
nhân hệ số thanh kéo là kết quả model hoặc áp dụng nguyên dải dự báo cho kịch bản đã chỉnh.

## Kiểm tra trước bàn giao

1. Đúng một model: 16 dòng tương lai; thêm một game: 4 dòng.
2. Quý dự báo đầu tiên ngay sau forecast_origin, bốn quý liên tiếp.
3. Actual tương lai trống; actual lịch sử thiếu vẫn trống.
4. LoL/Valorant có thể có last_observed_quarter trước origin; cảnh báo phải nhìn thấy.
5. Đổi model không làm actual tăng ba lần.
6. Sheet holdout có đủ n_evaluated và không trộn selection hay Overall với từng game.
7. CSV mới không thay đổi nguồn dữ liệu bản đồ hoặc bảng chi tiết giải đấu.

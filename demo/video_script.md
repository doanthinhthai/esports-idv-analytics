# KỊCH BẢN DEMO 4 PHÚT

## Mục tiêu

Trình bày ngắn gọn vấn đề, dữ liệu, dashboard, mô hình, insight và giới hạn trong 3–5 phút. Kịch bản dùng vai trò A, B và C; nhóm thay bằng tên thành viên khi quay.

## Chuẩn bị trước khi quay

- Chạy `src/validate_deliverables.py` và xác nhận tất cả automated checks PASS.
- Mở dashboard Tableau ở trạng thái mặc định.
- Đặt `target_policy = source`, `model = random_forest`, `split = test`.
- Chuẩn bị tab hoặc ảnh backup cho Overview, Trend, Country Map và Forecast.
- Tắt thông báo hệ điều hành và đóng các cửa sổ không liên quan.
- Kiểm tra âm thanh và đặt đồng hồ giới hạn 4 phút 20 giây.

Tên sheet và thao tác dưới đây là chức năng yêu cầu. Sau khi Thành viên B bàn giao workbook, đối chiếu với tên sheet thực tế trước khi quay; không tự ghi tên không tồn tại.

## 0:00–0:45 — Thành viên A: vấn đề và dữ liệu

**Màn hình:** Overview hoặc trang giới thiệu dự án.

**Lời thoại:**

> Nhóm phân tích dữ liệu E-sports của bốn nhóm game: Counter-Strike, Dota 2, League of Legends và Valorant. Mục tiêu là theo dõi quỹ thưởng, mức độ chú ý trên Twitch, phân bố tiền thưởng theo quốc gia tuyển thủ và dự báo quỹ thưởng theo quý. Analysis release gồm 14.082 giải đấu, 52.551 placement và 369 quan sát game–tháng trên Twitch. Release đã làm sạch theo policy nhưng chưa xác minh đầy đủ độ phủ nguồn, đặc biệt năm 2025.

**Thao tác:** Di chuột qua KPI tổng số giải, tổng quỹ thưởng và phạm vi thời gian. Không drill-down vào placement trong phần này.

## 0:45–2:10 — Thành viên B: dashboard và tương tác

### 0:45–1:20 — Xu hướng

**Màn hình:** Prize Trend.

**Lời thoại:**

> Dota 2 có tổng quỹ thưởng quan sát lớn nhất, khoảng 380,57 triệu USD, và có các quý đột biến mạnh. Counter-Strike đạt khoảng 208,57 triệu USD. Năm 2025 được đánh dấu riêng vì số liệu nguồn chưa được xác minh đầy đủ; mức giảm quan sát không được hiểu ngay là thị trường suy giảm.

**Thao tác:** Lọc lần lượt Dota 2 và Counter-Strike; hover quý 2021Q4 của Dota 2.

### 1:20–1:45 — Twitch

**Màn hình:** Twitch hoặc Audience.

**Lời thoại:**

> League of Legends có trung vị khoảng 99 triệu giờ xem Twitch mỗi tháng. Dota 2 có tương quan mô tả giữa giờ xem và quỹ thưởng cao hơn, khoảng 0,698, trong khi các family khác gần 0. Đây không phải bằng chứng quỹ thưởng làm tăng người xem.

**Thao tác:** Chuyển filter game family và hiển thị tooltip giờ xem.

### 1:45–2:10 — Bản đồ

**Màn hình:** Player Country Map.

**Lời thoại:**

> Bản đồ thể hiện quốc gia tuyển thủ trong dữ liệu tiền thưởng đã đối chiếu, không phải quốc gia khán giả. Độ phủ tiền thưởng quốc gia đạt khoảng 97,67% tổng nguồn và phải được hiển thị cùng bản đồ.

**Thao tác:** Lọc một family và hover quốc gia đứng đầu. Không gọi đây là audience geography.

## 2:10–3:40 — Thành viên C: mô hình và insight

### 2:10–2:55 — Kết quả mô hình

**Màn hình:** Forecast Performance hoặc Actual vs Predicted.

**Lời thoại:**

> Nhóm so sánh Seasonal Naive, Linear Regression và Random Forest theo temporal split. Dữ liệu đến năm 2023 dùng để train, năm 2024 là validation và năm 2025 là test. Random Forest có validation RMSE thấp nhất, khoảng 1,98 triệu USD, nên được chọn trước khi xem test. Trên test, Seasonal Naive có RMSE 2,41 triệu USD, thấp hơn Random Forest 2,51 triệu USD. Vì vậy mô hình phức tạp chưa cải thiện ổn định ngoài mẫu.

**Thao tác:** Giữ target policy là source. Chuyển model giữa Seasonal Naive và Random Forest. Hiển thị coverage 13/16 cho test.

### 2:55–3:20 — Missing và residual

**Màn hình:** Residual Review.

**Lời thoại:**

> Ba target test bị thiếu được giữ là null và không tính vào metrics. Sai số lớn tập trung ở Dota 2 và Q4. Dota 2 chiếm khoảng 42,3% tổng sai số tuyệt đối, còn Q4 chiếm khoảng 36,6%. Residual lớn có thể phản ánh cả biến động thị trường và độ phủ nguồn.

**Thao tác:** Hover Dota 2 2024Q3, Counter-Strike 2025Q4 và Dota 2 2025Q4.

### 3:20–3:40 — Hàm ý

**Lời thoại:**

> Kết quả được dùng như tín hiệu ưu tiên tài trợ và phân bổ thử nghiệm. Nhóm không tuyên bố ROI vì dữ liệu chưa có doanh thu, chi phí tài trợ hoặc lợi nhuận. Dự báo phải được xem cùng baseline, coverage và cảnh báo dữ liệu.

## 3:40–4:10 — Kết luận chung

**Màn hình:** Overview hoặc kết luận.

**Lời thoại — Thành viên A:**

> Đóng góp chính của đề tài là một pipeline tái lập từ dữ liệu, EDA và mô hình đến Tableau, đồng thời kiểm soát grain, leakage và missing. Hướng phát triển tiếp theo là xác minh nguồn 2025, mở rộng dữ liệu audience và xây dựng khoảng dự báo thay vì chỉ dùng một giá trị điểm.

## Phương án backup

### Tableau không mở được

Trình chiếu các ảnh theo thứ tự:

1. `reports/figures/eda_01_quarterly_prize.png`.
2. `reports/figures/eda_02_twitch_hours.png`.
3. `reports/figures/story_03_country_distribution.png`.
4. `reports/figures/model_performance_comparison.png`.
5. `reports/figures/story_04_forecast_error_concentration.png`.

### Filter hoặc action lỗi

Không sửa workbook trong lúc quay. Chuyển sang ảnh backup và tiếp tục lời thoại. Sau buổi demo mới ghi lỗi vào checklist tích hợp.

### Mạng lỗi

Sử dụng file `.twbx` và ảnh PNG cục bộ. Không phụ thuộc Tableau Public trong bản demo chính.

### Thiếu thời gian

Cắt phần drill-down Twitch và rút phần bản đồ còn một câu. Không cắt kết quả mô hình, missing policy hoặc giới hạn ROI.

## Kiểm tra sau khi nhận dashboard từ Thành viên B

- Đổi tên chức năng trong kịch bản sang đúng tên worksheet thực tế.
- Chụp ảnh từng trạng thái filter cần dùng.
- Thử toàn bộ thao tác trong một lần dưới 4 phút 20 giây.
- Xác nhận không có KPI bị nhân khi chuyển model hoặc chọn country.
- Lưu `.twbx` và ảnh backup cùng phiên bản với video.

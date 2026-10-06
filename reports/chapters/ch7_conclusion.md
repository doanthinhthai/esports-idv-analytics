# CHƯƠNG 7. KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

## 7.1. Kết quả đạt được

Đề tài xây dựng được một pipeline tái lập từ analysis release đến EDA, mô hình dự báo, storytelling và bảng dữ liệu bàn giao cho Tableau. Pipeline xử lý bốn nhóm game gồm Counter-Strike, Dota 2, League of Legends và Valorant, đồng thời giữ rõ grain của từng bảng để tránh cộng trùng dữ liệu.

Các đóng góp chính gồm:

- Kiểm tra khóa, quan hệ và đối chiếu tổng giữa tournament và bảng quý.
- Phân tích xu hướng quỹ thưởng, Twitch, số giải, chất lượng và độ phủ quốc gia.
- Xây dựng Seasonal Naive, Linear Regression và Random Forest theo temporal split.
- Ngăn leakage bằng lag, rolling sau `shift(1)` và loại feature cùng quý.
- Đánh giá bằng MAE, RMSE, số kỳ quan sát và coverage.
- Phân tích target strict-quality như kiểm tra độ nhạy riêng.
- Xuất bảng dự báo và summary đúng grain cho Tableau.
- Xây dựng ba câu chuyện dữ liệu kèm giới hạn và hành động đề xuất.
- Chuẩn bị tài liệu triển khai, demo và FAQ bảo vệ.

## 7.2. Kết luận phân tích

Dota 2 có tổng quỹ thưởng quan sát lớn nhất, khoảng 380,57 triệu USD, nhưng đồng thời có các quý đột biến và mức sai số dự báo cao. Counter-Strike có tổng quỹ thưởng khoảng 208,57 triệu USD và mức mùa vụ ít cực đoan hơn. League of Legends có trung vị giờ xem Twitch cao nhất, khoảng 99,0 triệu giờ mỗi tháng, dù tương quan giữa Twitch và quỹ thưởng gần 0.

Random Forest đạt validation RMSE thấp nhất, khoảng 1,98 triệu USD, nên được chọn làm mô hình chính theo quy tắc đã xác định trước. Trên test, Seasonal Naive có RMSE khoảng 2,41 triệu USD, thấp hơn Random Forest khoảng 2,51 triệu USD. Kết quả cho thấy Random Forest chưa cải thiện ổn định so với baseline mùa vụ, đặc biệt khi quỹ thưởng giảm đột ngột.

Sai số tập trung ở Dota 2 và Q4. Điều này phù hợp với giới hạn của feature trễ khi chuỗi thay đổi chế độ. Tuy nhiên, do độ phủ nguồn năm 2025 chưa được xác minh đầy đủ, không thể quy toàn bộ residual cho hành vi thị trường.

Phân tích quốc gia cho thấy các nhóm game có cấu trúc quốc gia tuyển thủ khác nhau. Bảng quốc gia đối chiếu khoảng 97,67% tổng quỹ thưởng nguồn. Kết quả này hỗ trợ nội dung gắn với tuyển thủ hoặc lựa chọn thị trường nghiên cứu thêm, nhưng không đại diện cho quốc gia khán giả.

## 7.3. Giá trị ứng dụng

Dashboard và mô hình hỗ trợ ba nhóm quyết định:

1. Theo dõi quy mô và mùa vụ của quỹ thưởng theo game.
2. So sánh tín hiệu chú ý trên Twitch với hoạt động quỹ thưởng.
3. Sàng lọc game hoặc quốc gia tuyển thủ cho phân bổ tài trợ thử nghiệm.

Kết quả phù hợp để tạo `tín hiệu ưu tiên tài trợ`, cảnh báo biến động và danh sách thị trường cần xác minh. Kết quả không đủ để tính ROI vì dữ liệu không chứa doanh thu, chi phí tài trợ hoặc lợi nhuận.

## 7.4. Hạn chế

- Analysis release đã làm sạch theo policy nhưng chưa chứng nhận đầy đủ độ phủ nguồn.
- Dữ liệu 2025 thiếu target của League of Legends và Valorant; ngay cả Counter-Strike và Dota 2 cũng chưa xác minh source coverage.
- Test chỉ có một năm và số quan sát theo family nhỏ.
- Quỹ thưởng là USD danh nghĩa, chưa điều chỉnh lạm phát.
- Seasonal Naive và các mô hình học máy dùng giao thức rolling one-step; kết quả không tương đương dự báo nhiều quý từ đầu năm.
- Twitch chỉ là category chính trên Twitch, kết thúc tháng 9/2024 và không gồm YouTube.
- Country data là quốc gia tuyển thủ trong phần đã đối chiếu.
- Correlation và feature importance không chứng minh quan hệ nhân quả.
- Random Forest có thể học chậm trước các thay đổi chế độ hoặc quý có sự kiện đặc biệt.

## 7.5. Hướng phát triển

### 7.5.1. Cải thiện nguồn dữ liệu

- Xác minh và bổ sung giải đấu năm 2025 trước khi khóa test cuối.
- Thêm cờ source completeness theo family và quý.
- Lưu thời điểm thu thập để phân biệt kỳ chưa hoàn thành với kỳ thực sự thấp.
- Mở rộng dữ liệu YouTube và người xem giải đấu nếu có nguồn đáng tin cậy.

### 7.5.2. Cải thiện mô hình

- Đánh giá walk-forward trên nhiều năm thay vì một validation year.
- Thử mô hình robust với outlier và biến đổi `log1p` của target.
- Thêm biến lịch sự kiện chỉ khi có thể biết tại forecast origin.
- Xây dựng prediction interval hoặc quantile model thay cho một point forecast.
- Kiểm tra regime-change và mô hình riêng cho Dota 2.
- So sánh mô hình pooled với mô hình riêng theo family khi có thêm dữ liệu.

### 7.5.3. Cải thiện đánh giá kinh doanh

- Thu thập chi phí tài trợ, doanh thu, conversion và brand-lift để đánh giá hiệu quả.
- Phân biệt audience geography với player country.
- Theo dõi hiệu suất chiến dịch theo game, khu vực và giai đoạn giải đấu.
- Chỉ tính ROI khi có định nghĩa doanh thu và chi phí thống nhất.

### 7.5.4. Cải thiện dashboard

- Hiển thị source-coverage status cạnh KPI.
- Cho phép đổi giữa source target và strict-quality sensitivity.
- Thêm tooltip giải thích prediction-only và rolling one-step.
- Cảnh báo khi người dùng chọn nhiều model làm actual bị lặp.
- Tách player-country map khỏi audience geography.

## 7.6. Kết luận cuối

Đề tài chứng minh một quy trình phân tích có thể tái lập và kiểm soát leakage quan trọng hơn việc chỉ tối ưu một chỉ số mô hình. Random Forest cung cấp tín hiệu hữu ích trên validation, nhưng Seasonal Naive vẫn là đối thủ mạnh trên test. Vì vậy dự báo nên được dùng cùng baseline, coverage và residual review.

Giá trị chính của hệ thống nằm ở việc kết nối dữ liệu, mô hình và trực quan hóa trong một luồng có thể kiểm tra. Các giới hạn về nguồn, target thiếu và phạm vi Twitch được giữ rõ trong báo cáo và dashboard để tránh diễn giải vượt quá bằng chứng.

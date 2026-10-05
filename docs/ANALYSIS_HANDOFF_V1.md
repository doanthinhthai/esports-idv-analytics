# Quy tắc bàn giao dữ liệu và EDA V1

## Trạng thái và phạm vi

Bộ `analysis_release_v1_*` là dữ liệu làm sạch theo chính sách sử dụng, không phải chứng nhận mọi số liệu nguồn đều đúng hoặc mọi giải đã được thu thập. Raw, SQLite và các bản clean cũ không thay đổi. `manifest.json` ghi phiên bản, kiểm tra, hash và độ phủ quốc gia.

- Earnings: giải bắt đầu từ 2012-01-01 đến 2025-12-31; USD danh nghĩa, chưa điều chỉnh lạm phát/tỷ giá lịch sử.
- Twitch: category chính theo tháng, 2016-01 đến 2024-09; Valorant từ 2020-04. Bao gồm stream giải đấu lẫn stream thông thường. Không có khán giả YouTube, năm 2025 hoặc quốc gia khán giả.
- Counter-Strike là family gồm CS:GO và CS2. Category Twitch `Counter-Strike` không chứng minh một phiên bản riêng. Các category CS2/Limited Test bổ sung được giữ riêng, không cộng peak/avg vào chuỗi chính.
- Scope khác nhau giữa các bảng là chủ ý. Không cắt Earnings xuống 2016–2024 cho mọi bài toán chỉ vì Twitch có khoảng thời gian đó.

## Bảng, khóa và quan hệ

| File | Một dòng biểu diễn | Khóa | Sử dụng |
|---|---|---|---|
| tournaments.csv | Một giải | tournament_id | Số giải, tổng quỹ thưởng nguồn |
| placements.csv | Một kết quả đội/giải | placement_id | Thứ hạng, khoản thưởng đội được chấp nhận |
| twitch_monthly.csv | Category chính của family trong tháng | game_family + month_start | Xu hướng người xem game |
| game_monthly_panel.csv | Family–tháng trong phạm vi Twitch | game_family + month_start | Phân tích mô tả hai nguồn |
| country_prizes.csv | Quốc gia tuyển thủ trong một giải có bảng quốc gia đối chiếu đạt | tournament_id + country_code | Bản đồ tiền thưởng quốc gia |
| country_year.csv | Family–năm–quốc gia | game_family + year + country_code | Tỷ trọng quốc gia trong tập đã đối chiếu |
| country_coverage.csv | Family–năm | game_family + year | Độ phủ bản đồ; phải hiển thị kèm |
| forecast_prize_quarterly.csv | Family–quý trên lưới thời gian | game_family + quarter | Mục tiêu dự báo tiền thưởng |
| forecast_twitch_monthly.csv | Family–tháng | game_family + month_start | Dự báo giờ xem/avg viewers nếu nhóm chọn |

Giải → placements/quốc gia là 1–n. Không cộng `prize_pool_usd` sau khi nối với placements/quốc gia: tiền của giải sẽ bị lặp. Tổng hợp từng bảng trước, hoặc dùng quan hệ logic riêng trong dashboard. Không nối quốc gia với người xem để suy diễn quốc gia khán giả.

## Chính sách chất lượng

1. **Metadata nguồn:** tất cả tournaments trong bản clean có ngày hợp lệ, family hợp lệ và quỹ thưởng không âm; dùng tổng quỹ thưởng công bố để mô tả hoạt động giải. Quỹ thưởng này vẫn có thể sai tại nguồn.
2. **Độ nhạy nghiêm ngặt:** `strict_quality=True` loại giải có quality_note hoặc placements chưa đối chiếu đạt. Bảng dự báo có cả mục tiêu nguồn và mục tiêu nghiêm ngặt; không lẫn hai chính sách trong cùng thí nghiệm. Chính sách nghiêm ngặt có thể thiên lệch về các giải dễ thu thập, không mặc nhiên chính xác hơn toàn lịch sử.
3. Placements đã được đối chiếu tổng tiền trong phạm vi 0,02 USD, **không xác minh từng đội**. ID đội không rõ vẫn null; không ghép đội xuyên giải bằng ID chưa rõ hoặc chỉ dựa vào tên. `strict_quality` giúp lọc các giải có identity flag.
4. Quốc gia chỉ giữ bảng có tổng lệch quỹ thưởng tối đa 0,02 USD, cấu trúc hợp lệ và không trùng code. Tổng khớp không chứng minh từng khoản quốc gia đúng. `source_player_count` là số người ghi trong từng bảng giải; cộng qua giải là lượt tham gia, không phải tuyển thủ duy nhất.
5. Thiếu ngày, trang nguồn trống, allocation chưa duyệt được giữ trong quarantine. Không đảo ngày, bịa tên hoặc chia lại tiền để làm tổng khớp. Quarantine có thể trùng giải vẫn có metadata hợp lệ.
6. IQR chỉ là cờ mô tả tính trên toàn chuỗi, không xóa tháng bùng nổ. Không dùng cờ này để tiền xử lý mô hình trước khi chia train/test.
7. Không có giải quan sát trong kỳ ≠ không có giải diễn ra. Quỹ thưởng kỳ không có quan sát để null, không tự điền 0. Trước khi game xuất hiện cũng không tự coi là chuỗi 0.

## KPI dashboard

- Tổng quỹ thưởng: cộng `pool_cents / 100` từ tournaments, không cộng qua bảng kết quả đội.
- Số giải: distinct tournament_id.
- Giờ xem: cộng hours_watched theo các tháng/category được chọn. Ghi rõ Twitch, category chính.
- Avg viewers: hiển thị theo tháng. Nếu gộp nhiều tháng, cân nhắc trung bình có trọng số giờ lịch, không SUM. Không tự cộng avg qua category.
- Peak viewers: peak tháng/category; không SUM nhiều tháng. MAX là "peak tháng lớn nhất", không phải tổng người xem duy nhất.
- `hours_streamed` là tổng giờ phát của các kênh trong category; không phải airtime của một giải. `streamers`/`source_player_count` cộng qua tháng/giải không phải số người duy nhất.
- Tỷ trọng Twitch: giờ xem game chia giờ xem toàn Twitch cùng tháng. Với nhiều tháng, tỷ lệ tổng tử số/tổng mẫu số duy nhất theo tháng, không trung bình giản đơn và không cộng mẫu số lặp qua game.
- Tỷ trọng quốc gia: phần trăm tiền thưởng trong **tập bảng quốc gia đã đối chiếu**, kèm country_money_coverage_pct. Không gọi đây là tỷ trọng toàn bộ thị trường khi độ phủ chưa đủ.
- Không có ROI, prize_per_viewer từng giải, hoặc bản đồ quốc gia khán giả trong bộ này.
- Bản đồ quốc gia không tự đồng nghĩa bản đồ khu vực. Nếu nhóm muốn châu lục/khu vực thi đấu, cần bảng ánh xạ được duyệt, ghi phiên bản và xử lý ngoại lệ; không suy từ location_raw của giải.

## Dự báo và chống rò rỉ

Mục tiêu chính theo scope: `target_prize_pool_usd` theo family–quý, phân tiền vào quý bắt đầu giải. Không chia đều tiền qua ngày diễn ra.

- Earnings: train 2012–2023; validation 2024; test 2025. Chọn điểm cắt theo độ dài lịch sử, không theo điểm test; giúp Valorant có thêm dữ liệu train. Một số game có lịch sử ngắn/không quan sát; giữ lưới thời gian, chỉ bắt đầu tại kỳ có dữ liệu và kiểm tra khoảng trống. Không drop kỳ thiếu rồi coi các kỳ còn lại liền nhau.
- Twitch: train đến 2022-12; validation 2023; test 2024-01 đến 2024-09 (năm chưa đầy đủ). Valorant chỉ từ 2020-04.
- Baseline có sẵn: seasonal naive quý t-4, đánh giá rolling one-step. Với kỳ test về sau, được dùng giá trị **đã quan sát trước kỳ đó**, không phải biết toàn test từ đầu. Không dùng điểm này để so sánh với mô hình dự báo cả 12 quý một lần nếu chưa thống nhất giao thức.
- Chọn mô hình, biến, imputation, scaler, ngưỡng ngoại lệ trên train/validation; chỉ đánh giá test cuối cùng. EDA toàn lịch sử là mô tả và phải được phân biệt với bước chọn mô hình.
- Không dùng viewers của quý đang dự báo, tiền placements cùng quý hoặc số giải thực tế tương lai làm predictor nếu lúc dự báo chưa biết. Dùng lag hoặc biến đã biết trước, ghi rõ forecast origin/horizon.
- MAE, RMSE và seasonal-naive là chuẩn so sánh; không hứa R² cao. Tránh MAPE khi target bằng 0 hoặc thiếu.
- Đối chiếu kết quả mục tiêu nguồn và mục tiêu nghiêm ngặt; khác biệt có thể phản ánh độ phủ, không chỉ năng lực mô hình.
- Phân tích tương quan không chứng minh tiền thưởng gây tăng người xem; cả hai có thể cùng mùa giải/xu hướng thời gian.

## EDA đã chuẩn bị và điều kiện chốt

Bộ release xuất missingness, phân bố Twitch, tháng IQR, tăng trưởng tháng, tương quan Pearson/Spearman mô tả, seasonality chỉ trên train, baseline và sáu biểu đồ. Các bảng forecast-readiness bổ sung mô tả độ dài chuỗi, kỳ thiếu và tự tương quan chỉ train.

Trước khi nhóm chốt sản phẩm: xem manifest/country coverage, thống nhất chọn mục tiêu và horizon dự báo, thống nhất KPI và bộ lọc chất lượng. Sau đó dashboard và mô hình có thể triển khai song song. Đây không phải yêu cầu phải tìm nguồn mới để bắt đầu, nhưng không được che giấu những giới hạn nguồn chưa giải quyết.

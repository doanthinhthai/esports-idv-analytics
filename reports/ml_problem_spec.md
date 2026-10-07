# ĐẶC TẢ BÀI TOÁN MACHINE LEARNING

## 1. Mục tiêu

Dự báo tổng quỹ thưởng E-sports theo quý cho từng `game_family`. Mục tiêu chính là hỗ trợ dashboard và minh họa quy trình dự báo chuỗi thời gian, không phải đưa ra cam kết tài chính cho thị trường thực tế.

Đây là bài toán dự báo hồi quy theo thời gian. Một quan sát là một cặp `game_family`–`quarter`, không phải một giải đấu riêng lẻ.

## 2. Nguồn dữ liệu được phép sử dụng

Nguồn chính là thư mục `data/processed/analysis_release_v1_*` mới nhất, có `manifest.json` với trạng thái `analysis_release_v1_policy_clean_not_source_verified`.

- `forecast_prize_quarterly.csv`: bảng mô hình chính.
- `tournaments.csv`: kiểm tra tổng quỹ thưởng và số giải.
- `forecast_readiness.csv`: độ dài chuỗi và các kỳ thiếu.
- `forecast_status.csv`: trạng thái độ phủ test 2025.
- `forecast_baseline_predictions.csv` và `forecast_baseline_scores.csv`: seasonal-naive baseline.
- `eda_quality_sensitivity.csv`: đánh giá ảnh hưởng của chính sách chất lượng.

Không dùng các bảng processed cũ nằm ngoài release để trộn vào thí nghiệm.

## 3. Biến mục tiêu

### Mục tiêu chính

`target_prize_pool_usd`: tổng quỹ thưởng nguồn của các giải bắt đầu trong cùng family và quý. Giá trị được tính từ `pool_cents / 100` và bảo toàn tổng tiền từ bảng giải đấu.

### Phân tích độ nhạy

`strict_target_prize_pool_usd`: tổng quỹ thưởng chỉ của các giải đạt `strict_quality=True`.

Hai target không được trộn trong cùng một lần huấn luyện. Mô hình chính dùng target nguồn; target nghiêm ngặt là thí nghiệm độ nhạy vì bộ lọc này chỉ giữ 68,99% quỹ thưởng Dota 2 và 78,37% quỹ thưởng toàn bộ dữ liệu.

## 4. Phạm vi và cách chia dữ liệu

- Family: Counter-Strike, Dota 2, League of Legends và Valorant.
- Train: 2012Q1–2023Q4.
- Validation: 2024Q1–2024Q4.
- Test: 2025Q1–2025Q4.
- Valorant chỉ bắt đầu có quan sát từ 2020Q2. Các quý trước khi game xuất hiện không được coi là 0.

Việc chia phải theo thời gian. Không được shuffle các quý giữa train và test.

## 5. Trạng thái sẵn sàng của test

- Counter-Strike và Dota 2 có đủ bốn target quý trong năm 2025, nhưng độ phủ nguồn vẫn chưa được xác minh đầy đủ.
- League of Legends thiếu 2025Q4.
- Valorant thiếu 2025Q2 và 2025Q4.

Không tự điền 0 cho các quý thiếu. Báo cáo chính thức cho toàn bộ bốn family chỉ được chốt sau khi nhóm xác minh nguồn 2025 hoặc thống nhất một mốc test khác trước khi xem kết quả mô hình. Trong thời gian chờ, có thể chạy pipeline để kiểm tra kỹ thuật và báo cáo riêng số quý test thực sự quan sát được.

## 6. Đặc trưng được phép

Tất cả đặc trưng phải có sẵn trước quý cần dự báo:

- Target lag: `lag_1`, `lag_2`, `lag_4`.
- Thống kê quá khứ đã shift: trung bình, trung vị và độ lệch chuẩn của 4 quý trước.
- Mùa vụ: quý trong năm, có thể mã hóa one-hot hoặc sin/cos.
- Chỉ số thời gian tuyến tính để mô tả xu hướng dài hạn.
- `game_family` nếu huấn luyện một mô hình gộp; phải one-hot encode trong pipeline.

Mọi rolling feature phải được `shift(1)` trước khi tính để không chứa target của quý đang dự báo.

## 7. Biến không được dùng

- `observed_tournament_count` của quý đang dự báo vì đây là kết quả chỉ biết sau khi quý kết thúc.
- `strict_count`, `pool_cents`, `strict_pool_cents` của quý đang dự báo vì chúng trực tiếp chứa hoặc suy ra target.
- Tiền placements cùng quý.
- Twitch viewers hoặc hours watched cùng/tương lai quý nếu tại forecast origin chưa quan sát được.
- IQR flag hoặc ngưỡng ngoại lệ tính trên toàn chuỗi trước khi chia train/test.

Nếu bổ sung Twitch, chỉ dùng lag có thời điểm quan sát rõ ràng và phải ghi lại độ trễ công bố dữ liệu.

## 8. Mô hình và baseline

### Baseline bắt buộc

Seasonal naive: dự báo quý hiện tại bằng giá trị cùng quý năm trước (`t-4`). Baseline hiện có dùng rolling one-step; các quý test trước đó chỉ được dùng làm lag sau khi chúng đã được quan sát.

### Mô hình chính

1. Linear/Ridge Regression với lag và đặc trưng mùa vụ. Đây là mô hình dễ giải thích.
2. Random Forest Regressor với cùng tập thông tin để học quan hệ phi tuyến.

Siêu tham số chỉ được chọn bằng train và validation. Test không được dùng để chọn mô hình, feature, ngưỡng ngoại lệ, scaler hoặc chính sách missing.

## 9. Giao thức dự báo

Ưu tiên rolling one-step để so sánh công bằng với seasonal-naive hiện tại. Nếu nhóm muốn dự báo cả bốn quý cùng một lúc, phải huấn luyện và đánh giá lại baseline theo cùng forecast origin và horizon; không so trực tiếp hai giao thức khác nhau.

Pipeline phải fit preprocessing trên train, chọn cấu hình bằng validation, sau đó mới đánh giá test. Báo cáo số quan sát thực tế dùng trong từng family và split.

## 10. Chỉ số đánh giá

- MAE theo USD: dễ giải thích và ít nhạy hơn với quý cực lớn.
- RMSE theo USD: phạt mạnh các sai số lớn.
- Báo cáo riêng theo family và tổng hợp có trọng số theo số quý quan sát.

Không dùng MAPE làm chỉ số chính vì target có kỳ thiếu và có thể xuất hiện giá trị rất nhỏ. R² có thể bổ sung nhưng không dùng làm tiêu chí duy nhất do mỗi family có ít quý test.

## 11. Kết quả cần xuất ở Ngày 2

- `src/model.py`.
- Bảng metrics của seasonal naive, Linear/Ridge và Random Forest.
- Dự báo và residual ở cấp family–quý.
- Biểu đồ Actual vs Predicted.
- Feature importance hoặc coefficient.
- Bảng so sánh target nguồn với target nghiêm ngặt.
- Ghi rõ các quý test bị thiếu và số quan sát thực tế được đánh giá.

## 12. Giới hạn bắt buộc công bố

Release đã được làm sạch theo chính sách nhưng chưa xác minh đầy đủ độ phủ nguồn. Twitch chỉ là category chính theo tháng, bao gồm cả stream giải đấu và stream thông thường, kết thúc ở 2024-09 và không có YouTube. Tương quan giữa Twitch và quỹ thưởng không chứng minh quan hệ nhân quả. Tiền thưởng là USD danh nghĩa, chưa điều chỉnh lạm phát hoặc tỷ giá lịch sử.

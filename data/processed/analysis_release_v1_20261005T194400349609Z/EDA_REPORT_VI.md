# Kết quả EDA và mức sẵn sàng bàn giao

- Earnings: 14,082 giải, 52,551 placements.
- Twitch chính: 369 game–tháng; không phải người xem từng giải.
- Quốc gia: 57,597 dòng; 12,548/14,082 bảng giải đối chiếu đạt.
- Độ phủ tiền quốc gia: 97.67% tổng quỹ thưởng trong tập Earnings. Không dùng tỷ trọng trên tập đã duyệt để khẳng định toàn thị trường.
- Còn 1,534 bảng quốc gia thiếu hoặc tổng không khớp; đã cách ly, không bịa/hiệu chỉnh tiền.

## Kết luận sử dụng

Dashboard mô tả có thể triển khai theo README_VI.md. Bản đồ phải có bộ lọc/nhãn độ phủ và chỉ gọi là tiền thưởng theo quốc gia tuyển thủ. Chưa có mapping khu vực thi đấu/châu lục được duyệt.

Mục tiêu dự báo chính là tổng quỹ thưởng quý từ nguồn. Xem forecast_readiness.csv trước khi chọn family; kỳ thiếu cần chính sách riêng, không xóa khoảng trống hay tự điền 0. Chia thời gian đã có trong cột split. Baseline đã chuẩn bị; chưa huấn luyện/chọn mô hình cuối.

**Chưa được coi dự báo năm 2025 của cả bốn game là sẵn sàng:** kỳ test không có quan sát: League of Legends: 2025Q4; Valorant: 2025Q2, 2025Q4. Xem forecast_status.csv để biết game nào có đủ kỳ quan sát. Độ phủ nguồn vẫn chưa xác minh ngay cả khi có đủ kỳ. Cần bổ sung/kiểm tra nguồn 2025, hoặc được nhóm đồng ý đổi mốc đánh giá; không tự thu hẹp scope dự án.

## Phát hiện quan trọng cho dashboard và mô hình

- Số giải quan sát năm 2025: Counter-Strike: 289; Dota 2: 19; League of Legends: 10; Valorant: 5. Xem eda_annual_source_counts.csv để đối chiếu các năm trước; giảm số giải quan sát có thể là cảnh báo độ phủ, không được tự diễn giải là thị trường sụp giảm.
- Bộ lọc nghiêm ngặt giữ quỹ thưởng: Counter-Strike: 90.47%; Dota 2: 68.99%; League of Legends: 83.07%; Valorant: 92.22%. Bỏ mọi giải có cờ chất lượng làm thay đổi target; dùng mục tiêu quỹ thưởng nguồn và báo cáo độ nhạy riêng.
- Tương quan Pearson giờ xem–quỹ thưởng tháng: Counter-Strike: 0.042 (n=105); Dota 2: 0.698 (n=105); League of Legends: 0.050 (n=105); Valorant: 0.024 (n=53). Spearman có trong bảng tương quan. Không hứa mô hình nhiều biến sẽ tốt; cần kiểm soát mùa vụ/xu hướng và dùng lag hợp lệ.
- Quốc gia có độ phủ tiền không đồng đều theo năm: thấp nhất League of Legends, năm 2020, 71.10%. Dashboard phải hiện độ phủ theo bộ lọc, không chỉ một con số toàn tập.
- Twitch không thiếu tháng trong bốn chuỗi chính; Valorant có lịch sử ngắn hơn. Dữ liệu sau 2024-09 không có, không điền thêm các tháng giả để ghép với Earnings 2025.

EDA toàn lịch sử là mô tả, không là bằng chứng nhân quả và không dùng để chọn mô hình theo test. Seasonality/autocorrelation phục vụ mô hình chỉ tính train. IQR giữ nguyên các tháng bùng nổ.

## Tệp nên đọc

- eda_quality_sensitivity.csv: mức thay đổi khi chỉ dùng tập nghiêm ngặt.
- eda_correlations_descriptive.csv: tương quan có n từng family, chưa loại xu hướng/mùa vụ.
- forecast_readiness.csv, eda_train_autocorrelation.csv: số kỳ và cấu trúc thời gian.
- country_coverage.csv: độ phủ bản đồ theo family–năm.
- eda/01–06: xu hướng Twitch, tiền thưởng, tỷ trọng, độ phủ và scatter.

## Giới hạn chưa thể giải quyết bằng cleaning

Chưa xác minh đủ website; quỹ thưởng và phân bổ có thể sai ở nguồn. Thiếu Twitch sau 2024-09, YouTube và quốc gia khán giả. Không có prize_per_viewer giải hay ROI. Bàn giao được theo phạm vi này, không phải cam kết không có trở ngại hay dữ liệu đúng tuyệt đối.

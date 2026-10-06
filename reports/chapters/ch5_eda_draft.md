# CHƯƠNG 5. KHÁM PHÁ DỮ LIỆU VÀ ĐẶC TẢ MÔ HÌNH

## 5.1. Phạm vi phân tích

Phân tích sử dụng bản `analysis_release_v1_20261005T194400349609Z`, là release đã làm sạch theo chính sách nhưng chưa xác minh đầy đủ độ phủ nguồn. Dữ liệu giải đấu bao phủ từ ngày 04/01/2012 đến 15/11/2025 và gồm bốn family: Counter-Strike, Dota 2, League of Legends và Valorant.

Release chứa 14.082 giải đấu, 52.551 kết quả placement, 369 quan sát game–tháng trên Twitch và 57.597 dòng tiền thưởng quốc gia đã đối chiếu. Tổng quỹ thưởng nguồn là khoảng 745,13 triệu USD danh nghĩa. Tiền thưởng chưa được điều chỉnh lạm phát hoặc tỷ giá lịch sử.

Đơn vị phân tích thay đổi theo câu hỏi:

- Xu hướng quỹ thưởng: một family–quý.
- Xu hướng Twitch: một family–tháng.
- Số giải: một family–năm.
- Bản đồ: một giải–quốc gia tuyển thủ, chỉ gồm các bảng quốc gia đối chiếu đạt.

Không nối trực tiếp bảng giải với placements hoặc quốc gia rồi cộng lại `prize_pool_usd`, vì quan hệ một–nhiều sẽ làm lặp quỹ thưởng của giải.

## 5.2. Kiểm tra chất lượng

Các khóa `tournament_id` và `placement_id` là duy nhất. Toàn bộ placement có giải đấu cha hợp lệ. Bảng Twitch không trùng khóa `game_family + month_start`; bảng dự báo không trùng khóa `game_family + quarter`. Tổng tiền và số giải theo quý đối chiếu đúng với bảng tournament.

Release không coi missing là 0. Các trường thiếu trong bảng tournament và placement chủ yếu phản ánh thông tin nguồn không có, identity chưa xác định hoặc dữ liệu đã được cách ly. Việc bảng đã qua cleaning không có nghĩa mọi số liệu nguồn hoặc độ phủ giải đấu đều đúng hoàn toàn.

## 5.3. Kết quả EDA

### 5.3.1. Quỹ thưởng theo quý

Dota 2 có tổng quỹ thưởng nguồn lớn nhất, khoảng 380,57 triệu USD. Counter-Strike đạt khoảng 208,57 triệu USD, League of Legends khoảng 121,38 triệu USD và Valorant khoảng 34,61 triệu USD. Chuỗi Dota 2 có các quý đột biến trên 30 triệu USD, trong khi Counter-Strike có xu hướng ổn định hơn sau giai đoạn tăng mạnh trước năm 2018.

**Hình 5.1.** Tổng quỹ thưởng theo family–quý. Nền vàng là validation năm 2024, nền đỏ là test năm 2025. Đường đứt mô tả target nghiêm ngặt. League of Legends thiếu 2025Q4; Valorant thiếu 2025Q2 và 2025Q4 nên các điểm này để trống.

### 5.3.2. Xu hướng Twitch

Twitch có 105 tháng cho Counter-Strike, Dota 2 và League of Legends trong giai đoạn 2016-01 đến 2024-09. Valorant có 54 tháng từ 2020-04 đến 2024-09. Dữ liệu là category chính của game trên Twitch, bao gồm cả stream giải đấu và stream thông thường; không đại diện cho người xem của từng giải và không bao gồm YouTube.

**Hình 5.2.** Giờ xem Twitch theo tháng và trung bình trượt 12 tháng. League of Legends đạt quy mô giờ xem cao trong phần lớn giai đoạn. Valorant có lịch sử ngắn hơn và điểm đầu chuỗi biến động mạnh, cần thận trọng khi so sánh dài hạn.

### 5.3.3. Số giải quan sát và độ phủ 2025

Số giải quan sát năm 2025 là 289 với Counter-Strike, 19 với Dota 2, 10 với League of Legends và 5 với Valorant. Mức giảm mạnh so với năm trước có thể phản ánh thiếu độ phủ nguồn. Không được diễn giải biểu đồ này như bằng chứng thị trường E-sports suy giảm.

**Hình 5.3.** Số giải quan sát theo family và năm. Năm 2025 được đánh dấu riêng vì độ phủ nguồn chưa xác minh.

### 5.3.4. Độ nhạy với chính sách chất lượng

Bộ lọc `strict_quality` giữ lại 90,47% quỹ thưởng Counter-Strike, 68,99% Dota 2, 83,07% League of Legends và 92,22% Valorant. Toàn bộ bốn family giữ khoảng 78,37% quỹ thưởng nguồn. Sự khác biệt lớn ở Dota 2 cho thấy chính sách chất lượng có thể làm thay đổi đáng kể target và kết luận mô hình.

**Hình 5.4.** Tỷ lệ quỹ thưởng nguồn còn lại sau bộ lọc strict-quality. Target nguồn được dùng cho mô hình chính; target strict được dùng như phân tích độ nhạy riêng.

### 5.3.5. Độ phủ bảng quốc gia

Các bảng quốc gia đã đối chiếu bao phủ khoảng 97,67% tổng quỹ thưởng nguồn. Độ phủ không đồng đều theo family và năm. Mức thấp nhất là League of Legends năm 2020, khoảng 71,10%. Vì vậy dashboard bản đồ phải hiển thị độ phủ theo bộ lọc và gọi đúng là tiền thưởng theo quốc gia tuyển thủ trong tập đã đối chiếu, không phải tỷ trọng toàn bộ thị trường hoặc quốc gia khán giả.

**Hình 5.5.** Độ phủ quỹ thưởng của các bảng quốc gia đã đối chiếu theo family và năm.

### 5.3.6. Tương quan mô tả

Tương quan Pearson giữa giờ xem Twitch và quỹ thưởng theo tháng là 0,042 với Counter-Strike, 0,698 với Dota 2, 0,050 với League of Legends và 0,024 với Valorant. Kết quả Dota 2 cao hơn rõ rệt nhưng chưa kiểm soát mùa vụ, xu hướng thời gian hoặc các sự kiện lớn. Các hệ số này chỉ mô tả bộ dữ liệu và không chứng minh tiền thưởng làm tăng người xem.

## 5.4. Bài toán dự báo

Mục tiêu chính là `target_prize_pool_usd` theo family–quý. Dữ liệu chia theo thời gian: 2012–2023 cho train, năm 2024 cho validation và năm 2025 cho test. Valorant chỉ bắt đầu từ 2020Q2; các quý trước khi game xuất hiện không được coi là 0.

Seasonal naive `t-4` là baseline bắt buộc. Hai mô hình tiếp theo là Linear/Ridge Regression và Random Forest sử dụng target lag, thống kê rolling đã shift và mùa vụ quý. Không sử dụng số giải, placements hoặc Twitch của chính quý đang dự báo vì các biến này chưa có tại forecast origin hoặc trực tiếp chứa thông tin target.

League of Legends và Valorant chưa có đủ target test 2025. Vì vậy kết quả toàn bộ bốn family chưa được coi là đánh giá cuối cho đến khi nhóm xác minh nguồn hoặc thống nhất mốc test khác trước khi xem kết quả mô hình.

## 5.5. Giới hạn

Release là policy-clean chứ không phải chứng nhận độ chính xác hoặc độ phủ nguồn. Quỹ thưởng là USD danh nghĩa. Twitch kết thúc ở 2024-09 và không có YouTube. Dữ liệu country là quốc gia tuyển thủ, không phải quốc gia khán giả. Bộ lọc nghiêm ngặt có thể thiên lệch về các giải dễ thu thập. Các tháng/quý bùng nổ được giữ nguyên trong EDA; mọi xử lý ngoại lệ cho mô hình phải được fit trên train sau khi chia thời gian.

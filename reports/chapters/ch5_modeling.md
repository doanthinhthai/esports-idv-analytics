# CHƯƠNG 5. PHÂN TÍCH DỮ LIỆU VÀ MÔ HÌNH DỰ BÁO

## 5.1. Phạm vi và dữ liệu

Phân tích sử dụng `analysis_release_v1_20261005T194400349609Z`. Đây là release đã làm sạch theo chính sách nhưng chưa xác minh đầy đủ độ phủ nguồn. Release gồm bốn nhóm game: Counter-Strike, Dota 2, League of Legends và Valorant; 14.082 giải đấu; 52.551 kết quả placement; 369 quan sát game–tháng trên Twitch; và 57.597 dòng tiền thưởng quốc gia đã đối chiếu.

Tổng quỹ thưởng nguồn quan sát được khoảng 745,13 triệu USD danh nghĩa. Tiền thưởng chưa được điều chỉnh lạm phát. Dữ liệu Twitch chỉ đại diện cho category chính của game trên Twitch, không phải riêng stream giải đấu và không bao gồm YouTube. Dữ liệu quốc gia là quốc gia tuyển thủ nhận tiền thưởng, không phải quốc gia khán giả.

Đơn vị phân tích của mô hình là một `game_family` trong một quý. Target chính là `target_prize_pool_usd`; target `strict_target_prize_pool_usd` chỉ dùng để kiểm tra độ nhạy với chính sách chất lượng. Các quý trước khi Valorant xuất hiện không được coi là quỹ thưởng bằng 0.

## 5.2. Kiểm tra dữ liệu

Các khóa `tournament_id` và `placement_id` là duy nhất. Toàn bộ placement có tournament cha hợp lệ. Bảng Twitch không trùng khóa `game_family + month_start`; bảng dự báo không trùng khóa `game_family + quarter`. Tổng quỹ thưởng và số giải theo quý đối chiếu đúng với bảng tournament.

Không nối trực tiếp bảng tournament với placements hoặc country rồi cộng `prize_pool_usd`, vì quan hệ một–nhiều sẽ lặp quỹ thưởng của giải. Các bảng quốc gia đã đối chiếu bao phủ khoảng 97,67% tổng quỹ thưởng nguồn, nhưng độ phủ khác nhau theo family và năm.

Ba target test đang thiếu là League of Legends 2025Q4, Valorant 2025Q2 và Valorant 2025Q4. Các giá trị này được giữ là null, không nội suy và không thay bằng 0.

## 5.3. Kết quả khám phá dữ liệu

Dota 2 có tổng quỹ thưởng quan sát lớn nhất, khoảng 380,57 triệu USD. Counter-Strike đạt 208,57 triệu USD, League of Legends đạt 121,38 triệu USD và Valorant đạt 34,61 triệu USD. Quý cao nhất của Dota 2 là 2021Q4 với khoảng 42,19 triệu USD, lớn hơn rõ rệt đỉnh của các family khác.

Trung vị giờ xem Twitch hàng tháng cao nhất thuộc về League of Legends, khoảng 99,0 triệu giờ. Tương quan Pearson giữa giờ xem và quỹ thưởng theo tháng là 0,042 với Counter-Strike, 0,698 với Dota 2, 0,050 với League of Legends và 0,024 với Valorant. Đây là tương quan mô tả, không chứng minh quỹ thưởng làm tăng lượng người xem.

Bộ lọc strict-quality giữ lại khoảng 90,47% quỹ thưởng Counter-Strike, 68,99% Dota 2, 83,07% League of Legends và 92,22% Valorant. Chênh lệch lớn ở Dota 2 cho thấy kết luận có thể nhạy với chính sách chất lượng.

Các hình EDA được lưu tại `reports/figures/eda_*.png`. Năm 2025 được ghi chú riêng vì độ phủ nguồn chưa được xác minh; số giải quan sát thấp không được diễn giải thành bằng chứng thị trường suy giảm.

## 5.4. Đặc tả bài toán dự báo

Dữ liệu được chia theo thời gian:

- Train: từ kỳ quan sát đầu tiên đến 2023Q4.
- Validation: 2024Q1–2024Q4.
- Test: 2025Q1–2025Q4.

Giao thức đánh giá là rolling one-step. Khi dự báo một quý, target đã quan sát của những quý trước trong cùng split có thể được dùng để tạo biến trễ. Đây là dự báo cập nhật theo quý, không phải dự báo toàn bộ năm tại một thời điểm duy nhất.

Các feature hợp lệ gồm `lag_1`, `lag_2`, `lag_4`, trung bình, trung vị và độ lệch chuẩn của bốn quý trước sau `shift(1)`, quý trong năm, chỉ số thời gian và `game_family`. Mô hình không sử dụng số giải, placements, quỹ thưởng hoặc Twitch của chính quý cần dự báo vì các trường này chưa có tại forecast origin hoặc chứa trực tiếp thông tin target.

## 5.5. Các mô hình

### 5.5.1. Seasonal Naive

Seasonal Naive dùng cùng quý của năm trước:

```text
ŷ(t) = y(t-4)
```

Đây là baseline bắt buộc. Mô hình học máy chỉ có ý nghĩa thực tiễn khi được so sánh với baseline đơn giản này trên cùng split và giao thức.

### 5.5.2. Linear Regression

Linear Regression có dạng:

```text
ŷ = β0 + β1x1 + β2x2 + ... + βpxp
```

Feature số được điền median và chuẩn hóa. `game_family` và quý trong năm được one-hot encoding. Dự báo âm được cắt về 0 vì quỹ thưởng không thể âm. Mô hình này hỗ trợ giải thích tuyến tính nhưng khó mô tả các quý đột biến.

### 5.5.3. Random Forest

Random Forest lấy trung bình dự báo của nhiều cây quyết định:

```text
ŷ = (1/B) × Σ f_b(x)
```

Mô hình sử dụng 500 cây. Siêu tham số được chọn trên validation, không xem test. Cấu hình tốt nhất cho target nguồn là `max_depth=4`, `min_samples_leaf=1` và `max_features=sqrt`.

## 5.6. Chỉ số đánh giá

Sai số tuyệt đối trung bình:

```text
MAE = (1/n) × Σ |y - ŷ|
```

Căn sai số bình phương trung bình:

```text
RMSE = sqrt((1/n) × Σ (y - ŷ)²)
```

RMSE phạt mạnh các dự báo sai lớn nên phù hợp với chuỗi quỹ thưởng có quý đột biến. R² chỉ là chỉ số chẩn đoán. R² không được báo cáo cho nhóm có ít hơn bốn kỳ đánh giá và không được dùng làm tiêu chí duy nhất khi test nhỏ.

## 5.7. Kết quả mô hình

| Mô hình | Validation MAE (USD) | Validation RMSE (USD) | Test MAE (USD) | Test RMSE (USD) |
|---|---:|---:|---:|---:|
| Seasonal Naive `t-4` | 1.303.145 | 2.194.181 | 1.845.569 | **2.410.869** |
| Linear Regression | 2.014.934 | 2.980.558 | 2.925.854 | 3.995.387 |
| Random Forest | 1.419.040 | **1.976.568** | **1.818.034** | 2.511.323 |

Random Forest có validation RMSE thấp nhất nên được chọn làm mô hình chính trước khi xem test. Trên 13 family–quý test có actual, Seasonal Naive có test RMSE thấp hơn Random Forest khoảng 100 nghìn USD. Random Forest có test MAE thấp hơn baseline khoảng 28 nghìn USD nhưng không cải thiện RMSE. Vì vậy mô hình phức tạp chưa chứng minh được mức cải thiện ổn định ngoài mẫu.

R² test tổng hợp là khoảng -0,324 với Seasonal Naive, -2,636 với Linear Regression và -0,437 với Random Forest. R² âm cho thấy các mô hình gặp khó khăn trên tập test nhỏ, có quý biến động mạnh và chưa xác minh đầy đủ độ phủ nguồn.

### 5.7.1. Kết quả Random Forest theo family

| Family | Kỳ test được đánh giá | Tổng kỳ test | Test RMSE (USD) |
|---|---:|---:|---:|
| Counter-Strike | 4 | 4 | 2.872.341 |
| Dota 2 | 4 | 4 | 3.014.293 |
| League of Legends | 3 | 4 | 1.664.336 |
| Valorant | 2 | 4 | 1.471.794 |

Không so sánh trực tiếp RMSE giữa family để kết luận family nào dễ dự báo nhất, vì quy mô target và số kỳ được đánh giá khác nhau. League of Legends và Valorant chỉ có partial test.

## 5.8. Feature importance và sai số

`lag_4` có importance lớn nhất trong Random Forest target nguồn, khoảng 0,266. Các biến tiếp theo là trung bình trượt bốn quý 0,125; độ lệch chuẩn trượt 0,116; `lag_2` khoảng 0,100; trung vị trượt khoảng 0,100; và `lag_1` khoảng 0,079. Impurity importance chỉ mô tả cách mô hình sử dụng biến và không chứng minh quan hệ nhân quả.

Ba sai số tuyệt đối lớn nhất trên validation và test là:

| Family | Quý | Actual (USD M) | Random Forest (USD M) | Residual (USD M) |
|---|---|---:|---:|---:|
| Dota 2 | 2024Q3 | 9,50 | 15,19 | -5,68 |
| Counter-Strike | 2025Q4 | 0,66 | 6,24 | -5,59 |
| Dota 2 | 2025Q4 | 1,00 | 6,54 | -5,54 |

Residual được tính bằng actual trừ predicted; residual âm là overprediction. Dota 2 chiếm khoảng 42,3% tổng sai số tuyệt đối, còn Q4 chiếm khoảng 36,6%. Mô hình dùng biến trễ phản ứng chậm khi một mẫu quỹ thưởng cao được theo sau bởi mức giảm đột ngột. Actual 2025 cũng có thể chịu ảnh hưởng của độ phủ nguồn.

## 5.9. Phân tích độ nhạy strict-quality

Random Forest strict-quality có validation RMSE khoảng 1,24 triệu USD và test RMSE khoảng 2,07 triệu USD. Các số này không được diễn giải là mô hình strict tốt hơn target nguồn, vì target và tổng tiền đã thay đổi sau bộ lọc. Kết quả strict chỉ cho biết kết luận mô hình nhạy như thế nào với chính sách loại dữ liệu.

## 5.10. Hàm ý sử dụng

Dota 2 là tín hiệu quy mô quỹ thưởng lớn nhưng có biến động và rủi ro dự báo cao. League of Legends có quy mô chú ý trên Twitch cao nhưng tương quan giữa Twitch và quỹ thưởng gần 0. Country view có thể hỗ trợ nội dung gắn với tuyển thủ, nhưng không đại diện cho quốc gia khán giả.

Các kết quả hỗ trợ `tín hiệu ưu tiên tài trợ`, `phân bổ thử nghiệm` và lựa chọn thị trường cần xác minh thêm. Dữ liệu không có doanh thu, chi phí tài trợ hoặc lợi nhuận nên không đủ cơ sở tính ROI.

## 5.11. Giới hạn

- Release là policy-clean, không phải chứng nhận đầy đủ độ phủ nguồn.
- Quỹ thưởng là USD danh nghĩa và chưa điều chỉnh lạm phát.
- Test chỉ có một năm; League of Legends và Valorant thiếu target.
- Giao thức rolling one-step sử dụng actual của các quý trước trong cùng split và không tương đương dự báo nhiều bước từ đầu năm.
- Twitch kết thúc tháng 9/2024, không chỉ gồm stream giải đấu và không có YouTube.
- Country là quốc gia tuyển thủ trong bảng đã đối chiếu.
- Feature importance và correlation không chứng minh quan hệ nhân quả.

Nguồn số liệu chi tiết nằm trong `reports/model_metrics.csv`, `reports/model_predictions.csv`, `reports/model_feature_importance.csv`, `reports/storytelling_evidence.csv` và các hình `reports/figures/model_*.png`, `reports/figures/story_*.png`.

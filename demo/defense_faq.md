# FAQ BẢO VỆ ĐỒ ÁN

## A. Dữ liệu và grain

### 1. Vì sao phải xác định grain trước khi phân tích?

Grain cho biết mỗi dòng đại diện cho đối tượng nào. Tournament là một dòng mỗi giải, placements là nhiều dòng trong một giải, country là nhiều dòng theo quốc gia tuyển thủ và forecast là một dòng mỗi family–quarter–policy–model. Nếu join các bảng khác grain rồi cộng tiền, quỹ thưởng bị lặp.

### 2. Fan-out là gì?

Fan-out xảy ra khi một dòng tournament ghép với nhiều placement hoặc country rows. Ví dụ quỹ thưởng 1 triệu USD ghép với 20 placement sẽ xuất hiện 20 lần và có thể bị cộng thành 20 triệu USD. Nhóm đối chiếu tổng ở grain tournament hoặc family–quarter trước khi trực quan hóa.

### 3. Vì sao không coi missing là 0?

0 nghĩa là đã quan sát và thực sự không có quỹ thưởng. Missing nghĩa là chưa có dữ liệu hoặc kỳ không thuộc phạm vi. Đổi missing thành 0 sẽ làm giảm giả tạo target, residual và metrics.

### 4. Ba target test nào đang thiếu?

League of Legends 2025Q4, Valorant 2025Q2 và Valorant 2025Q4. Chúng có prediction nhưng không có actual và không được tính vào metrics.

### 5. Vì sao không kết luận số giải năm 2025 giảm?

Nguồn năm 2025 chưa được xác minh đầy đủ độ phủ. Số giải quan sát thấp có thể phản ánh thu thập thiếu chứ không phải thị trường suy giảm.

### 6. Strict-quality là gì?

Đây là target sau bộ lọc chất lượng nghiêm ngặt hơn. Nhóm dùng nó như sensitivity analysis để xem kết luận có nhạy với policy không. Strict không tự động đồng nghĩa với chính xác hơn vì có thể loại nhiều giải khó thu thập.

## B. Mô hình và đánh giá

### 7. Vì sao dự báo theo family–quý thay vì từng tournament?

Release hiện tại có target quý ổn định và lịch sử liên tục hơn. Nhiều feature cấp tournament trong đề cương ban đầu không tồn tại hoặc chỉ biết sau khi giải diễn ra. Dự báo tournament bằng các trường đó sẽ gây leakage hoặc tạo bài toán không tái lập.

### 8. Vì sao chia dữ liệu theo thời gian?

Dự báo phải học từ quá khứ và đánh giá ở tương lai. Chia ngẫu nhiên có thể đưa quan sát tương lai vào train, làm kết quả lạc quan giả tạo.

### 9. Train, validation và test được chia thế nào?

Train đến 2023Q4, validation là bốn quý năm 2024 và test là bốn quý năm 2025. Không đổi mốc test sau khi nhìn kết quả.

### 10. Rolling one-step là gì?

Mô hình dự báo từng quý và được phép dùng actual đã quan sát của quý trước làm lag. Đây là dự báo cập nhật theo quý, không phải dự báo toàn bộ năm từ đầu năm.

### 11. Nhóm ngăn leakage như thế nào?

Chỉ dùng lag và rolling đã `shift(1)`. Nhóm loại số giải, placements, quỹ thưởng và Twitch của chính quý cần dự báo. Validation chỉ fit train; test fit train cộng validation.

### 12. Vì sao cần Seasonal Naive?

Quỹ thưởng có mùa vụ. Seasonal Naive dùng cùng quý năm trước và tạo baseline thực tế. Nếu mô hình phức tạp không thắng baseline, nhóm phải báo cáo trung thực thay vì chỉ trình bày model học máy.

### 13. Vì sao chọn Random Forest khi Seasonal Naive tốt hơn trên test RMSE?

Quy tắc chọn model dùng validation RMSE trước khi xem test. Random Forest đạt validation RMSE 1,98 triệu USD, thấp hơn Seasonal Naive 2,19 triệu USD. Test dùng để đánh giá độc lập; việc Seasonal Naive đạt 2,41 triệu USD so với Random Forest 2,51 triệu USD cho thấy Random Forest chưa cải thiện ổn định, không phải lý do chọn lại model sau khi xem test.

### 14. Vì sao Linear Regression kém?

Quỹ thưởng có quan hệ phi tuyến, seasonality và quý đột biến. Một mô hình tuyến tính gộp khó mô tả các thay đổi này. Linear Regression vẫn hữu ích làm mô hình giải thích và đối chuẩn.

### 15. MAE và RMSE khác nhau thế nào?

MAE là sai số tuyệt đối trung bình và dễ diễn giải theo USD. RMSE bình phương sai số trước khi lấy trung bình nên phạt mạnh những quý dự báo sai lớn. Nhóm báo cáo cả hai.

### 16. Vì sao không dùng MAPE làm chỉ số chính?

MAPE không ổn định khi actual nhỏ hoặc bằng 0 và phạt bất đối xứng overprediction/underprediction. Dữ liệu có các quý actual thấp và thiếu. MAE và RMSE phù hợp hơn với đơn vị USD và chính sách missing.

### 17. R² âm có nghĩa là gì?

Trên tập test này, R² âm cho thấy mô hình chưa tốt hơn dự báo bằng trung bình test theo định nghĩa R². Test chỉ có 13 actual hợp lệ và có các quý biến động mạnh. Nhóm coi R² là chẩn đoán, không che giấu và không dùng làm chỉ số duy nhất.

### 18. Feature importance có chứng minh nguyên nhân không?

Không. Importance chỉ cho biết Random Forest sử dụng feature nào để giảm impurity. `lag_4` quan trọng nhất cho thấy seasonality hữu ích, nhưng không chứng minh quỹ thưởng năm trước gây ra quỹ thưởng năm nay.

### 19. Vì sao không loại các quý đột biến?

Các quý đột biến là một phần thật của thị trường E-sports. Loại chúng chỉ vì mô hình dự báo khó sẽ làm sai bài toán. Nếu cần xử lý outlier, quy tắc phải được fit trên train và báo cáo riêng.

### 20. Vì sao Dota 2 sai số lớn?

Dota 2 có các quý giải thưởng rất lớn và thay đổi mạnh theo mùa sự kiện. Feature trễ có thể dự báo quá cao sau một quý lớn. Ngoài ra, độ phủ nguồn 2025 chưa được xác minh nên residual không chỉ phản ánh model.

## C. Twitch, country và diễn giải

### 21. Tương quan Dota 2 khoảng 0,698 có nghĩa gì?

Trong các tháng quan sát, giờ xem Twitch và quỹ thưởng Dota 2 có quan hệ tuyến tính mô tả tương đối cao. Nó không chứng minh quỹ thưởng làm tăng người xem vì chưa kiểm soát mùa vụ, xu hướng, giải lớn hoặc các yếu tố khác.

### 22. Vì sao League of Legends có nhiều giờ xem nhưng tương quan thấp?

Twitch category ghi nhận cả nội dung ngoài giải đấu. Lượng xem có thể đến từ streamer, cập nhật game hoặc cộng đồng, không nhất thiết chuyển động cùng quỹ thưởng theo tháng.

### 23. Country trên bản đồ là gì?

Là quốc gia tuyển thủ nhận tiền thưởng trong các bảng đã đối chiếu. Nó không phải audience country hoặc tournament location. Dashboard phải hiển thị coverage cùng bản đồ.

### 24. Vì sao không được nói ROI?

ROI cần doanh thu hoặc lợi ích tài chính và chi phí đầu tư. Dataset chỉ có quỹ thưởng, Twitch và thông tin quốc gia tuyển thủ; không có chi phí tài trợ, doanh thu hay lợi nhuận.

## D. Tableau và triển khai

### 25. Vì sao forecast không join với placements hoặc country?

Forecast ở grain family–quarter, trong khi placements và country có nhiều dòng trong mỗi family–quarter. Physical join sẽ lặp actual và prediction. Nhóm dùng forecast như fact table riêng hoặc relationship với dimension duy nhất.

### 26. Vì sao model filter phải single-select?

Actual được lặp một lần cho mỗi model trong bảng dài. Nếu chọn nhiều model rồi SUM actual, Tableau sẽ nhân actual. Single-select hoặc FIXED LOD tại family–quarter–policy ngăn lỗi này.

### 27. Làm sao kiểm tra Tableau đúng?

Với `source + random_forest + test`, phải có 16 dòng, 13 dòng evaluated và ba dòng prediction-only. MAE/RMSE Overall phải khớp `tableau_forecast_summary.csv`. Actual không được đổi khi chỉ đổi kiểu biểu đồ hoặc tương tác country map.

### 28. Pipeline có tái lập được không?

Có. Từ repository root, chạy lần lượt `src/eda.py`, `src/model.py`, `src/storytelling.py` và `src/validate_deliverables.py`. Các script tự chọn analysis release mới nhất và ghi output vào đường dẫn tương đối.

### 29. Hạn chế lớn nhất của đề tài là gì?

Độ phủ nguồn 2025 chưa được xác minh đầy đủ và test nhỏ. Vì vậy kết quả phù hợp làm chẩn đoán và tín hiệu planning, chưa phải forecast production hoặc bằng chứng ROI.

### 30. Nếu có thêm thời gian, nhóm sẽ cải thiện gì?

Xác minh dữ liệu 2025, đánh giá walk-forward nhiều năm, xây prediction interval, bổ sung lịch sự kiện biết trước, mở rộng YouTube và audience geography, rồi thu thập dữ liệu chi phí/doanh thu để đánh giá hiệu quả tài trợ.

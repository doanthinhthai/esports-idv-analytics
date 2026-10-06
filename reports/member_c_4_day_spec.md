# ĐẶC TẢ CÔNG VIỆC 4 NGÀY - THÀNH VIÊN C

## 1. Vai trò và phạm vi

Thành viên C phụ trách Data Science, EDA, mô hình dự báo, diễn giải kết quả, Chương 5-7 của báo cáo, kịch bản demo và nội dung ôn vấn đáp.

Kế hoạch này chuyển các đầu việc trong tài liệu phân công thành bốn ngày làm việc liên tục và điều chỉnh theo `analysis_release_v1_*` hiện tại. Dữ liệu mới khác giả định ban đầu của đề cương: bài toán phù hợp là dự báo tổng quỹ thưởng theo `game_family`-quý, không phải dự báo từng giải bằng các biến chưa có trong release.

## 2. Nguyên tắc bắt buộc

1. Chỉ dùng thư mục `data/processed/analysis_release_v1_*` mới nhất cho EDA và mô hình.
2. Không sửa dữ liệu nguồn của Thành viên A trong release.
3. Không coi missing là 0. League of Legends thiếu `2025Q4`; Valorant thiếu `2025Q2` và `2025Q4`.
4. Không dùng thông tin của chính quý cần dự báo, như số giải thực tế, tiền placements hoặc Twitch cùng quý.
5. Không ghi trước R² hoặc mức cải thiện của Random Forest. Mọi con số phải lấy từ kết quả chạy thực tế.
6. Không khẳng định tương quan là quan hệ nhân quả.
7. Không gọi khuyến nghị là ROI nếu chưa có dữ liệu doanh thu, chi phí tài trợ và lợi nhuận.
8. Mỗi nhánh phải có phạm vi chức năng rõ ràng, được review trước khi merge vào `develop`.

## 3. Tổng quan bốn ngày

| Ngày | Chức năng chính | Nhánh Git đề xuất | Trạng thái |
|---|---|---|---|
| Ngày 1 | Kiểm định dữ liệu, EDA và đặc tả ML | `feature/tournament-prize-eda` | Đã hoàn thành, commit `78fe303` |
| Ngày 2 | Huấn luyện và đánh giá mô hình dự báo | `feature/prize-forecast-model` | Chưa thực hiện |
| Ngày 3 | Phân tích insight, storytelling và bàn giao Tableau | `feature/forecast-storytelling` | Chưa thực hiện |
| Ngày 4 | Hoàn thiện báo cáo, demo và FAQ vấn đáp | `docs/report-defense-package` | Chưa thực hiện |

---

## 4. Ngày 1 - EDA và đặc tả bài toán ML

### 4.1. Mục tiêu

Xác nhận release mới đủ điều kiện để phân tích, mô tả các xu hướng quan trọng, nhận diện giới hạn dữ liệu và khóa giao thức mô hình trước khi huấn luyện.

### 4.2. Đầu vào

- `manifest.json`.
- `tournaments.csv`.
- `placements.csv`.
- `twitch_monthly.csv`.
- `game_monthly_panel.csv`.
- `forecast_prize_quarterly.csv`.
- `country_coverage.csv`.
- Các bảng `eda_*` và `forecast_*` trong release.

### 4.3. Công việc

#### Buổi sáng - Kiểm định release

- Kiểm tra khóa `tournament_id`, `placement_id`.
- Kiểm tra placement có tournament cha.
- Kiểm tra grain game-tháng và game-quý.
- Đối chiếu tổng tiền và số giải giữa bảng tournament và bảng quý.
- Xác nhận phạm vi bốn family và giai đoạn 2012-2025.

#### Buổi chiều - EDA

- Vẽ quỹ thưởng theo family-quý.
- Vẽ giờ xem Twitch theo tháng và trung bình trượt 12 tháng.
- Vẽ số giải quan sát theo năm.
- Phân tích độ nhạy của bộ lọc `strict_quality`.
- Phân tích độ phủ bảng quốc gia.
- Ghi rõ những kỳ thiếu và giới hạn nguồn.

#### Buổi tối - Đặc tả ML và báo cáo

- Xác định target `target_prize_pool_usd`.
- Chọn seasonal naive `t-4` làm baseline.
- Xác định train 2012-2023, validation 2024, test 2025.
- Liệt kê feature hợp lệ và feature gây leakage.
- Viết phần EDA của Chương 5.

### 4.4. Đầu ra

- `src/eda.py`.
- `reports/eda_summary.csv`.
- `reports/ml_problem_spec.md`.
- `reports/chapters/ch5_eda_draft.md`.
- Năm hình `reports/figures/eda_*.png` ở 300 DPI.

### 4.5. Tiêu chí hoàn thành

- Script chạy lại được từ repository.
- Tổng tiền theo quý khớp bảng tournament.
- Không có khóa trùng hoặc placement mồ côi.
- Hình không cắt chữ và đúng 300 DPI.
- Quý thiếu được để trống, không thay bằng 0.
- Báo cáo phân biệt rõ dữ liệu Twitch với người xem từng giải.

### 4.6. Handoff

- Bàn giao biểu đồ và định nghĩa KPI cho Thành viên B.
- Bàn giao các cảnh báo về fan-out, độ phủ quốc gia và dữ liệu năm 2025 cho cả nhóm.

---

## 5. Ngày 2 - Mô hình dự báo và đánh giá

### 5.1. Mục tiêu

Xây dựng pipeline dự báo quỹ thưởng theo family-quý, so sánh mô hình với seasonal naive và xuất dữ liệu dự báo có thể kết nối Tableau.

### 5.2. Đầu vào

- `forecast_prize_quarterly.csv`.
- `forecast_readiness.csv`.
- `forecast_status.csv`.
- `forecast_baseline_predictions.csv`.
- `forecast_baseline_scores.csv`.
- Đặc tả `reports/ml_problem_spec.md` từ Ngày 1.

### 5.3. Giao thức mô hình

- Đơn vị: một `game_family` trong một quý.
- Target chính: `target_prize_pool_usd`.
- Target độ nhạy: `strict_target_prize_pool_usd`.
- Train: đến hết 2023Q4.
- Validation: 2024Q1-2024Q4.
- Test: 2025Q1-2025Q4.
- Giao thức: rolling one-step, cùng giao thức với seasonal naive.

### 5.4. Feature hợp lệ

- `lag_1`, `lag_2`, `lag_4` của target.
- Trung bình, trung vị và độ lệch chuẩn của bốn quý trước, sau `shift(1)`.
- Quý trong năm.
- Chỉ số thời gian.
- `game_family` nếu dùng mô hình gộp.

### 5.5. Feature bị cấm

- `pool_cents` và `strict_pool_cents` của quý hiện tại.
- `observed_tournament_count` và `strict_count` của quý hiện tại.
- Tiền placements cùng quý.
- Twitch của cùng hoặc tương lai quý nếu chưa quan sát tại forecast origin.
- Bất kỳ feature rolling nào chưa `shift(1)`.

### 5.6. Công việc

#### Buổi sáng - Pipeline feature và baseline

- Đọc release mới nhất bằng đường dẫn tương đối.
- Kiểm tra lưới quý liên tục từ kỳ quan sát đầu tiên.
- Tạo lag và rolling feature không leakage.
- Tái tính seasonal naive `t-4` để đối chiếu file baseline.

#### Buổi chiều - Huấn luyện

- Linear Regression làm mô hình giải thích.
- Random Forest Regressor làm mô hình phi tuyến đối chuẩn.
- Chọn siêu tham số trên validation, không xem test để chọn cấu hình.
- Chạy lại với target strict như phân tích độ nhạy riêng.

#### Buổi tối - Đánh giá và xuất kết quả

- Tính MAE và RMSE theo family và tổng hợp theo số kỳ quan sát.
- R² chỉ là chỉ số bổ sung; không nhấn mạnh khi tập test quá nhỏ.
- Vẽ Actual vs Predicted, so sánh mô hình, residual và feature importance.
- Ghi lại số kỳ test thực sự được đánh giá.

### 5.7. Chính sách test thiếu

- Counter-Strike và Dota 2: báo cáo đủ bốn quý nhưng vẫn ghi độ phủ nguồn chưa xác minh.
- League of Legends: báo cáo partial test với ba quý, không gọi là full-year score.
- Valorant: báo cáo partial test với hai quý, chỉ mang tính chẩn đoán.
- Không đổi mốc test sau khi đã nhìn kết quả.
- Không nội suy hoặc điền 0 để làm đẹp metrics.

### 5.8. Đầu ra

- `src/model.py`.
- `reports/model_metrics.csv`.
- `reports/model_predictions.csv`.
- `reports/model_feature_importance.csv`.
- `reports/model_quality_sensitivity.csv`.
- `reports/model_evaluation_notes.md`.
- `reports/figures/model_actual_vs_predicted.png`.
- `reports/figures/model_performance_comparison.png`.
- `reports/figures/model_feature_importance.png`.
- `reports/figures/model_residuals.png`.

### 5.9. Tiêu chí hoàn thành

- Kết quả chạy lại được với một lệnh.
- Không có leakage trong danh sách feature.
- Baseline và các mô hình dùng cùng forecast protocol.
- Metrics ghi rõ family, split, số quan sát và target policy.
- File predictions có khóa family-quý duy nhất.
- Mọi kết luận dựa trên số liệu thực chạy, không dùng R² dự kiến trong đề cương.

### 5.10. Commit đề xuất

`feat(model): add quarterly prize forecasting benchmarks`

---

## 6. Ngày 3 - Storytelling và bàn giao Tableau

### 6.1. Mục tiêu

Chuyển EDA và kết quả mô hình thành các câu chuyện có thể kiểm chứng, xuất bảng dùng trực tiếp trong Tableau và hướng dẫn Thành viên B tích hợp đúng grain.

### 6.2. Ba câu chuyện phù hợp dữ liệu hiện tại

#### Câu chuyện 1 - Cấu trúc và tính mùa vụ của quỹ thưởng

- So sánh tổng quỹ thưởng giữa bốn family.
- Làm rõ các quý đột biến của Dota 2.
- Phân biệt xu hướng thị trường với độ phủ nguồn năm 2025.

#### Câu chuyện 2 - Sự lệch pha giữa sự chú ý trên Twitch và quỹ thưởng

- So sánh giờ xem Twitch với quỹ thưởng theo family-tháng.
- Nêu Dota 2 có tương quan mô tả cao hơn các family khác.
- Không kết luận tiền thưởng gây ra lượng người xem.

#### Câu chuyện 3 - Phân bố tiền thưởng theo quốc gia tuyển thủ

- Chỉ dùng các bảng quốc gia đã đối chiếu.
- Hiển thị `country_money_coverage_pct` cùng bản đồ.
- Không gọi là quốc gia khán giả hoặc toàn bộ thị trường.

### 6.3. Khuyến nghị kinh doanh được phép

- Dùng thuật ngữ `tín hiệu ưu tiên tài trợ` hoặc `khuyến nghị phân bổ thử nghiệm`.
- Ưu tiên các family có quy mô khán giả ổn định và sai số dự báo chấp nhận được.
- Đề xuất kiểm tra độ phủ và rủi ro dữ liệu trước khi đầu tư.
- Không tính hoặc tuyên bố ROI vì dữ liệu chưa có doanh thu, chi phí tài trợ và lợi nhuận.

### 6.4. Công việc

#### Buổi sáng - Error analysis và insight

- Phân tích các quý mô hình dự báo sai lớn.
- Kiểm tra sai số có tập trung ở quý đột biến hay family cụ thể.
- Viết ba insight với bằng chứng, giới hạn và hàm ý hành động.

#### Buổi chiều - Tableau export

- Tạo bảng dự báo với grain `game_family + quarter`.
- Bao gồm actual, predicted, residual, split, model và target policy.
- Tạo bảng summary family-level cho KPI.
- Không join prediction vào placements hoặc country rows.

#### Buổi tối - Handoff và nội dung báo cáo

- Viết hướng dẫn relationship trong Tableau.
- Chỉ định biểu đồ Actual vs Predicted, trendline và tooltip.
- Bàn giao field definitions và cảnh báo aggregation cho Thành viên B.

### 6.5. Đầu ra

- `reports/storytelling_insights.md`.
- `reports/tableau_forecast_handoff.md`.
- `data/processed/tableau_forecast_predictions.csv`.
- `data/processed/tableau_forecast_summary.csv`.
- Phần diễn giải mô hình hoàn chỉnh trong Chương 5.

### 6.6. Tiêu chí hoàn thành

- Mỗi insight có số liệu, biểu đồ, giới hạn và hành động đề xuất.
- Tableau export không trùng khóa ở grain đã công bố.
- Tổng actual trong export đối chiếu được với bảng quý nguồn.
- Không có từ ngữ nhân quả hoặc ROI không được hỗ trợ.
- Thành viên B có thể dựng sheet dự báo mà không cần join một-nhiều.

### 6.7. Commit đề xuất

`feat(storytelling): add forecast insights and Tableau handoff`

---

## 7. Ngày 4 - Báo cáo, demo và bảo vệ

### 7.1. Mục tiêu

Hoàn thiện phần tài liệu do Thành viên C phụ trách, kiểm tra tính nhất quán giữa code, dashboard và báo cáo, đồng thời chuẩn bị nội dung demo và vấn đáp.

### 7.2. Công việc

#### Buổi sáng - Hoàn thiện Chương 5

- Trình bày bài toán, target, split và forecast protocol.
- Viết công thức Linear Regression và giải thích Random Forest.
- Chèn bảng MAE/RMSE và số kỳ đánh giá.
- Chèn Actual vs Predicted, feature importance và residual analysis.
- Viết hạn chế test 2025 và phân tích strict-quality.

#### Buổi trưa - Chương 6 và 7

- Hướng dẫn tạo môi trường và chạy EDA/model.
- Hướng dẫn mở Tableau và kiểm tra nguồn dữ liệu.
- Viết kết luận, đóng góp, giới hạn và hướng mở rộng.
- Kiểm tra tài liệu tham khảo và chú thích hình/bảng.

#### Buổi chiều - Kịch bản demo

- Viết kịch bản 3-5 phút theo luồng: vấn đề, dashboard, dự báo, insight, giới hạn.
- Phân vai lời thoại cho A, B và C.
- Ghi rõ thao tác filter, drill-down, map và sheet dự báo.
- Chuẩn bị phương án khi Tableau hoặc mạng gặp lỗi.

#### Buổi tối - FAQ và kiểm tra release

- Soạn câu hỏi về fan-out, missing, strict-quality, temporal split và leakage.
- Giải thích vì sao không hứa R² và không dùng MAPE làm chỉ số chính.
- Tổ chức mock defense và ghi lại câu trả lời chưa thống nhất.
- Kiểm tra tên file, đường dẫn tương đối, figures, metrics và README.

### 7.3. Đầu ra

- `reports/chapters/ch5_modeling.md`.
- `reports/chapters/ch6_implementation.md`.
- `reports/chapters/ch7_conclusion.md`.
- `demo/video_script.md`.
- `demo/defense_faq.md`.
- `reports/final_integration_checklist.md`.
- Bản nội dung sẵn sàng ghép vào báo cáo IEEE cuối.

### 7.4. Tiêu chí hoàn thành

- Mọi con số trong báo cáo truy ngược được về CSV kết quả.
- Không còn placeholder hoặc metrics dự kiến.
- Hình/bảng có số thứ tự, caption, đơn vị và nguồn.
- Demo nằm trong 3-5 phút và có phương án backup.
- FAQ có câu trả lời cho cả dữ liệu, Tableau và mô hình.
- Không merge trực tiếp vào `main`; gửi PR và chờ review chéo.

### 7.5. Commit đề xuất

`docs(report): add modeling chapters demo script and defense FAQ`

---

## 8. Handoff giữa các thành viên

### Thành viên A cần cung cấp cho C

- Release path chính thức.
- Chính sách quality và missing cuối cùng.
- Xác nhận có bổ sung nguồn 2025 hay không.
- Data dictionary và thay đổi schema nếu có.

### C cần cung cấp cho Thành viên B

- Predictions ở grain family-quý.
- Định nghĩa actual, predicted, residual và target policy.
- Hướng dẫn aggregation và relationship.
- Danh sách quý bị thiếu và nhãn cảnh báo.

### C cần nhận lại từ Thành viên B

- Ảnh chụp dashboard và sheet dự báo.
- Tên filter, parameter và action cuối cùng.
- Link Tableau Public hoặc file `.twbx` để viết Chương 6 và kịch bản demo.

## 9. Definition of Done toàn bộ phần Thành viên C

- EDA và mô hình đều chạy lại được từ README.
- Có baseline, Linear Regression và Random Forest.
- Metrics dùng cùng split và forecast protocol.
- Có phân tích độ nhạy quality policy.
- Tableau nhận được bảng dự báo đúng grain.
- Chương 5-7 không có số liệu dự kiến hoặc tuyên bố vượt quá dữ liệu.
- Kịch bản demo và FAQ đã được cả nhóm review.
- Tất cả thay đổi được đưa qua Pull Request và review chéo trước khi merge.

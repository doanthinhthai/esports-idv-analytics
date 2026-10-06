# FINAL INTEGRATION CHECKLIST

## 1. Phần Thành viên C đã hoàn thành

| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| EDA chạy lại được | PASS | `src/eda.py`, `reports/eda_summary.csv`, năm hình EDA |
| Mô hình chạy lại được | PASS | `src/model.py`, predictions, metrics và bốn hình model |
| Không dùng feature cùng quý | PASS | Feature list chỉ gồm lag, rolling đã shift, time, quarter và family |
| Baseline cùng forecast protocol | PASS | Seasonal Naive và model đều rolling one-step |
| Missing test không thành 0 | PASS | Ba prediction-only rows có actual và residual là null |
| Tableau prediction export | PASS | 192 dòng, khóa family–quarter–policy–model duy nhất |
| Tableau summary export | PASS | 60 dòng, metrics khớp model output |
| Storytelling | PASS | Ba câu chuyện, error analysis, giới hạn và hành động |
| Chương 5 | PASS | `reports/chapters/ch5_modeling.md` |
| Chương 6 phần triển khai code | PASS | `reports/chapters/ch6_implementation.md` |
| Chương 7 | PASS | `reports/chapters/ch7_conclusion.md` |
| Kịch bản demo | PASS | `demo/video_script.md`, mục tiêu 4 phút |
| FAQ bảo vệ | PASS | `demo/defense_faq.md`, 30 câu hỏi |
| Kiểm tra tự động | PASS khi script trả mã 0 | `src/validate_deliverables.py` |

Kết quả chạy gần nhất nằm trong `reports/final_validation_results.csv` và `reports/final_validation_summary.md`.

## 2. Mục cần Thành viên B bàn giao

| Hạng mục | Trạng thái | Điều kiện hoàn thành |
|---|---|---|
| Tableau workbook | WAITING FOR B | Nhận `.twbx` hoặc link Tableau Public |
| Tên worksheet cuối | WAITING FOR B | Đối chiếu với các chức năng Trend, Twitch, Country Map và Forecast |
| Ảnh dashboard | WAITING FOR B | Ảnh đúng phiên bản workbook dùng khi nộp |
| Filter và action | WAITING FOR B | Danh sách tên, giá trị mặc định và phạm vi tác động |
| QA forecast sheet | WAITING FOR B | `source + random_forest + test` có 16 dòng, 13 evaluated |
| QA aggregation | WAITING FOR B | Actual không bị nhân khi đổi model hoặc tương tác country |
| Kịch bản thao tác cuối | WAITING FOR B | Thay tên chức năng bằng tên sheet thật và chạy thử dưới 4 phút 20 giây |

Các mục này không ngăn việc hoàn thiện code, Chương 5, Chương 7 hoặc FAQ. Chúng ngăn việc khóa Chương 6, quay video cuối và merge release cuối.

## 3. Kiểm tra trước khi gửi PR

- [x] Nhánh chức năng không merge trực tiếp vào `main`.
- [x] Ngày 1, Ngày 2 và Ngày 3 dùng nhánh theo chức năng.
- [x] Mọi con số mô hình lấy từ CSV kết quả.
- [x] Không tuyên bố correlation là causality.
- [x] Không tuyên bố ROI.
- [x] Source target và strict-quality được phân biệt.
- [x] Figure có caption/đơn vị và file 300 DPI.
- [x] README có thứ tự chạy pipeline.
- [ ] Nhận review chéo từ Thành viên A về release và source coverage 2025.
- [ ] Nhận review chéo từ Thành viên B về Tableau grain và aggregation.
- [ ] Chạy lại validation sau khi thêm `.twbx`, ảnh và link cuối.

## 4. Kiểm tra trước khi nộp

- [ ] Khóa analysis release chính thức.
- [ ] Chạy EDA, model, storytelling và validation từ môi trường sạch.
- [ ] So sánh KPI Tableau với `tableau_forecast_summary.csv`.
- [ ] Mở `.twbx` trên máy thứ hai hoặc tài khoản khác.
- [ ] Kiểm tra link Tableau Public nếu dùng.
- [ ] Kiểm tra video 3–5 phút, âm thanh và độ phân giải.
- [ ] Lưu ảnh backup cục bộ.
- [ ] Kiểm tra báo cáo không còn nội dung chờ Thành viên B.
- [ ] Tạo PR vào `develop` và chờ review.

## 5. Điều kiện Definition of Done cuối

Phần Thành viên C chỉ được gọi là tích hợp hoàn toàn khi automated validation PASS, Thành viên B xác nhận Tableau không cộng trùng, các tài sản dashboard đã được chèn vào Chương 6 và kịch bản demo đã chạy thử với workbook cuối.

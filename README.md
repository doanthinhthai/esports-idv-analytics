```text

esports-idv-analytics/

├── data/

│   ├── raw/                  # 3 bảng dữ liệu thô ban đầu

│   ├── processed/            # Dữ liệu sạch xuất cho Tableau \& ML

│   └── dictionary/           # Từ điển dữ liệu \& sơ đồ ERD

├── src/                      # Mã nguồn Python tiền xử lý và mô hình ML

├── tableau/                  # File Tableau Packaged Workbook (.twbx)

├── reports/                  # Bản thảo báo cáo IEEE theo từng chương

└── demo/                     # Kịch bản demo và link video backup

```

## Chạy EDA cho analysis release

Tạo môi trường Python, cài thư viện và chạy:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python src\eda.py
```

`src/eda.py` tự chọn thư mục `data/processed/analysis_release_v1_*` mới nhất, kiểm tra khóa và đối chiếu tổng theo quý, sau đó tạo:

- `reports/eda_summary.csv`.
- Năm biểu đồ PNG 300 DPI trong `reports/figures/`.
- Các biểu đồ giữ nguyên quý thiếu và ghi rõ giới hạn độ phủ nguồn năm 2025.

Không dùng các bảng processed cũ nằm ngoài analysis release cho EDA này.

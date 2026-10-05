# DATA DICTIONARY

## 1. Phạm vi

- Thời gian: ngày bắt đầu giải trong 2012–2025.
- Nhóm game: Counter-Strike, Dota 2, League of Legends, Valorant.
- Counter-Strike gồm CS:GO và CS2, giữ riêng phiên bản.
- Nguồn: Esports Earnings và Esports Charts.
- Dữ liệu thiếu giữ null, không tự thay bằng 0.

## 2. Quy ước trạng thái

- EXTRACTED: parser/pipeline đã tạo trường.
- CONFIGURED: có trong cấu hình.
- DERIVED: cần tạo khi chuẩn hóa.
- NOT_COLLECTED: chưa được crawler hiện tại thu thập.

EXTRACTED không có nghĩa mọi bản ghi đều đầy đủ hoặc đã xác minh.

ID nguồn giữ dạng string.
Ngày giải dùng YYYY-MM-DD.
Thời điểm kỹ thuật dùng ISO 8601 UTC.
Tiền thưởng USD có độ chính xác đến cent.
Tên raw được giữ để đối chiếu.

## 3. Thông tin giải — cấu trúc hiện tại

Một dòng đại diện cho một giải của một game tại nguồn Earnings.

| Trường | Kiểu / đơn vị | Ý nghĩa | Trạng thái |
|---|---|---|---|
| source_site | string | Tên nguồn | EXTRACTED |
| source_url | string / URL | Trang giải tại nguồn | EXTRACTED |
| source_tournament_id | string | ID giải Earnings | EXTRACTED |
| tournament_name_raw | string | Tên giải nguyên gốc | EXTRACTED |
| location_raw | string, nullable | Địa điểm nguyên gốc | EXTRACTED |
| date_raw | string | Chuỗi ngày nguyên gốc | EXTRACTED |
| start_date | date | Ngày bắt đầu giải | EXTRACTED |
| end_date | date | Ngày kết thúc giải | EXTRACTED |
| game_name_raw | string | Tên game trên trang nguồn | EXTRACTED |
| source_game_id | string | ID game Earnings | EXTRACTED |
| game_source_url | string / URL, nullable | Trang game tại nguồn | EXTRACTED |
| prize_pool_raw | string | Quỹ thưởng nguyên gốc | EXTRACTED |
| prize_pool_usd | number / USD | Quỹ thưởng USD được nguồn cung cấp | EXTRACTED |
| currency_raw | string | Tiền tệ nguyên gốc | EXTRACTED |
| source_html_file | string | Đường dẫn HTML phục vụ đối chiếu | EXTRACTED |
| parsed_at | timestamp UTC | Thời điểm parse | EXTRACTED |
| game_id | string | ID phiên bản game nội bộ | EXTRACTED |
| game_slug | string | Slug phiên bản game | EXTRACTED |
| crawled_at | timestamp UTC | Thời điểm tải HTML | EXTRACTED |
| placements_status | string | Trạng thái trích xuất/đối chiếu kết quả | EXTRACTED |

Lưu ý:

- prize_pool_usd không được cộng sau join một giải với nhiều placements.
- location_raw chưa phải mã quốc gia chuẩn.
- Một giải có thông tin nhưng không có placements vẫn được giữ lại.
- Không suy ra phiên bản game chỉ bằng năm.

## 4. Kết quả đội — cấu trúc hiện tại

Một dòng đại diện cho một kết quả đội tại một giải.

Parser hiện tại lấy kết quả đội, chưa được coi là parser đầy đủ
cho mọi dạng kết quả cá nhân.

| Trường | Kiểu / đơn vị | Ý nghĩa | Trạng thái |
|---|---|---|---|
| source_site | string | Tên nguồn | EXTRACTED |
| source_url | string / URL | Trang giải | EXTRACTED |
| source_tournament_id | string | ID giải Earnings | EXTRACTED |
| source_team_id | string, nullable | ID đội nếu nguồn có liên kết | EXTRACTED |
| team_name_raw | string | Tên đội nguyên gốc | EXTRACTED |
| team_source_url | string / URL, nullable | Trang đội tại nguồn | EXTRACTED |
| rank_raw | string | Hạng hoặc nhãn kết quả nguyên gốc | EXTRACTED |
| rank_min | integer, nullable | Đầu khoảng hạng | EXTRACTED |
| rank_max | integer, nullable | Cuối khoảng hạng | EXTRACTED |
| result_outcome | string, nullable | WIN/LOSE khi nguồn dùng nhãn này | EXTRACTED |
| prize_money_raw | string | Tiền thưởng nguyên gốc của đội | EXTRACTED |
| prize_money_usd | number / USD | Tiền thưởng của đội tính bằng USD | EXTRACTED |
| source_html_file | string | Đường dẫn HTML | EXTRACTED |
| parsed_at | timestamp UTC | Thời điểm parse | EXTRACTED |
| game_id | string | ID game nội bộ | EXTRACTED |
| game_slug | string | Slug game | EXTRACTED |
| crawled_at | timestamp UTC | Thời điểm tải HTML | EXTRACTED |
| validation_status | string | Trạng thái đối chiếu tiền thưởng | EXTRACTED |

Lưu ý:

- 3rd–4th được giữ thành rank_min=3, rank_max=4.
- Không tự đổi WIN/LOSE thành thứ hạng số.
- Thiếu source_team_id không đồng nghĩa tên đội không hợp lệ.
- Tên đội giống nhau chưa đủ để chứng minh cùng một đội.
- Không cộng tiền thưởng đội với tiền thưởng người chơi
  nếu đó là cùng khoản thưởng.

## 5. Trạng thái chất lượng

| Trạng thái | Ý nghĩa |
|---|---|
| matched | Tổng tiền thưởng trích xuất khớp quỹ thưởng |
| rounding_difference | Chênh lệch khác 0 và không quá 0.02 USD theo quy tắc hiện tại |
| needs_review | Chênh lệch vượt ngưỡng cần đối chiếu |
| tournament_only | Có thông tin giải nhưng chưa có kết quả đội hợp lệ |
| failed | Chưa xử lý được thông tin giải |

matched chỉ xác nhận phép đối chiếu tiền thưởng.
rounding_difference không tự chứng minh nguyên nhân là làm tròn.

## 6. Trường chuẩn hóa cần tạo

| Trường | Ý nghĩa | Trạng thái |
|---|---|---|
| tournament_id | ID giải nội bộ ổn định để liên kết nguồn | DERIVED |
| tournament_name | Tên giải chuẩn, giữ tên raw riêng | DERIVED |
| game_family | Nhóm game để phân tích | CONFIGURED |
| game_version | Phiên bản game, suy từ ánh xạ đã xác minh | DERIVED |
| host_country_code | Mã quốc gia tổ chức nếu xác minh được | DERIVED |
| event_mode | Online/LAN/Hybrid nếu xác minh được | DERIVED |
| placement_id | ID kết quả nội bộ ổn định | DERIVED |
| team_id | ID đội nội bộ sau đối chiếu | DERIVED |
| crosses_year | Giải có ngày bắt đầu/kết thúc khác năm | DERIVED |

Không đoán host_country_code hoặc event_mode từ thông tin không đủ rõ.

## 7. Dữ liệu khu vực cần thu thập

| Trường | Ý nghĩa | Trạng thái |
|---|---|---|
| source_player_id | ID người chơi tại nguồn | NOT_COLLECTED |
| player_id | ID người chơi nội bộ | DERIVED |
| player_name_raw | Tên/handle nguyên gốc | NOT_COLLECTED |
| player_country_code | Quốc gia người chơi theo nguồn | NOT_COLLECTED |
| team_id_at_event | Đội tại thời điểm giải nếu xác minh được | NOT_COLLECTED |
| player_prize_money_usd | Tiền thưởng người chơi tại giải | NOT_COLLECTED |
| region | Nhóm khu vực từ bảng ánh xạ quốc gia | DERIVED |

Quy tắc:

- Tiền thưởng phải gắn với giải để lọc đúng 2012–2025.
- Không dùng thu nhập mọi thời đại thay cho tiền thưởng trong phạm vi.
- Ghi rõ độ phủ quốc gia và giới hạn lịch sử thuộc tính này.
- Không dùng quốc gia tổ chức giải làm quốc gia người chiến thắng.
- Không dùng roster hiện tại để suy ra roster lịch sử.
- Country-to-region mapping phải được lưu và dùng thống nhất.

## 8. Dữ liệu người xem cần thu thập

| Trường | Kiểu / đơn vị | Ý nghĩa | Trạng thái |
|---|---|---|---|
| source_event_id | string | ID sự kiện Charts nếu nguồn cung cấp | NOT_COLLECTED |
| source_url | URL | Trang thống kê | NOT_COLLECTED |
| event_name_raw | string | Tên sự kiện nguyên gốc | NOT_COLLECTED |
| start_date | date | Ngày bắt đầu tại nguồn Charts | NOT_COLLECTED |
| end_date | date | Ngày kết thúc tại nguồn Charts | NOT_COLLECTED |
| peak_viewers | number / viewers | Đỉnh người xem đồng thời | NOT_COLLECTED |
| average_viewers | number / viewers | Người xem đồng thời trung bình | NOT_COLLECTED |
| hours_watched | number / viewer-hours | Tổng giờ xem | NOT_COLLECTED |
| airtime_hours | number / hours | Thời lượng phát sóng | NOT_COLLECTED |
| measurement_scope | string | Phạm vi nền tảng/đo lường của số liệu | NOT_COLLECTED |
| crawled_at | timestamp UTC | Thời điểm thu thập | NOT_COLLECTED |

Quy tắc:

- Không đảm bảo mọi trường đều công khai ở mọi giải.
- Thiếu dữ liệu người xem không được điền 0.
- Không cộng peak viewers thành người xem duy nhất.
- Ghi rõ giới hạn nền tảng và độ phủ nguồn.
- Không lặp số liệu cả sự kiện cho nhiều giải thành phần rồi cộng.

## 9. Liên kết nguồn

Bảng source_mapping cần lưu:

- tournament_id.
- source_site.
- source_event_id.
- source_url.
- match_status.
- match_method.
- verified_at.
- notes.

Trạng thái:

- verified_match.
- candidate_match.
- unmatched.
- rejected_match.

Đối chiếu tên, game/phiên bản, ngày, mùa và phạm vi.
Ghép gần đúng chỉ tạo ứng viên, không tự xác nhận.

## 10. Điều kiện sẵn sàng cho EDA

- [ ] Có dữ liệu 4 nhóm game.
- [ ] Trên 5.000 placements sạch sau lọc và loại trùng.
- [ ] Không trùng khóa chính.
- [ ] Khóa ngoại hợp lệ.
- [ ] Có thống kê độ phủ theo game/năm/nguồn.
- [ ] Có kiểm tra tiền thưởng và ngày.
- [ ] Có dữ liệu hỗ trợ phân tích khu vực.
- [ ] Có tập người xem với độ phủ được công khai.
- [ ] Có source mapping được kiểm tra.
- [ ] Có danh sách lỗi và hạn chế.
- [ ] Có snapshot cố định để bàn giao nhóm.
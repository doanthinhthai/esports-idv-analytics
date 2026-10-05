# DATA DICTIONARY (TỪ ĐIỂN DỮ LIỆU DỰ ÁN E-SPORTS ANALYTICS)

## 1. dim_games (20 tựa game)
- **Game_ID** (PK): Mã định danh game (G_01...).
- **Game_Title**: Tên tựa game (League of Legends, Dota 2, CS2...).
- **Genre**: Thể loại (MOBA, Tactical FPS, Battle Royale...).
- **Publisher**: Nhà phát hành (Riot Games, Valve, Krafton...).
- **Platform**: Nền tảng (PC, Mobile).

## 2. dim_teams_regions (177 đội tuyển)
- **Team_ID** (PK): Mã đội tuyển (TM_00001...).
- **Team_Name**: Tên đội (T1, Gen.G, Team Liquid...).
- **Country_ISO_Code**: Mã ISO-3 quốc gia (KOR, USA, VNM) - *Dùng vẽ Map Tableau*.
- **Region**: Khu vực địa lý (East Asia, Europe, North America, Southeast Asia).
- **Primary_Game_ID** (FK): Khóa ngoại trỏ về `dim_games`.

## 3. fact_tournaments_clean (5,500 giải đấu sạch)
- **Tournament_ID** (PK): Mã giải đấu (TN_0001...).
- **Game_ID** (FK): Khóa ngoại trỏ về `dim_games`.
- **Winning_Team_ID** (FK): Khóa ngoại trỏ về `dim_teams_regions`.
- **Year / Month**: Năm và tháng tổ chức.
- **Duration_Days**: Thời lượng giải (ngày).
- **Tier**: Cấp độ giải (Tier 1: S-Tier, Tier 2: A-Tier...).
- **Host_Country_ISO**: Mã ISO-3 quốc gia đăng cai.
- **Prize_Pool_Cleaned**: Tổng tiền thưởng thực tế đã làm sạch (USD).
- **Prize_Pool_Capped**: Tiền thưởng sau Winsorization (dành cho Machine Learning).
- **Peak_Viewers**: Lượng người xem đỉnh điểm.
- **Average_Viewers**: Lượng người xem trung bình.
- **Prize_Per_Viewer_Ratio**: Tỷ lệ chi phí giải thưởng trên mỗi lượt xem ($/Viewer).
- **Audience_Retention_Rate**: Tỷ lệ giữ chân người xem (%).
- **Daily_Hours_Watched**: Số giờ xem trung bình mỗi ngày.

## 4. fact_tournament_placements (36,580 kết quả)
- **Placement_ID** (PK): Mã thứ vị.
- **Tournament_ID** (FK), **Team_ID** (FK).
- **Rank**: Thứ vị đạt được (1: Vô địch, 2: Á quân...).
- **Prize_Money_USD**: Tiền thưởng thực nhận.

## 5. fact_viewership_breakdown (25,806 lượt xem)
- **Breakdown_ID** (PK): Mã phân bổ view.
- **Tournament_ID** (FK).
- **Platform**: Nền tảng phát sóng (Twitch, YouTube, TikTok...).
- **Broadcast_Language**: Ngôn ngữ bình luận (English, Korean, Vietnamese...).
- **Platform_Peak_Viewers**: Lượng người xem đỉnh theo nền tảng.
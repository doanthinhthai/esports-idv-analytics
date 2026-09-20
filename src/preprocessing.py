# -*- coding: utf-8 -*-
import sys
import os
import pandas as pd

# Thêm đường dẫn để import các module con trong src/cleaning
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cleaning.clean_games import clean_games
from cleaning.clean_teams import clean_teams
from cleaning.clean_players import clean_players
from cleaning.clean_tournaments import clean_tournaments
from cleaning.clean_placements import clean_placements
from cleaning.clean_viewership import clean_viewership

def run_pipeline():
    print("=" * 70)
    print("KHỞI ĐỘNG PIPELINE MODULAR LÀM SẠCH 6 BẢNG DỮ LIỆU E-SPORTS")
    print("=" * 70)

    # 1. Làm sạch các bảng danh mục Dimension
    df_games       = clean_games()
    df_teams       = clean_teams(df_games)
    df_players     = clean_players(df_games, df_teams)

    # 2. Làm sạch các bảng sự kiện Fact
    df_tournaments = clean_tournaments(df_games, df_teams)
    df_placements  = clean_placements(df_tournaments, df_teams)
    df_viewership  = clean_viewership(df_tournaments)

    # 3. Báo cáo tổng kết toàn hệ thống
    total_rows = sum([len(df_games), len(df_teams), len(df_players), 
                      len(df_tournaments), len(df_placements), len(df_viewership)])
    print("=" * 70)
    print(f"Tổng cộng: {total_rows:,} dòng dữ liệu đã được làm sạch và kiểm định.")
    print("=" * 70)

if __name__ == "__main__":
    run_pipeline()
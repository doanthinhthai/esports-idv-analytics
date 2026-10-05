import os
import pandas as pd

PROCESSED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "processed")

def clean_players(df_games: pd.DataFrame = None, df_teams: pd.DataFrame = None) -> pd.DataFrame:
    if df_games is None: df_games = pd.read_csv(os.path.join(PROCESSED_DIR, "dim_games.csv"))
    if df_teams is None: df_teams = pd.read_csv(os.path.join(PROCESSED_DIR, "dim_teams_regions.csv"))
    
    path = os.path.join(PROCESSED_DIR, "dim_players.csv")
    df = pd.read_csv(path).drop_duplicates(subset=["Player_ID"])
    df["Real_Name"] = df["Real_Name"].fillna("Anonymous / Pro Athlete").str.strip()
    df["Total_Prize_USD"] = df["Total_Prize_USD"].clip(lower=0.0).round(2)
    assert df["Primary_Game_ID"].isin(df_games["Game_ID"]).all(), "Lỗi khóa Player -> Game!"
    assert df["Current_Team_ID"].isin(df_teams["Team_ID"]).all(), "Lỗi khóa Player -> Team!"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"dim_players: Đã làm sạch {len(df):,} tuyển thủ.")
    return df

if __name__ == "__main__":
    clean_players()
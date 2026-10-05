import os
import pandas as pd

PROCESSED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "processed")

def clean_teams(df_games: pd.DataFrame = None) -> pd.DataFrame:
    if df_games is None:
        df_games = pd.read_csv(os.path.join(PROCESSED_DIR, "dim_games.csv"))
    path = os.path.join(PROCESSED_DIR, "dim_teams_regions.csv")
    df = pd.read_csv(path).drop_duplicates(subset=["Team_ID"])
    df["Country_ISO_Code"] = df["Country_ISO_Code"].str.strip().str.upper()
    assert df["Primary_Game_ID"].isin(df_games["Game_ID"]).all(), "Lỗi khóa ngoại Primary_Game_ID!"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"dim_teams_regions: Đã làm sạch {len(df)} đội tuyển.")
    return df

if __name__ == "__main__":
    clean_teams()
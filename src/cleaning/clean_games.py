import os
import pandas as pd

PROCESSED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "processed")

def clean_games() -> pd.DataFrame:
    path = os.path.join(PROCESSED_DIR, "dim_games.csv")
    df = pd.read_csv(path).drop_duplicates(subset=["Game_ID"])
    df["Game_Title"] = df["Game_Title"].str.strip()
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"dim_games: Đã làm sạch {len(df)} tựa game.")
    return df

if __name__ == "__main__":
    clean_games()
import os
import pandas as pd

PROCESSED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "processed")

def clean_placements(df_tournaments: pd.DataFrame = None, df_teams: pd.DataFrame = None) -> pd.DataFrame:
    if df_tournaments is None: df_tournaments = pd.read_csv(os.path.join(PROCESSED_DIR, "fact_tournaments.csv"))
    if df_teams is None: df_teams = pd.read_csv(os.path.join(PROCESSED_DIR, "dim_teams_regions.csv"))

    path = os.path.join(PROCESSED_DIR, "fact_tournament_placements.csv")
    df = pd.read_csv(path).drop_duplicates(subset=["Placement_ID"])
    df["Prize_Money_USD"] = df["Prize_Money_USD"].clip(lower=0.0).round(2)
    assert df["Tournament_ID"].isin(df_tournaments["Tournament_ID"]).all(), "Lỗi khóa Placement -> Tournament!"
    assert df["Team_ID"].isin(df_teams["Team_ID"]).all(), "Lỗi khóa Placement -> Team!"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"fact_tournament_placements: Đã làm sạch {len(df):,} kết quả giải đấu.")
    return df

if __name__ == "__main__":
    clean_placements()
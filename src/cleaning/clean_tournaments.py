import os
import numpy as np
import pandas as pd

PROCESSED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "processed")

def clean_tournaments(df_games: pd.DataFrame = None, df_teams: pd.DataFrame = None) -> pd.DataFrame:
    if df_games is None: df_games = pd.read_csv(os.path.join(PROCESSED_DIR, "dim_games.csv"))
    if df_teams is None: df_teams = pd.read_csv(os.path.join(PROCESSED_DIR, "dim_teams_regions.csv"))

    raw_path = os.path.join(PROCESSED_DIR, "fact_tournaments.csv")
    df = pd.read_csv(raw_path).drop_duplicates(subset=["Tournament_ID"])
    df["Host_City"] = df["Host_City"].fillna("Online / TBD")
    df["Prize_Pool_Cleaned"] = df["Prize_Pool_USD"].astype(float)

    # IQR Outlier Capping (Winsorization)
    q1, q3 = df["Prize_Pool_Cleaned"].quantile(0.25), df["Prize_Pool_Cleaned"].quantile(0.75)
    iqr = q3 - q1
    df["Prize_Pool_Capped"] = np.clip(df["Prize_Pool_Cleaned"], max(0.0, q1 - 1.5 * iqr), q3 + 1.5 * iqr)

    # 3 KPIs phái sinh
    df["Prize_Per_Viewer_Ratio"] = (df["Prize_Pool_Cleaned"] / df["Peak_Viewers"]).round(4)
    df["Audience_Retention_Rate"] = ((df["Average_Viewers"] / df["Peak_Viewers"]) * 100).round(2)
    df["Daily_Hours_Watched"] = ((df["Hours_Watched_Thousands"] * 1000) / df["Duration_Days"].replace(0, 1)).round(2)

    assert df["Game_ID"].isin(df_games["Game_ID"]).all(), "Lỗi khóa Tournament -> Game!"
    assert df["Winning_Team_ID"].isin(df_teams["Team_ID"]).all(), "Lỗi khóa Tournament -> Team!"

    clean_path = os.path.join(PROCESSED_DIR, "fact_tournaments_clean.csv")
    df.to_csv(clean_path, index=False, encoding="utf-8-sig")
    print(f"fact_tournaments_clean: Đã làm sạch {len(df):,} giải đấu.")
    return df

if __name__ == "__main__":
    clean_tournaments()
import os
import pandas as pd

PROCESSED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "processed")

def clean_viewership(df_tournaments: pd.DataFrame = None) -> pd.DataFrame:
    if df_tournaments is None: df_tournaments = pd.read_csv(os.path.join(PROCESSED_DIR, "fact_tournaments.csv"))

    path = os.path.join(PROCESSED_DIR, "fact_viewership_breakdown.csv")
    df = pd.read_csv(path).drop_duplicates(subset=["Breakdown_ID"])
    df["Viewer_Share_Pct"] = df["Viewer_Share_Pct"].clip(lower=0.0, upper=100.0).round(2)
    assert df["Tournament_ID"].isin(df_tournaments["Tournament_ID"]).all(), "Lỗi khóa Viewership -> Tournament!"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"fact_viewership_breakdown: Đã làm sạch {len(df):,} lượt xem nền tảng.")
    return df

if __name__ == "__main__":
    clean_viewership()
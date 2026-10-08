"""Kiểm tra chống rò rỉ, quý thiếu, mốc năm và hợp đồng bàn giao Tableau."""

from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from phan_tich_esports.cau_hinh import FAMILIES
from phan_tich_esports.du_bao_danh_gia import (
    attach_actual, attach_intervals, evaluate_and_select, interval_radii, summarize_backtest,
)
from phan_tich_esports.du_bao_tuong_lai import TARGET, load_future_inputs, prepare_quarterly, recursive_forecast
from phan_tich_esports.du_bao_xuat import build_timeline, validate_future_export


def sample_data() -> pd.DataFrame:
    """Chuỗi kiểm thử nhân tạo, chỉ nằm trong test, không xuất sang Tableau."""
    rows = []
    for i, family in enumerate(FAMILIES, 1):
        for n, period in enumerate(pd.period_range("2020Q1", "2029Q4", freq="Q")):
            rows.append({"game_family": family, "quarter": str(period),
                         "period_start": period.start_time, TARGET: float(i * 1000 + n * 20 + period.quarter * 100)})
    return prepare_quarterly(pd.DataFrame(rows))


class ForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = sample_data()
        cls.origin = pd.Period("2028Q4", freq="Q")
        cls.predictions = recursive_forecast(cls.data, cls.origin)

    def test_no_future_actual_leakage(self):
        changed = self.data.copy()
        changed.loc[changed["period"] > self.origin, TARGET] = 1e12
        assert_frame_equal(self.predictions, recursive_forecast(changed, self.origin))

    def test_relative_year_and_four_quarters(self):
        self.assertEqual(len(self.predictions), 48)
        self.assertEqual(set(self.predictions["quarter"]), {"2029Q1", "2029Q2", "2029Q3", "2029Q4"})
        self.assertEqual(set(self.predictions["horizon_quarters"]), {1, 2, 3, 4})
        self.assertFalse(self.predictions.query("horizon_quarters == 1")["uses_recursive_predictions"].any())
        self.assertTrue(self.predictions.query("horizon_quarters > 1")["uses_recursive_predictions"].all())

    def test_missing_zero_and_seasonal_fallback(self):
        data = self.data.copy()
        mask = data["game_family"].eq("Valorant") & data["quarter"].eq("2028Q4")
        data.loc[mask, TARGET] = np.nan
        zero = data["game_family"].eq("Dota 2") & data["quarter"].eq("2028Q4")
        data.loc[zero, TARGET] = 0.0
        original = data.copy(deep=True)
        result = recursive_forecast(data, self.origin)
        assert_frame_equal(data, original)
        valorant = result.query("game_family == 'Valorant' and model == 'seasonal_naive'")
        self.assertTrue(valorant["missing_recent_quarters"].eq(1).all())
        self.assertTrue(valorant["last_observed_quarter"].eq("2028Q3").all())
        self.assertTrue(valorant.query("quarter == '2029Q4'")["seasonal_fallback_used"].all())
        dota = result.query("game_family == 'Dota 2' and model == 'seasonal_naive' and quarter == '2029Q4'")
        self.assertEqual(dota.iloc[0]["predicted_prize_pool_usd"], 0.0)
        self.assertFalse(dota.iloc[0]["seasonal_fallback_used"])

    def test_seasonal_recurrence_for_all_steps(self):
        source = self.data.set_index(["game_family", "quarter"])[TARGET]
        for row in self.predictions.query("model == 'seasonal_naive'").itertuples():
            expected = source.loc[row.game_family, str(pd.Period(row.quarter) - 4)]
            self.assertEqual(row.predicted_prize_pool_usd, expected)

    def test_next_step_uses_own_prediction(self):
        class PreviousQuarterPlusOne:
            def predict(self, frame):
                return frame["lag_1"].to_numpy() + 1

        fake = {name: PreviousQuarterPlusOne() for name in ["linear_regression", "random_forest"]}
        with patch("phan_tich_esports.du_bao_tuong_lai.fit_models", return_value=fake):
            result = recursive_forecast(self.data, self.origin)
        last_actual = self.data[self.data["period"].eq(self.origin)].set_index("game_family")[TARGET]
        for row in result.query("model == 'linear_regression'").itertuples():
            self.assertEqual(row.predicted_prize_pool_usd,
                             last_actual[row.game_family] + row.horizon_quarters)

    def test_holdout_not_used_to_select_model_or_intervals(self):
        # Dùng seasonal dự báo nhanh để kiểm tra ranh giới selection/holdout.
        def fast_forecast(data, origin):
            rows = []
            for model, label, factor in [("seasonal_naive", "Seasonal", 1),
                                          ("linear_regression", "Linear", 1.1),
                                          ("random_forest", "Forest", 0.9)]:
                history = data[data["period"] <= origin]
                for family, group in history.groupby("game_family"):
                    for h in range(1, 5):
                        rows.append({"game_family": family, "quarter": str(origin + h),
                                     "forecast_origin": str(origin), "horizon_quarters": h,
                                     "model": model, "model_label": label,
                                     "predicted_prize_pool_usd": group[TARGET].dropna().iloc[-1] * factor})
            return pd.DataFrame(rows)

        changed = self.data.copy()
        changed.loc[changed["period"] > self.origin - 4, TARGET] = 1e12
        with patch("phan_tich_esports.du_bao_danh_gia.recursive_forecast", side_effect=fast_forecast):
            first = evaluate_and_select(self.data, self.origin, progress=lambda _: None)
            second = evaluate_and_select(changed, self.origin, progress=lambda _: None)
        self.assertEqual(first[0], second[0])
        assert_frame_equal(first[1], second[1])
        selection = first[2].query("evaluation_phase == 'selection'")
        self.assertTrue((pd.PeriodIndex(selection["quarter"], freq="Q") <= self.origin - 4).all())

    def test_invalid_source_and_gap(self):
        duplicate = pd.concat([self.data, self.data.iloc[[0]]], ignore_index=True)
        with self.assertRaises(ValueError):
            prepare_quarterly(duplicate)
        negative = self.data.copy()
        negative.loc[negative.index[0], TARGET] = -1
        with self.assertRaises(ValueError):
            prepare_quarterly(negative)
        gap = self.data[~(self.data["game_family"].eq("Valorant") & self.data["quarter"].eq("2025Q2"))]
        restored = prepare_quarterly(gap)
        self.assertTrue(restored.query("game_family == 'Valorant' and quarter == '2025Q2'")[TARGET].isna().all())

    def test_loader_ignores_null_future_placeholders(self):
        data = self.data.copy()
        data.loc[data["period"] > pd.Period("2025Q4"), TARGET] = np.nan
        with tempfile.TemporaryDirectory() as folder:
            release = Path(folder)
            (release / "manifest.json").write_text(json.dumps({
                "stage": "analysis_release_v1_policy_clean_not_source_verified"
            }), encoding="utf-8")
            data.to_csv(release / "forecast_prize_quarterly.csv", index=False)
            _, _, history, origin = load_future_inputs(release)
            self.assertEqual(origin, pd.Period("2025Q4"))
            self.assertTrue((history["period"] <= origin).all())
            with self.assertRaises(ValueError):
                load_future_inputs(release, "2029Q4")

    def test_null_actual_excluded_from_metrics(self):
        data = self.data.copy()
        data.loc[data["quarter"].eq("2029Q4"), TARGET] = np.nan
        backtest = attach_actual(self.predictions, data, "holdout")
        metrics = summarize_backtest(backtest)
        overall = metrics.query("game_family == 'Overall' and horizon_quarters == 0")
        self.assertTrue(overall["n_evaluated"].eq(12).all())
        self.assertTrue(overall["n_predictions"].eq(16).all())
        for row in overall.itertuples():
            errors = backtest.loc[backtest["model"].eq(row.model), "residual_usd"].dropna()
            self.assertAlmostEqual(row.rmse_usd, float(np.sqrt((errors ** 2).mean())))

    def test_intervals_need_enough_samples(self):
        calibration = pd.DataFrame({"game_family": ["Dota 2"] * 8, "model": ["linear_regression"] * 8,
                                    "horizon_quarters": [1] * 8, "absolute_error_usd": np.arange(1, 9) * 100})
        radii = interval_radii(calibration)
        self.assertEqual(radii.iloc[0]["radius_usd"], 800)
        self.assertTrue(interval_radii(calibration.iloc[:7])["radius_usd"].isna().all())
        intervals = attach_intervals(self.predictions, radii)
        valid = intervals.dropna(subset=["lower_80_usd"])
        self.assertTrue((valid["lower_80_usd"] >= 0).all())
        self.assertTrue(valid["predicted_prize_pool_usd"].between(valid["lower_80_usd"], valid["upper_80_usd"]).all())

    def test_tableau_export_preserves_null_and_unique_keys(self):
        future = self.predictions.copy()
        future["actual_prize_pool_usd"] = np.nan
        future["lower_80_usd"] = np.nan
        future["upper_80_usd"] = np.nan
        future["source_release"] = "synthetic_test_only"
        future["generated_at_utc"] = "2029-01-01T00:00:00+00:00"
        future["source_coverage_verified"] = False
        validate_future_export(future, self.origin)
        history = self.data[self.data["period"] <= self.origin].copy()
        history.loc[history["quarter"].eq("2028Q4"), TARGET] = np.nan
        timeline = build_timeline(history, future, "linear_regression")
        self.assertFalse(timeline.duplicated(["game_family", "quarter", "model"]).any())
        self.assertTrue(timeline.query("record_type == 'forecast'")["actual_prize_pool_usd"].isna().all())
        self.assertTrue(timeline.query("quarter == '2028Q4'")["display_prize_pool_usd"].isna().all())
        self.assertTrue(timeline.query("model == 'linear_regression'")["is_primary_model"].all())


if __name__ == "__main__":
    unittest.main()

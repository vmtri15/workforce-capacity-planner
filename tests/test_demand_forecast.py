import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import forecast_demand as fd


def make_series(n=120):
    rng = np.random.default_rng(0)
    index = pd.bdate_range('2023-01-05', periods=n)
    values = rng.integers(500, 3000, n).astype(float)
    values[rng.choice(n, 15, replace=False)] = np.nan  # dates with no source records
    return pd.Series(values, index=index)


class ForecastLeakageTest(unittest.TestCase):
    def test_forecast_ignores_values_after_origin(self):
        series = make_series()
        pos = fd.origin_positions(series)[0]
        corrupted = series.copy()
        corrupted.iloc[pos + 1:] = 1e9
        names = ['SameWeekdayLastWeek', 'Mean20Days', 'XGBoost']
        _, clean = fd.forecast_at(series, pos, names)
        _, dirty = fd.forecast_at(corrupted, pos, names)
        for name in names:
            np.testing.assert_allclose(clean[name], dirty[name], err_msg=name)

    def test_origins_leave_a_full_window(self):
        series = make_series()
        for pos in fd.origin_positions(series):
            self.assertLessEqual(pos + fd.HORIZON, len(series) - 1)
            self.assertEqual(series.index[pos].weekday(), 4)


if __name__ == '__main__':
    unittest.main()

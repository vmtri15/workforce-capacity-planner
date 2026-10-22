import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'inventory'))
import build_inventory as inv


def test_lines(qty_by_day, key=('joliet', 'P1', 9.0)):
    start = pd.Timestamp(inv.CONFIG['test'][0])
    rows = [dict(order_id=i, key=key, qty=q, abc='A', day=start + pd.Timedelta(d, unit='D')) for i, (d, q) in enumerate(qty_by_day)]
    return pd.DataFrame(rows)


class InventoryTest(unittest.TestCase):
    def test_reorder_point_is_the_target_share_of_past_windows(self):
        windows = {'k': np.arange(1, 101)}
        self.assertAlmostEqual(inv.reorder_points(windows, lambda key: 0.9)['k'], 90.1)

    def test_stock_never_goes_negative_and_short_lines_wait(self):
        key = ('joliet', 'P1', 9.0)
        lines = test_lines([(0, 5), (0, 5), (1, 20), (30, 3)], key)
        short, held = inv.simulate(lines, {key: 0.0}, {key: 0.0})  # no safety stock, no history: every order waits
        self.assertTrue((held >= 0).all())
        self.assertTrue(short.all())
        short, _ = inv.simulate(lines, {key: 0.0}, {key: 1.0})  # starts with 14 days of cover: 14 pairs
        self.assertEqual(short.tolist(), [False, False, True, False])  # day 1 needs 20 with 4 left; day 30 is restocked

    def test_enough_stock_means_no_short_lines(self):
        key = ('joliet', 'P1', 9.0)
        lines = test_lines([(d, 2) for d in range(0, 60, 3)], key)
        short, _ = inv.simulate(lines, {key: 50.0}, {key: 1.0})
        self.assertFalse(short.any())


if __name__ == '__main__':
    unittest.main()

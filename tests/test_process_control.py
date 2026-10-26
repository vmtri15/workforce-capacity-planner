import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_process_control import cpk_upper, imr, p_chart, tukey_letters  # noqa: E402


class ProcessControlTest(unittest.TestCase):
    def test_imr_limits_come_from_the_average_moving_range(self):
        chart = imr([10, 12, 10, 12, 10])  # every moving range is 2
        self.assertAlmostEqual(chart['center'], 10.8)
        self.assertAlmostEqual(chart['sigma_within'], 2 / 1.128)
        self.assertAlmostEqual(chart['mr_ucl'], 3.267 * 2)
        self.assertEqual(chart['beyond_limits'], [])

    def test_imr_flags_a_point_far_from_the_rest(self):
        self.assertEqual(imr([10, 10.5] * 20 + [99, 10, 10.5])['beyond_limits'], [40])  # the index of the 99

    def test_cpk_upper(self):
        self.assertAlmostEqual(cpk_upper(80, 10, 110), 1.0)
        self.assertLess(cpk_upper(80, 10, 70), 0)

    def test_p_chart_flags_only_the_bad_day(self):
        chart = p_chart([5, 4, 6, 40], [100, 100, 100, 100])
        self.assertAlmostEqual(chart['p_bar'], 55 / 400)
        self.assertEqual(list(chart['above']), [False, False, False, True])

    def test_tukey_letters_group_levels_that_are_not_different(self):
        means = {'a': 10, 'b': 11, 'c': 20, 'd': 21}
        different = {frozenset(p) for p in [('a', 'c'), ('a', 'd'), ('b', 'c'), ('b', 'd')]}
        self.assertEqual(tukey_letters(means, lambda x, y: frozenset((x, y)) in different), {'a': 'A', 'b': 'A', 'c': 'B', 'd': 'B'})

    def test_tukey_letters_overlap(self):  # b ties with both a and c, but a and c differ
        means = {'a': 10, 'b': 15, 'c': 20}
        self.assertEqual(tukey_letters(means, lambda x, y: {x, y} == {'a', 'c'}), {'a': 'A', 'b': 'AB', 'c': 'B'})


if __name__ == '__main__':
    unittest.main()

import unittest

from workforce_planner.backlog import simulate_backlog


class BacklogTests(unittest.TestCase):
    def test_fifo_recovery_and_conservation(self):
        result = simulate_backlog([
            dict(date='2023-01-01', arrivals=10, capacity=0),
            dict(date='2023-01-02', arrivals=5, capacity=8),
            dict(date='2023-01-03', arrivals=0, capacity=3),
            dict(date='2023-01-04', arrivals=0, capacity=10)])
        self.assertEqual([r['closing_backlog'] for r in result], [10, 7, 4, 0])
        self.assertEqual([r['oldest_backlog_days'] for r in result], [0, 1, 1, 0])
        self.assertEqual(result[-1]['unused_capacity'], 6)
        for row in result:
            self.assertEqual(row['opening_backlog'] + row['arrivals'],
                             row['completed'] + row['closing_backlog'])

    def test_no_future_work(self):
        result = simulate_backlog([dict(date='2023-01-01', arrivals=0, capacity=100),
                                   dict(date='2023-01-02', arrivals=10, capacity=0)])
        self.assertEqual(result[-1]['closing_backlog'], 10)

    def test_absence_reduces_completions(self):
        normal = simulate_backlog([dict(date='2023-01-01', arrivals=10, capacity=10)])
        absent = simulate_backlog([dict(date='2023-01-01', arrivals=10, capacity=5)])
        self.assertEqual(absent[0]['closing_backlog'] - normal[0]['closing_backlog'], 5)

    def test_invalid_days_and_quantities(self):
        first = dict(date='2023-01-01', arrivals=1, capacity=1)
        for day in ['2023-01-01', '2023-01-03', '2022-12-31']:
            with self.assertRaises(ValueError):
                simulate_backlog([first, dict(first, date=day)])
        for value in [-1, 1.5, float('nan'), True]:
            for key in ['arrivals', 'capacity']:
                with self.assertRaises(ValueError):
                    simulate_backlog([dict(first, **{key: value})])


if __name__ == '__main__':
    unittest.main()

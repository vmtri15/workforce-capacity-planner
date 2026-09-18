"""Check baseline roster coverage, employee limits, and invalid inputs."""

import math
import unittest
from collections import Counter
from datetime import date, timedelta

from workforce_planner.roster import build_roster


class RosterTests(unittest.TestCase):
    def setUp(self):
        self.dates = [(date(2011, 10, 14) + timedelta(days=i)).isoformat() for i in range(56)]

    def test_minimum_roster_covers_all_dates_and_rolling_weeks(self):
        staffing = [{"site_id": "joliet", "role_id": role, "scheduled_headcount": count}
                    for role, count in [("fulfillment_associate", 23), ("packing_associate", 2),
                                        ("shipping_receiving_coordinator", 1), ("warehouse_supervisor", 2)]]
        result = build_roster(staffing, self.dates, 8)
        daily = Counter((row["role_id"], row["planning_date"]) for row in result["assignments"])
        by_role = Counter(row["role_id"] for row in result["workers"])
        for group in staffing:
            self.assertEqual(by_role[group["role_id"]], math.ceil(7 * group["scheduled_headcount"] / 5))
            for day in self.dates:
                self.assertEqual(daily[group["role_id"], day], group["scheduled_headcount"])
        for worker in result["workers"]:
            worked = {row["planning_date"] for row in result["assignments"]
                      if row["worker_id"] == worker["worker_id"]}
            for start in range(len(self.dates) - 6):
                self.assertLessEqual(sum(day in worked for day in self.dates[start:start + 7]), 5)

    def test_determinism_and_day_limits(self):
        groups = [{"site_id": site, "role_id": "packer", "scheduled_headcount": count}
                  for site, count in [("b", 1), ("a", 2)]]
        for max_days in [1, 3, 5, 7]:
            result = build_roster(groups, self.dates[:8], 8, max_days)
            self.assertEqual(result, build_roster(list(reversed(groups)), self.dates[:8], 8, max_days))
            self.assertTrue(all(len(worker["weekdays"]) <= max_days for worker in result["workers"]))

    def test_empty_staffing(self):
        group = {"site_id": "a", "role_id": "packer", "scheduled_headcount": 0}
        for staffing in [[], [group]]:
            result = build_roster(staffing, self.dates, 8)
            self.assertEqual(result["workers"], [])
            self.assertEqual(result["assignments"], [])

    def test_bad_inputs(self):
        group = {"site_id": "a", "role_id": "packer", "scheduled_headcount": 1}
        for dates in [[], ["2011-10-14", "2011-10-16"], ["2011-10-14", "2011-10-14"], ["20111014"]]:
            with self.assertRaises(ValueError):
                build_roster([group], dates, 8)
        for paid_hours in [0, -8, float("nan"), float("inf"), True]:
            with self.assertRaises(ValueError):
                build_roster([group], self.dates, paid_hours)
        for max_days in [0, 8, 2.5, True]:
            with self.assertRaises(ValueError):
                build_roster([group], self.dates, 8, max_days)
        with self.assertRaises(ValueError):
            build_roster([group, group], self.dates, 8)
        for count in [-1, 1.5, True]:
            with self.assertRaises(ValueError):
                build_roster([{**group, "scheduled_headcount": count}], self.dates, 8)


if __name__ == "__main__":
    unittest.main()

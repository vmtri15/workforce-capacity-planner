import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from validate_recommendations import choose, price


class RecommendationTests(unittest.TestCase):
    def test_repricing(self):
        self.assertEqual(price(dict(regular_paid_hours=8,overtime_paid_hours=2,temporary_shifts=1),22,1.5,30,8),482)

    def test_robust_rejects_any_failed_case(self):
        r=dict(policy='cheap',basis='retained',rate=40,absent=0,lead_days=1,target_met=True,total_cost=10)
        rows=[r,r|dict(absent=1,target_met=False),r|dict(policy='robust',total_cost=20),r|dict(policy='robust',absent=1,total_cost=30)]
        self.assertEqual(choose(rows,False),'cheap')
        self.assertEqual(choose(rows,True),'robust')
        self.assertIsNone(choose([r|dict(target_met=False)],True))


if __name__=='__main__':
    unittest.main()

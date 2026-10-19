import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prep_parcels as prep


class PrepTest(unittest.TestCase):
    def test_haversine_sao_paulo_to_rio(self):
        km = prep.haversine_km(-23.5505, -46.6333, -22.9068, -43.1729)
        self.assertAlmostEqual(float(km), 360, delta=10)

    def test_clean_orders_drops_impossible_and_incomplete_rows(self):
        t = pd.Timestamp
        base = dict(order_status='delivered', order_purchase_timestamp=t('2018-01-01'),
                    order_approved_at=t('2018-01-01'), order_estimated_delivery_date=t('2018-01-20'))
        orders = pd.DataFrame([
            dict(base, order_id='ok', order_delivered_carrier_date=t('2018-01-02'), order_delivered_customer_date=t('2018-01-05')),
            dict(base, order_id='backwards', order_delivered_carrier_date=t('2018-01-05'), order_delivered_customer_date=t('2018-01-02')),
            dict(base, order_id='before_purchase', order_delivered_carrier_date=t('2017-12-30'), order_delivered_customer_date=t('2018-01-03')),
            dict(base, order_id='no_delivery', order_delivered_carrier_date=t('2018-01-02'), order_delivered_customer_date=pd.NaT),
            dict(base, order_id='canceled', order_status='canceled', order_delivered_carrier_date=t('2018-01-02'),
                 order_delivered_customer_date=t('2018-01-05')),
        ])
        report = {}
        kept = prep.clean_orders(orders, report)
        self.assertEqual(list(kept['order_id']), ['ok'])
        self.assertEqual(report['orders_total'], 5)
        self.assertEqual(report['dropped_missing_handover_or_delivery_time'], 1)
        self.assertEqual(report['dropped_delivery_before_handover_or_handover_before_purchase'], 2)


if __name__ == '__main__':
    unittest.main()

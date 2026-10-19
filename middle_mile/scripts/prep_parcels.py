"""Turn the Olist orders into a clean parcels table with real route distances.

Everything in the output comes from the real Olist data. Nothing is simulated here.
One row per delivered order. Distances are straight line (great circle) kilometres between the
median coordinates of the seller and customer zip code prefixes, from Olist's geolocation file.

Outputs (data/processed/):
  parcels.csv       one row per parcel (not committed, derived from the raw Olist files)
  route_stats.csv   one row per seller state to customer state route
  prep_report.json  how many orders each cleaning rule removed

Needs the Olist files in archive/ (download from Kaggle, they are not in the repo).
Run from the project root:
    python3 scripts/prep_parcels.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'archive'
OUT = ROOT / 'data/processed'
BRAZIL = dict(lat=(-34.0, 6.0), lng=(-74.0, -34.0))  # a few geolocation rows fall outside Brazil
TIMES = ['order_purchase_timestamp', 'order_approved_at', 'order_delivered_carrier_date',
         'order_delivered_customer_date', 'order_estimated_delivery_date']


def haversine_km(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(a))


def clean_orders(orders, report):
    """Keep delivered orders with a consistent time order; count what each rule removes."""
    report['orders_total'] = len(orders)
    orders = orders[orders['order_status'] == 'delivered']
    report['delivered'] = len(orders)
    complete = orders.dropna(subset=['order_delivered_carrier_date', 'order_delivered_customer_date'])
    report['dropped_missing_handover_or_delivery_time'] = len(orders) - len(complete)
    transit = complete['order_delivered_customer_date'] - complete['order_delivered_carrier_date']
    ordered = complete[(transit >= pd.Timedelta(0))
                       & (complete['order_delivered_carrier_date'] >= complete['order_purchase_timestamp'])]
    report['dropped_delivery_before_handover_or_handover_before_purchase'] = len(complete) - len(ordered)
    report['parcels'] = len(ordered)
    return ordered


def zip_centroids(geo):
    geo = geo[geo['geolocation_lat'].between(*BRAZIL['lat']) & geo['geolocation_lng'].between(*BRAZIL['lng'])]
    by_zip = geo.groupby('geolocation_zip_code_prefix')[['geolocation_lat', 'geolocation_lng']].median()
    by_state = geo.groupby('geolocation_state')[['geolocation_lat', 'geolocation_lng']].median()
    return by_zip, by_state


def read(name, **kwargs):
    return pd.read_csv(RAW / f'olist_{name}_dataset.csv', **kwargs)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    orders = clean_orders(read('orders', parse_dates=TIMES), report)
    items = read('order_items', parse_dates=['shipping_limit_date'])
    products = read('products')[['product_id', 'product_weight_g']]
    sellers = read('sellers', dtype={'seller_zip_code_prefix': str})
    customers = read('customers', dtype={'customer_zip_code_prefix': str})
    geo = read('geolocation', dtype={'geolocation_zip_code_prefix': str})

    items = items.merge(products, on='product_id', how='left')
    per_order = items.groupby('order_id').agg(
        items=('order_item_id', 'max'), sellers=('seller_id', 'nunique'),
        shipping_limit=('shipping_limit_date', 'min'), weight_g=('product_weight_g', 'sum'),
        price=('price', 'sum'), freight_value=('freight_value', 'sum')).reset_index()
    primary = items.loc[items['order_item_id'] == 1, ['order_id', 'seller_id']]  # first item's seller
    report['orders_with_more_than_one_seller'] = int((per_order['sellers'] > 1).sum())

    p = (orders.merge(per_order, on='order_id', how='inner').merge(primary, on='order_id', how='left')
         .merge(sellers.rename(columns={'seller_zip_code_prefix': 'seller_zip', 'seller_state': 'seller_state'})
                [['seller_id', 'seller_zip', 'seller_state']], on='seller_id', how='left')
         .merge(customers[['customer_id', 'customer_zip_code_prefix', 'customer_state']], on='customer_id', how='left')
         .rename(columns={'customer_zip_code_prefix': 'customer_zip'}))
    report['parcels_without_items'] = report['parcels'] - len(p)

    by_zip, by_state = zip_centroids(geo)
    s = by_zip.reindex(p['seller_zip']).to_numpy()
    c = by_zip.reindex(p['customer_zip']).to_numpy()
    zip_ok = ~(np.isnan(s).any(axis=1) | np.isnan(c).any(axis=1))
    # fall back to state centroids when a zip prefix has no coordinates
    s_state = by_state.reindex(p['seller_state']).to_numpy()
    c_state = by_state.reindex(p['customer_state']).to_numpy()
    s_use, c_use = np.where(zip_ok[:, None], s, s_state), np.where(zip_ok[:, None], c, c_state)
    p['distance_km'] = haversine_km(s_use[:, 0], s_use[:, 1], c_use[:, 0], c_use[:, 1])
    p['distance_source'] = np.where(zip_ok, 'zip_prefix', 'state_centroid')
    report['distance_from_zip_prefix_share'] = round(float(zip_ok.mean()), 4)
    report['parcels_without_any_distance'] = int(p['distance_km'].isna().sum())

    day = pd.Timedelta(days=1)
    p['route'] = p['seller_state'] + '>' + p['customer_state']
    p['transit_days'] = (p['order_delivered_customer_date'] - p['order_delivered_carrier_date']) / day
    p['promised_days_from_purchase'] = (p['order_estimated_delivery_date'] - p['order_purchase_timestamp']) / day
    p['promised_days_from_handover'] = (p['order_estimated_delivery_date'] - p['order_delivered_carrier_date']) / day
    p['days_late'] = (p['order_delivered_customer_date'] - p['order_estimated_delivery_date']) / day
    p['late'] = p['days_late'] > 0
    p['handover_after_shipping_limit'] = p['order_delivered_carrier_date'] > p['shipping_limit']
    p = p.rename(columns={'order_purchase_timestamp': 'purchase_ts', 'order_approved_at': 'approved_ts',
                          'order_delivered_carrier_date': 'handover_ts', 'order_delivered_customer_date': 'delivered_ts',
                          'order_estimated_delivery_date': 'promised_ts', 'shipping_limit': 'shipping_limit_ts'})
    columns = ['order_id', 'seller_id', 'seller_state', 'seller_zip', 'customer_state', 'customer_zip', 'route',
               'purchase_ts', 'approved_ts', 'shipping_limit_ts', 'handover_ts', 'delivered_ts', 'promised_ts',
               'items', 'weight_g', 'price', 'freight_value', 'distance_km', 'distance_source',
               'transit_days', 'promised_days_from_purchase', 'promised_days_from_handover', 'days_late', 'late',
               'handover_after_shipping_limit']
    p = p[columns].sort_values('handover_ts').reset_index(drop=True)

    routes = p.groupby('route').agg(
        seller_state=('seller_state', 'first'), customer_state=('customer_state', 'first'), parcels=('order_id', 'size'),
        median_km=('distance_km', 'median'), median_transit_days=('transit_days', 'median'),
        p90_transit_days=('transit_days', lambda x: x.quantile(0.9)), late_share=('late', 'mean')
    ).reset_index().sort_values('parcels', ascending=False)

    p.to_csv(OUT / 'parcels.csv', index=False)
    routes.to_csv(OUT / 'route_stats.csv', index=False)
    report.update(first_handover=str(p['handover_ts'].min()), last_handover=str(p['handover_ts'].max()),
                  routes=len(routes), routes_with_100_or_more_parcels=int((routes['parcels'] >= 100).sum()),
                  late_share=round(float(p['late'].mean()), 4))
    (OUT / 'prep_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

"""Part 4a: inventory. How much stock should each site hold so orders do not wait for products?

Real: the 2023 order lines (product, size, quantity, time), each product's ABC class, and the customer to site
assignment from the middle mile. Assumed (config.json): supplier lead times, unit cost and holding cost.

For each stocking policy:
  1. set a reorder point for every site, product and size from January to June demand only
  2. replay July to October line by line: ship from stock, or the order waits for the next delivery
  3. measure orders delayed by a stockout, the average stock held, and what it costs to hold

Run from the repo root:
    .venv/bin/python inventory/build_inventory.py
"""
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / 'middle_mile' / 'connected'))
from build_connected import site_shares, weighted_pick  # noqa: E402  the same customer to site split as the middle mile

CONFIG = json.loads((HERE / 'config.json').read_text())
RAW = REPO / 'data/raw/warehouse_picking'
OUT = HERE / 'results'


def load_lines():
    lines = pd.read_csv(RAW / 'Customer_Order.csv', sep=';', encoding='utf-8-sig')
    lines = pd.DataFrame({'order_id': lines['orderNumber'], 'customer': lines['codCustomer'].str.strip(),
                          'product': lines['Reference'].str.strip(), 'size': lines['Size (US)'],
                          'qty': lines['quantity (units)'].astype(int),
                          'created': pd.to_datetime(lines['creationDate'], format='%d/%m/%Y %H:%M')})
    classes = pd.read_csv(RAW / 'Product.csv', sep=';')
    lines['abc'] = lines['product'].map(dict(zip(classes['Reference'].str.strip(), classes['ABCCOD'].str.strip())))
    shares = site_shares()
    lines['site'] = [weighted_pick(c, shares, 'site') for c in lines['customer']]
    lines['key'] = list(zip(lines['site'], lines['product'], lines['size']))
    lines['day'] = lines['created'].dt.normalize()
    return lines.sort_values(['created', 'order_id']).reset_index(drop=True)


def window_demand(train, lead_days, days=None):
    """Every lead time window of daily demand in the history, per site, product and size (calendar days)."""
    days = pd.date_range(*CONFIG['train']) if days is None else days
    daily = train.groupby(['key', 'day'])['qty'].sum().unstack(fill_value=0).reindex(columns=days, fill_value=0)
    sums = daily.T.rolling(lead_days).sum().iloc[lead_days - 1:].T
    return {key: row.to_numpy() for key, row in sums.iterrows()}, daily.mean(axis=1).to_dict()


def reorder_points(windows, targets):
    """Reorder point: the stock that covers the target share of past lead time windows."""
    return {key: float(np.quantile(w, targets(key))) for key, w in windows.items()}


def lead_time(key, n):
    """Actual lead time of the n-th replenishment of one item: random but the same in every run and policy."""
    lt = CONFIG['actual_lead_time_days']
    u = int(hashlib.sha256(f"{lt['seed']}|{key}|{n}".encode()).hexdigest()[:8], 16) / 16 ** 8
    return lt['min'] + int(u * (lt['max'] - lt['min'] + 1))


def simulate(test, reorder, mean_daily, fixed_lead=None, replan=None):
    """Replay the test lines in time order. replan: {day: (reorder, mean_daily)} to reset the rules on that day.
    Returns per line shortfall and the daily stock held."""
    cover = CONFIG['cover_days']
    items = set(reorder) | set(test['key'])
    target = {k: reorder.get(k, 0.0) + math.ceil(mean_daily.get(k, 0.0) * cover) for k in items}
    on_hand = {k: max(0, math.ceil(t)) for k, t in target.items()}  # each item starts the test full
    backorder, pipeline, orders_placed = defaultdict(int), defaultdict(list), defaultdict(int)
    position = dict(on_hand)  # on hand + on order - backorders
    short = np.zeros(len(test), dtype=bool)
    held, total_on_hand = [], sum(on_hand.values())
    lines_by_day = {day: g for day, g in test.groupby('day')}
    for day in pd.date_range(*CONFIG['test']):
        if replan and day in replan:  # new reorder points from recent demand; stock on hand and on order stay
            reorder, mean_daily = replan[day]
            target = {k: reorder.get(k, 0.0) + math.ceil(mean_daily.get(k, 0.0) * cover) for k in items}
        for key, qty in pipeline.pop(day, []):  # arrivals clear waiting orders first
            served = min(backorder[key], qty)
            backorder[key] -= served
            on_hand[key] = on_hand.get(key, 0) + qty - served
            total_on_hand += qty - served
        group = lines_by_day.get(day)
        if group is not None:
            for i, key, qty in zip(group.index, group['key'], group['qty']):
                have = on_hand.get(key, 0)
                take = min(have, qty)
                on_hand[key] = have - take
                total_on_hand -= take
                if take < qty:
                    short[i] = True
                    backorder[key] += qty - take
                position[key] = position.get(key, 0) - qty
                if position[key] <= reorder.get(key, 0.0):
                    amount = math.ceil(target[key] - position[key])
                    arrive = day + pd.Timedelta(int(fixed_lead or lead_time(key, orders_placed[key])), unit='D')
                    orders_placed[key] += 1
                    pipeline[arrive].append((key, amount))
                    position[key] += amount
        held.append(total_on_hand)
    return short, np.array(held)


def why_short(test, short, reorder, mean_daily):
    """What the lines that ran short have in common."""
    t = test[short]
    rp = t['key'].map(reorder)
    big = t['qty'] > CONFIG['cover_days'] * t['key'].map(mean_daily).fillna(0)
    return dict(short_lines=int(len(t)), share_bigger_than_cover=round(float(big.mean()), 4),
                share_never_sold_before=round(float(rp.isna().mean()), 4),
                share_no_safety_stock=round(float((rp.fillna(0) == 0).mean()), 4))


def evaluate(name, reorder, test, mean_daily, fixed_lead=None, replan=None):
    short, held = simulate(test, reorder, mean_daily, fixed_lead, replan)
    t = test.assign(short=short)
    orders = t.groupby('order_id')['short'].any()
    units = held.mean()
    value = units * CONFIG['unit_cost']
    row = dict(policy=name, orders=len(orders), orders_delayed=int(orders.sum()), share_orders_delayed=round(orders.mean(), 4),
               line_fill_rate=round(1 - t['short'].mean(), 4),
               unit_fill_rate=round(1 - t.loc[t['short'], 'qty'].sum() / t['qty'].sum(), 4),
               average_units_held=round(units), average_stock_value=round(value),
               holding_cost_per_year=round(value * CONFIG['holding_cost_per_year']))
    by_class = t.groupby('abc').agg(lines=('short', 'size'), line_fill_rate=('short', lambda s: round(1 - s.mean(), 4)))
    return row, by_class.reset_index().assign(policy=name), why_short(test, short, reorder, mean_daily)


def main():
    lines = load_lines()
    train = lines[(lines['day'] >= CONFIG['train'][0]) & (lines['day'] <= CONFIG['train'][1])]
    test = lines[(lines['day'] >= CONFIG['test'][0]) & (lines['day'] <= CONFIG['test'][1])].reset_index(drop=True)
    windows, mean_daily = window_demand(train, CONFIG['planning_lead_time_days'])
    abc = dict(zip(lines['key'], lines['abc']))
    policies = {f'flat_{int(q * 100)}': (lambda q: lambda key: q)(q) for q in CONFIG['flat_targets']}
    for name, by in CONFIG['class_policies'].items():
        policies[name] = (lambda by: lambda key: by[abc[key]])(by)
    runs = [(name, reorder_points(windows, targets), mean_daily, {}) for name, targets in policies.items()]
    reliable, monthly = CONFIG['reliable_supplier'], CONFIG['monthly_replan']
    runs.append((reliable['policy'], reorder_points(windows, lambda key: reliable['target']), mean_daily,
                 dict(fixed_lead=reliable['lead_time_days'])))
    replan = {}
    for start in pd.date_range(CONFIG['test'][0], CONFIG['test'][1], freq='MS'):  # only demand before each month
        days = pd.date_range(start - pd.Timedelta(monthly['history_days'], unit='D'), start - pd.Timedelta(1, unit='D'))
        history = lines[(lines['day'] >= days[0]) & (lines['day'] <= days[-1])]
        w, m = window_demand(history, CONFIG['planning_lead_time_days'], days)
        replan[start] = (reorder_points(w, lambda key: monthly['target']), m)
    runs.append((monthly['policy'], *replan[pd.Timestamp(CONFIG['test'][0])], dict(replan=replan)))
    rows, classes, reasons = [], [], {}
    for name, reorder, daily_mean, options in runs:
        row, by_class, reasons[name] = evaluate(name, reorder, test, daily_mean, **options)
        rows.append(row)
        classes.append(by_class)
        print(json.dumps(row), flush=True)
    curve = pd.DataFrame(rows)
    OUT.mkdir(exist_ok=True)
    curve.to_csv(OUT / 'policy_curve.csv', index=False)
    pd.concat(classes).to_csv(OUT / 'fill_rate_by_class.csv', index=False)
    new_items = set(test['key']) - set(windows)
    new_lines = test['key'].isin(new_items)
    orders_on_new = test.assign(new=new_lines).groupby('order_id')['new'].any()
    summary = dict(evidence_status=CONFIG['evidence_status'], train=CONFIG['train'], test=CONFIG['test'],
                   items_stocked=len(windows), test_orders=int(test['order_id'].nunique()),
                   items_new_in_test=len(new_items), test_lines_on_new_items=round(float(new_lines.mean()), 4),
                   test_orders_with_a_new_item=round(float(orders_on_new.mean()), 4),
                   why_lines_ran_short_flat_95=reasons['flat_95'], policies=rows)
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    pd.set_option('display.width', 220)
    print(curve.to_string(index=False))


if __name__ == '__main__':
    main()

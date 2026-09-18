"""Validated allocation of network packing hours to modeled sites."""
from decimal import Decimal, ROUND_HALF_UP

from .network_optimization import PACK


def packing_demand_rows(rows, daily, sites, units_per_job):
    """Preserve daily network hours to six decimals; keep picking at baseline."""
    shares = {s['site_id']: Decimal(str(s['allocation_share'])) for s in sites}
    if not shares or any(not s.is_finite() or s < 0 for s in shares.values()) or abs(sum(shares.values()) - 1) > Decimal('0.000000001'):
        raise ValueError('Site shares must be nonnegative and sum to one')
    if {r['site_id'] for r in rows} != set(shares):
        raise ValueError('Demand and allocation sites must match')
    dates = {r['planning_date'] for r in rows}
    selected = [r for r in daily if int(r['assumed_units_per_job']) == units_per_job]
    if len(selected) != len(dates) or {r['source_date'] for r in selected} != dates:
        raise ValueError('Packing demand requires one matching record per date')
    allocated = {}
    quantum = Decimal('0.000001')
    ordered = sorted(shares)
    for record in selected:
        total = Decimal(str(record['productive_packing_hours']))
        if not total.is_finite() or total < 0:
            raise ValueError('Packing hours must be finite and nonnegative')
        total = total.quantize(quantum, rounding=ROUND_HALF_UP)
        remainder = total
        for site in ordered[:-1]:
            amount = (total * shares[site]).quantize(quantum, rounding=ROUND_HALF_UP)
            allocated[site, record['source_date']] = str(amount)
            remainder -= amount
        allocated[ordered[-1], record['source_date']] = str(remainder)
    output = []
    for row in rows:
        if row['role_id'] == PACK:
            output.append(row | {'productive_demand_hours': allocated[row['site_id'], row['planning_date']]})
        else:
            output.append(dict(row))
    return output

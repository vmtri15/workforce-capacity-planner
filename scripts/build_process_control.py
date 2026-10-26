"""Six Sigma checks on the planner's own data: an I-MR chart and Cpk for packing time, and a p-chart of daily late parcels.

Packing time: real OpenPack lab recordings (one-item boxes in scenario S1, the same screen as evaluate_openpack_timing.py),
in recording order, against the 90 seconds per unit the planner's 40 units per hour base case allows (upper limit only).
Late parcels: the middle-mile replay's daily counts (middle_mile/connected/results/daily_late.csv), grouped by promise date.
Who packs: a block design on every S1 box with 1 to 5 items. Packer is the factor, box size (item count) the block; ANOVA with
adjusted sums of squares, a lack-of-fit test against the packer x box size interaction, and Tukey comparisons of the packers'
adjusted means (each packer averaged over the five box sizes).

Run after build_connected.py, before build_static_dashboard.py:
    .venv/bin/python scripts/build_process_control.py
"""
import csv
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from patsy import build_design_matrices
from scipy import stats
from statsmodels.stats.anova import anova_lm

ROOT = Path(__file__).resolve().parents[1]
TIMING = ROOT / 'data/processed/openpack_timing_audit.csv'
DAILY = ROOT / 'middle_mile/connected/results/daily_late.csv'
OUTPUT = ROOT / 'data/processed/process_control.json'
COSTS = json.loads((ROOT / 'config/staffing_cost_scenarios.json').read_text())
BASE_RATE = 40  # units per productive hour, the planner's base case
D2, D4 = 1.128, 3.267  # control chart constants for moving ranges of 2


def imr(values):
    """Individuals and moving range chart limits, with the points beyond 3 sigma."""
    x = np.asarray(values, float)
    mr = np.abs(np.diff(x))
    center, mr_bar = x.mean(), mr.mean()
    sigma = mr_bar / D2
    ucl, lcl = center + 3 * sigma, center - 3 * sigma
    return dict(center=center, sigma_within=sigma, ucl=ucl, lcl=lcl, mr_bar=mr_bar, mr_ucl=D4 * mr_bar,
                beyond_limits=[int(i) for i in np.flatnonzero((x > ucl) | (x < lcl))])


def cpk_upper(mean, sigma, usl):
    """One-sided capability: how many 3 sigma widths fit between the mean and the upper limit."""
    return (usl - mean) / (3 * sigma)


def p_chart(late, parcels):
    """Overall late share and each day's 3 sigma limits; flags days above the upper limit."""
    late, n = np.asarray(late, float), np.asarray(parcels, float)
    p = late.sum() / n.sum()
    se = np.sqrt(p * (1 - p) / n)
    ucl, lcl = p + 3 * se, np.maximum(0, p - 3 * se)
    return dict(p_bar=p, ucl=ucl, lcl=lcl, above=late / n > ucl)


def screened(path=TIMING):
    """S1 boxes that pass the OpenPack screen used by evaluate_openpack_timing.py."""
    with path.open() as f:
        return [r for r in csv.DictReader(f) if r['screen_pass'] == 'True' and abs(float(r['gap_seconds'])) <= .001
                and r['scenario'] == 'S1' and 1 <= int(r['item_count']) <= 5]


def tukey_letters(means, significant):
    """Grouping letters, fastest first: levels that share a letter are not significantly different."""
    order = sorted(means, key=means.get)
    groups = []
    for i in range(len(order)):
        j = i
        while j + 1 < len(order) and all(not significant(a, order[j + 1]) for a in order[i:j + 1]):
            j += 1
        group = set(order[i:j + 1])
        if not any(group <= g for g in groups):
            groups.append(group)
    return {level: ''.join(chr(65 + n) for n, g in enumerate(groups) if level in g) for level in order}


def packer_study(rows):
    d = pd.DataFrame({'packer': [r['person_id'] for r in rows], 'items': [int(r['item_count']) for r in rows],
                      'seconds': [float(r['station_seconds_excluding_picking']) for r in rows]})
    model = smf.ols('seconds ~ C(packer) + C(items)', d).fit()
    table = anova_lm(model, typ=2)  # adjusted (Type II) sums of squares, the same as Minitab's Adj SS for an additive model
    with warnings.catch_warnings():  # two packers never packed a 4-item box, so a few interaction cells are empty
        warnings.simplefilter('ignore')
        full = smf.ols('seconds ~ C(packer) * C(items)', d).fit()
    lof_df, lof_ss = model.df_resid - full.df_resid, model.ssr - full.ssr
    lof_f = (lof_ss / lof_df) / (full.ssr / full.df_resid)
    log_model = anova_lm(smf.ols('np.log(seconds) ~ C(packer) + C(items)', d).fit(), typ=2)
    # adjusted mean of each packer: the model's prediction averaged over the five box sizes
    packers, sizes = sorted(d['packer'].unique()), sorted(d['items'].unique())
    grid = pd.DataFrame([(p, n) for p in packers for n in sizes], columns=['packer', 'items'])
    X = np.asarray(build_design_matrices([model.model.data.model_spec], grid)[0], float)
    L = {p: X[grid['packer'].to_numpy() == p].mean(axis=0) for p in packers}
    beta, cov = model.params.to_numpy(), model.cov_params().to_numpy()
    means = {p: float(L[p] @ beta) for p in packers}
    k, df = len(packers), model.df_resid
    q_crit = stats.studentized_range.ppf(0.95, k, df)
    pairs = []
    for i, a in enumerate(packers):
        for b in packers[i + 1:]:
            c = L[b] - L[a]
            diff, se = float(c @ beta), float(np.sqrt(c @ cov @ c))
            pairs.append(dict(a=a, b=b, diff=round(diff, 2), se=round(se, 3), lo=round(diff - q_crit / np.sqrt(2) * se, 2),
                              hi=round(diff + q_crit / np.sqrt(2) * se, 2),
                              p_adj=float(stats.studentized_range.sf(abs(diff) / se * np.sqrt(2), k, df))))
    sig = {frozenset((p['a'], p['b'])): p['p_adj'] < 0.05 for p in pairs}
    letters = tukey_letters(means, lambda a, b: sig[frozenset((a, b))])
    resid = (model.resid / np.sqrt(model.mse_resid)).to_numpy()
    source = lambda name: dict(df=int(table.loc[name, 'df']), adj_ss=round(float(table.loc[name, 'sum_sq']), 1),
                               adj_ms=round(float(table.loc[name, 'sum_sq'] / table.loc[name, 'df']), 1),
                               f=round(float(table.loc[name, 'F']), 2), p=float(table.loc[name, 'PR(>F)']))
    return dict(
        boxes=len(d), packers=k, box_sizes=len(sizes),
        anova=dict(packer=source('C(packer)'), box_size=source('C(items)'),
                   error=dict(df=int(model.df_resid), adj_ss=round(model.ssr, 1), adj_ms=round(model.mse_resid, 1)),
                   lack_of_fit=dict(df=int(lof_df), adj_ss=round(lof_ss, 1), adj_ms=round(lof_ss / lof_df, 1), f=round(lof_f, 2),
                                    p=float(stats.f.sf(lof_f, lof_df, full.df_resid))),
                   pure_error=dict(df=int(full.df_resid), adj_ss=round(full.ssr, 1), adj_ms=round(full.ssr / full.df_resid, 1)),
                   total=dict(df=len(d) - 1, adj_ss=round(float(((d['seconds'] - d['seconds'].mean()) ** 2).sum()), 1))),
        s=round(float(np.sqrt(model.mse_resid)), 2), r_sq=round(model.rsquared, 4), r_sq_adj=round(model.rsquared_adj, 4),
        log_check=dict(packer_f=round(float(log_model.loc['C(packer)', 'F']), 2), packer_p=float(log_model.loc['C(packer)', 'PR(>F)'])),
        residual_skew=round(float(stats.skew(resid)), 2),
        q_crit=round(float(q_crit), 4),
        means=[dict(packer=p, boxes=int((d['packer'] == p).sum()), adjusted_mean=round(means[p], 2), group=letters[p])
               for p in sorted(packers, key=means.get)],
        pairs=pairs, residuals=sorted(round(float(v), 3) for v in resid),
        coaching=coaching_inputs(sorted(packers, key=means.get)))


def coaching_inputs(by_speed):
    """What the coaching simulator needs: the median packer and the volume and wage a packer's saved seconds are priced at."""
    orders = json.loads((ROOT / 'middle_mile/connected/results/summary.json').read_text())['plans'][0]['orders']
    return dict(median_packer=by_speed[len(by_speed) // 2], orders_2023=orders, base_workers=COSTS['base_workers'],
                boxes_per_packer=round(orders / COSTS['base_workers']), hourly_cost=COSTS['regular_hourly_cost'])


def packing(rows):
    rows = [r for r in rows if r['item_count'] == '1']
    rows.sort(key=lambda r: (r['recording_id'], r['session'], int(r['box'])))
    x = [float(r['station_seconds_excluding_picking']) for r in rows]
    chart, usl = imr(x), 3600 / BASE_RATE
    overall = float(np.std(x, ddof=1))
    people = sorted({r['person_id'] for r in rows})
    return dict(
        source='OpenPack packing recordings, scenario S1, one-item boxes, packing station time excluding picking',
        boxes=len(x), people=len(people), usl_seconds=usl, usl_basis=f'{BASE_RATE} units per productive hour (planner base case)',
        mean_seconds=round(chart['center'], 2), sigma_within=round(chart['sigma_within'], 2), sigma_overall=round(overall, 2),
        ucl=round(chart['ucl'], 2), lcl=round(chart['lcl'], 2), mr_bar=round(chart['mr_bar'], 2), mr_ucl=round(chart['mr_ucl'], 2),
        points_beyond_limits=len(chart['beyond_limits']),
        cpk=round(cpk_upper(chart['center'], chart['sigma_within'], usl), 2),
        ppk=round(cpk_upper(chart['center'], overall, usl), 2),
        share_over_usl=round(float(np.mean(np.array(x) > usl)), 4),
        cpk_at_stress_rates={str(rate): float(round(cpk_upper(chart['center'], chart['sigma_within'], 3600 / rate), 2))
                             for rate in COSTS['stress_productivity_rates']},
        ppk_at_stress_rates={str(rate): float(round(cpk_upper(chart['center'], overall, 3600 / rate), 2))
                             for rate in COSTS['stress_productivity_rates']},
        seconds_for_cpk_1_33=round(chart['center'] + 4 * chart['sigma_within'], 1),
        seconds_for_ppk_1_33=round(chart['center'] + 4 * overall, 1),  # Ppk is the fair number while the process is out of control
        person_means={p: round(float(np.mean([v for v, r in zip(x, rows) if r['person_id'] == p])), 1) for p in people},
        points=[dict(seconds=round(v, 2), person=r['person_id']) for v, r in zip(x, rows)])


def late_parcels():
    with DAILY.open() as f:
        rows = list(csv.DictReader(f))
    plans = {}
    for plan in dict.fromkeys(r['plan'] for r in rows):
        days = [r for r in rows if r['plan'] == plan]
        late, n = [int(r['late']) for r in days], [int(r['parcels']) for r in days]
        chart = p_chart(late, n)
        above = [d for d, flag in zip(days, chart['above']) if flag]
        busy = 1.5 * float(np.median(n))  # a peak day: half again the usual daily volume
        plans[plan] = dict(
            days=len(days), parcels=sum(n), late=sum(late), p_bar=round(chart['p_bar'], 5),
            days_above_limit=len(above), late_on_those_days=sum(int(d['late']) for d in above),
            weather_late_on_those_days=sum(int(d['late_from_weather']) for d in above),
            peak_day_parcels=busy, late_on_those_days_that_were_peaks=sum(int(d['late']) for d in above if int(d['parcels']) >= busy),
            points=[dict(date=d['promise_date'], parcels=int(d['parcels']), late=int(d['late']), ucl=round(u, 4), above=bool(a))
                    for d, u, a in zip(days, chart['ucl'], chart['above'])])
    return plans


def main():
    rows = screened()
    result = dict(packing=packing(rows), packer_study=packer_study(rows), late_parcels=late_parcels())
    OUTPUT.write_text(json.dumps(result, indent=1) + '\n')
    pk, six, ps = result['packing'], result['late_parcels']['affordable_6_workers'], result['packer_study']
    print(f"Who packs: F {ps['anova']['packer']['f']}, p {ps['anova']['packer']['p']:.1e}, lack of fit p {ps['anova']['lack_of_fit']['p']:.1e}; "
          f"groups {' '.join(m['packer'] + ':' + m['group'] for m in ps['means'])}")
    print(f"Packing: {pk['boxes']} boxes, mean {pk['mean_seconds']} s, Cpk {pk['cpk']} at {pk['usl_seconds']:.0f} s, "
          f"{pk['share_over_usl']:.1%} over; Cpk by rate {pk['cpk_at_stress_rates']}")
    print(f"6 workers: {six['days_above_limit']} of {six['days']} days above the p-chart limit hold "
          f"{six['late_on_those_days']} of {six['late']} late parcels")


if __name__ == '__main__':
    main()

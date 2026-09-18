"""Joint daily network model with explicit synthetic eligibility and paid time."""
from collections import defaultdict
from datetime import date, timedelta
from fractions import Fraction
from math import isfinite, lcm

from ortools.sat.python import cp_model

from .optimization import fraction as F, validate_policy, week_start

PICK = 'fulfillment_associate'
PACK = 'packing_associate'


def required_productive_hours(row):
    """An explicit hours input already excludes paid-time allowances."""
    if 'productive_demand_hours' in row:
        hours = F(row['productive_demand_hours'])
    else:
        hours = F(row['workload_quantity']) / F(row['productivity_rate'])
    if hours < 0:
        raise ValueError('Productive demand hours must be nonnegative')
    return hours


def validate_actions(config, paid_hours, step):
    cross, hire, transfer = (config[k] for k in ('cross_training', 'hiring', 'transfers'))
    for section, fields in ((cross, ['eligible_packers_per_site']),
                            (hire, ['candidate_pool_per_site', 'recruitment_lead_calendar_days', 'paid_training_days']),
                            (transfer, ['eligible_pickers_per_site', 'destination_readiness_delay_days'])):
        for field in fields:
            if type(section[field]) is not int or section[field] < 0:
                raise ValueError(f'{field} must be a nonnegative integer')
    for section, fields in ((cross, ['training_paid_hours', 'external_trainer_fee', 'max_redeployment_hours_per_day', 'picking_productivity_factor']),
                            (hire, ['recruitment_and_external_training_fee', 'productive_factor_after_training']),
                            (transfer, ['round_trip_paid_travel_hours', 'transport_cost_per_person_day'])):
        for field in fields:
            if type(section[field]) not in (int, float) or not isfinite(section[field]) or section[field] < 0:
                raise ValueError(f'{field} must be finite and nonnegative')
    if not 0 < cross['training_paid_hours'] <= paid_hours:
        raise ValueError('Training must consume positive hours within a paid shift')
    if not 0 <= cross['max_redeployment_hours_per_day'] <= paid_hours:
        raise ValueError('Redeployment exceeds paid shift')
    if not 0 <= transfer['round_trip_paid_travel_hours'] < paid_hours:
        raise ValueError('Travel must leave time to work at destination')
    if any(not 0 < value <= 1 for value in (cross['picking_productivity_factor'], hire['productive_factor_after_training'])):
        raise ValueError('Productivity factors must be in (0, 1]')
    weekdays = hire['weekdays']
    if not isinstance(weekdays, list) or not 1 <= len(weekdays) <= 5 or len(set(weekdays)) != len(weekdays):
        raise ValueError('Hiring weekdays must be unique, with at most five working days')
    if any(type(day) is not int or not 0 <= day <= 6 for day in weekdays) or len(weekdays) * paid_hours > 40:
        raise ValueError('Invalid hiring weekly schedule')
    if not isinstance(transfer['allowed_routes'], list):
        raise ValueError('Routes must be a list')
    routes = transfer['allowed_routes']
    if any(not isinstance(route, list) or len(route) != 2 or route[0] == route[1] for route in routes):
        raise ValueError('Routes require distinct origin and destination')
    if len({tuple(route) for route in routes}) != len(routes):
        raise ValueError('Duplicate routes')
    if not isfinite(config['solver_seconds']) or config['solver_seconds'] <= 0:
        raise ValueError('Solver limit must be positive')


def solve_network(rows, roster, policy, config, paid_hours=8, productive_factor=0.85):
    validate_policy(policy, paid_hours)
    validate_actions(config, paid_hours, policy['ot_step_hours'])
    if not rows or not isfinite(paid_hours) or paid_hours <= 0 or not 0 < productive_factor <= 1:
        raise ValueError('Valid daily inputs and productive hours are required')
    paid, productive, step = F(paid_hours), F(productive_factor), F(policy['ot_step_hours'])
    target = F(policy['service_target'])
    cross, hire, transfer = (config[k] for k in ('cross_training', 'hiring', 'transfers'))
    if hire['candidate_pool_per_site'] and (len(hire['weekdays']) > policy['regular_days_per_week'] or
            len(hire['weekdays']) * paid_hours > policy['weekly_total_hours']):
        raise ValueError('Hiring schedule exceeds configured weekly policy')
    dates = sorted({row['planning_date'] for row in rows})
    if any(date.fromisoformat(day).isoformat() != day for day in dates) or any(
            date.fromisoformat(b) - date.fromisoformat(a) != timedelta(days=1) for a, b in zip(dates, dates[1:])):
        raise ValueError('Dates must be canonical and consecutive')
    groups = sorted({(row['site_id'], row['role_id']) for row in rows})
    data = {(r['site_id'], r['role_id'], r['planning_date']): r for r in rows}
    if len(data) != len(rows) or len(data) != len(groups) * len(dates):
        raise ValueError('Expected one complete row per site-role-date')
    if any(role not in (PICK, PACK) for _, role in groups):
        raise ValueError('Only modeled picking/packing inputs are supported')
    sites = sorted({site for site, _ in groups})
    if any(origin not in sites or destination not in sites for origin, destination in transfer['allowed_routes']):
        raise ValueError('Route references unknown site')
    workers = sorted([w for w in roster['workers'] if (w['site_id'], w['role_id']) in groups], key=lambda w: w['worker_id'])
    worker_map = {w['worker_id']: w for w in workers}
    if len(worker_map) != len(workers):
        raise ValueError('Duplicate baseline worker IDs')
    wage, rate = {}, {}
    for group in groups:
        sample = data[*group, dates[0]]
        wage[group], rate[group] = F(sample['median_hourly_wage']), F(sample['productivity_rate'])
        if min(wage[group], rate[group]) <= 0:
            raise ValueError('Wages and productivity must be positive')
        for day in dates:
            row = data[*group, day]
            required_productive_hours(row)
            if F(row['median_hourly_wage']) != wage[group] or F(row['productivity_rate']) != rate[group]:
                raise ValueError('Group rates must remain constant over the horizon')
            actual = sum(w['site_id'] == group[0] and w['role_id'] == group[1] and
                         date.fromisoformat(day).weekday() in w['weekdays'] for w in workers)
            if actual != row['scheduled_headcount'] or row['workload_quantity'] < 0:
                raise ValueError('Baseline coverage or workload mismatch')
    model = cp_model.CpModel()
    actions, changes, costs = [], defaultdict(list), []

    def action(kind, worker_id, day, site, role, upper, cost, effects, hours=0, **metadata):
        variable = model.new_int_var(0, upper, f'action_{len(actions)}')
        record = dict(kind=kind, worker_id=worker_id, date=day, site_id=site, role_id=role,
                      hours_per_unit=float(hours), cost_per_unit=float(cost), **metadata)
        actions.append((variable, upper, F(cost), record, effects))
        costs.append((variable, F(cost)))
        for key, amount in effects.items():
            changes[key].append((variable, amount))
        return variable

    regular_ot = {}
    for worker in workers:
        wid, site, role = (worker[k] for k in ('worker_id', 'site_id', 'role_id'))
        if len(set(worker['weekdays'])) != len(worker['weekdays']) or len(worker['weekdays']) > policy['regular_days_per_week']:
            raise ValueError('Invalid regular worker template')
        for day in dates:
            if date.fromisoformat(day).weekday() not in worker['weekdays']:
                continue
            maximum = 0 if day in policy['ot_unavailable_dates'] else int(F(policy['ot_daily_hours']) // step)
            regular_ot[wid, day] = action('overtime', wid, day, site, role, maximum,
                                          step * wage[site, role] * F(policy['ot_wage_multiplier']),
                                          {(site, role, day): step * productive}, step)
        weekly_limit = min(F(policy['ot_weekly_hours']), F(policy['weekly_total_hours']) - paid * len(worker['weekdays']))
        for week in {week_start(d) for d in dates}:
            model.add(sum(v for (w, d), v in regular_ot.items() if w == wid and week_start(d) == week)
                      <= int(weekly_limit // step))

    temp_ready = (date.fromisoformat(dates[0]) + timedelta(days=policy['temp_ready_delay_days'])).isoformat()
    for site, role in groups:
        for index in range(policy['temp_pool_per_site_role']):
            wid = f'temp:{site}:{role}:{index}'
            shifts = {}
            for day in dates:
                upper = int(day >= temp_ready and day not in policy['temp_unavailable_dates'])
                shifts[day] = action('temporary_shift', wid, day, site, role, upper,
                                      paid * wage[site, role] * F(policy['temp_wage_multiplier']),
                                      {(site, role, day): paid * productive * F(policy['temp_productivity_factor'])}, paid,
                                      ready_date=temp_ready)
            for start in range(len(dates)):
                model.add(sum(shifts[d] for d in dates[start:start + 7]) <= policy['regular_days_per_week'])

    eligibility = {'cross_training': [], 'hiring': [], 'transfers': []}
    for site in sites:
        if (site, PICK) not in groups or (site, PACK) not in groups:
            continue
        packers = [w for w in workers if w['site_id'] == site and w['role_id'] == PACK][:cross['eligible_packers_per_site']]
        for worker in packers:
            wid = worker['worker_id']
            scheduled = [d for d in dates if date.fromisoformat(d).weekday() in worker['weekdays']]
            if not scheduled:
                continue
            training_day = scheduled[0]
            training_hours = F(cross['training_paid_hours'])
            trained = action('cross_training', wid, training_day, site, PACK, 1, F(cross['external_trainer_fee']),
                             {(site, PACK, training_day): -training_hours * productive}, training_hours)
            eligibility['cross_training'].append(dict(worker_id=wid, training_date=training_day,
                                                       ready_date=(date.fromisoformat(training_day) + timedelta(days=1)).isoformat()))
            for day in scheduled[1:]:
                upper = int(F(cross['max_redeployment_hours_per_day']) // step)
                redeploy = action('cross_role_work', wid, day, site, PICK, upper, F(0),
                                  {(site, PACK, day): -step * productive,
                                   (site, PICK, day): step * productive * F(cross['picking_productivity_factor'])}, step,
                                  donor_role=PACK)
                model.add(redeploy <= upper * trained)

    hire_start = date.fromisoformat(dates[0]) + timedelta(days=hire['recruitment_lead_calendar_days'])
    hire_schedule = [d for d in dates if date.fromisoformat(d) >= hire_start and date.fromisoformat(d).weekday() in hire['weekdays']]
    if len(hire_schedule) > hire['paid_training_days']:
        training_dates = hire_schedule[:hire['paid_training_days']]
        production_dates = hire_schedule[hire['paid_training_days']:]
        for site in sites:
            if (site, PICK) not in groups:
                continue
            for index in range(hire['candidate_pool_per_site']):
                wid = f'hire:{site}:{index}'
                total_cost = F(hire['recruitment_and_external_training_fee']) + len(hire_schedule) * paid * wage[site, PICK]
                action('fixed_term_hire', wid, hire_schedule[0], site, PICK, 1, total_cost,
                       {(site, PICK, day): paid * productive * F(hire['productive_factor_after_training']) for day in production_dates},
                       len(hire_schedule) * paid, training_dates=training_dates, production_dates=production_dates,
                       ready_date=production_dates[0], paid_training_hours=float(len(training_dates) * paid))
                eligibility['hiring'].append(dict(worker_id=wid, ready_date=production_dates[0],
                                                 paid_dates=hire_schedule, training_dates=training_dates))

    transfer_ready = (date.fromisoformat(dates[0]) + timedelta(days=transfer['destination_readiness_delay_days'])).isoformat()
    transfer_vars = defaultdict(list)
    for origin in sites:
        candidates = [w for w in workers if w['site_id'] == origin and w['role_id'] == PICK][:transfer['eligible_pickers_per_site']]
        for worker in candidates:
            wid = worker['worker_id']
            destinations = [dest for source, dest in transfer['allowed_routes'] if source == origin and (dest, PICK) in groups]
            eligibility['transfers'].append(dict(worker_id=wid, destinations=destinations, ready_date=transfer_ready))
            for day in dates:
                if day < transfer_ready or date.fromisoformat(day).weekday() not in worker['weekdays']:
                    continue
                for destination in destinations:
                    variable = action('transfer', wid, day, destination, PICK, 1, F(transfer['transport_cost_per_person_day']),
                                      {(origin, PICK, day): -paid * productive,
                                       (destination, PICK, day): (paid - F(transfer['round_trip_paid_travel_hours'])) * productive},
                                      paid, origin_site_id=origin, travel_paid_hours=transfer['round_trip_paid_travel_hours'])
                    transfer_vars[wid, day].append(variable)
                model.add(sum(transfer_vars[wid, day]) <= 1)
                # Travel is within the paid regular day; transferred workers cannot also do origin overtime.
                for variable in transfer_vars[wid, day]:
                    model.add(regular_ot[wid, day] == 0).only_enforce_if(variable)

    for key, row in data.items():
        baseline = row['scheduled_headcount'] * paid * productive
        required = target * required_productive_hours(row)
        terms = changes[key]
        scale = lcm(baseline.denominator, required.denominator, *(amount.denominator for _, amount in terms))
        model.add(sum(int(amount * scale) * v for v, amount in terms) >= int((required - baseline) * scale))
    cost_scale = lcm(*(cost.denominator for _, cost in costs)) if costs else 1
    tie_scale = sum(upper for _, upper, _, _, _ in actions) + 1
    # Exact lexicographic weighting: cost first, action-unit count second.
    model.minimize(sum((int(cost * cost_scale) * tie_scale + 1) * v for v, cost in costs))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = config['solver_seconds']
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    output = dict(status=solver.status_name(status), incremental_cost=None, actions=[], daily_results=[],
                  validated=False, policy=policy, action_config=config, eligibility=eligibility)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return output
    total = F(0)
    for variable, _, cost, record, effects in actions:
        units = solver.value(variable)
        if units:
            output['actions'].append(record | dict(units=units, paid_hours=units * record['hours_per_unit'],
                                                   incremental_cost=float(units * cost)))
            total += units * cost
    output['incremental_cost'] = float(total)
    output['best_bound_cost'] = int(solver.best_objective_bound // tie_scale) / cost_scale
    output['daily_results'] = audit_solution(output, rows, roster, paid_hours, productive_factor)
    output['validated'] = True
    return output


def audit_solution(output, rows, roster, paid_hours, productive_factor):
    """Reconstruct capacity from decoded business actions, not solver expressions."""
    policy, config = output['policy'], output['action_config']
    cross, hire, transfer = (config[k] for k in ('cross_training', 'hiring', 'transfers'))
    workers = {w['worker_id']: w for w in roster['workers']}
    data = {(r['site_id'], r['role_id'], r['planning_date']): r for r in rows}
    capacity = {key: r['scheduled_headcount'] * paid_hours * productive_factor for key, r in data.items()}
    grouped = defaultdict(list)
    trained, weekly_ot, temp_days = {}, defaultdict(float), defaultdict(set)
    total_cost = 0.0
    for a in output['actions']:
        wid, day, kind, hours = a['worker_id'], a['date'], a['kind'], a['paid_hours']
        site, role = a['site_id'], a['role_id']
        grouped[wid, day].append(a)
        if a['units'] <= 0 or (kind not in ('overtime', 'cross_role_work') and a['units'] != 1):
            raise ValueError('Invalid action units')
        if kind in ('overtime', 'cross_training', 'cross_role_work', 'transfer'):
            if wid not in workers or date.fromisoformat(day).weekday() not in workers[wid]['weekdays']:
                raise ValueError('Action assigned to absent regular worker')
        if kind == 'cross_training':
            if wid not in {e['worker_id'] for e in output['eligibility']['cross_training']}:
                raise ValueError('Training eligibility missing')
            trained[wid] = day
            if hours != cross['training_paid_hours']:
                raise ValueError('Training paid hours mismatch')
            capacity[site, PACK, day] -= hours * productive_factor
            expected_cost = cross['external_trainer_fee']
        elif kind == 'cross_role_work':
            if wid not in trained or day <= trained[wid] or hours > cross['max_redeployment_hours_per_day'] + 1e-8:
                raise ValueError('Redeployment before training or above cap')
            capacity[site, PACK, day] -= hours * productive_factor
            capacity[site, PICK, day] += hours * productive_factor * cross['picking_productivity_factor']
            expected_cost = 0
        elif kind == 'transfer':
            origin = a['origin_site_id']
            eligible = next((e for e in output['eligibility']['transfers'] if e['worker_id'] == wid), None)
            if not eligible or site not in eligible['destinations'] or day < eligible['ready_date']:
                raise ValueError('Transfer eligibility missing')
            capacity[origin, PICK, day] -= paid_hours * productive_factor
            capacity[site, PICK, day] += (paid_hours - transfer['round_trip_paid_travel_hours']) * productive_factor
            expected_cost = transfer['transport_cost_per_person_day']
        elif kind == 'fixed_term_hire':
            wage = data[site, PICK, a['production_dates'][0]]['median_hourly_wage']
            all_days = a['training_dates'] + a['production_dates']
            eligible = next((e for e in output['eligibility']['hiring'] if e['worker_id'] == wid), None)
            if not eligible or all_days != eligible['paid_dates'] or a['training_dates'] != eligible['training_dates'] or a['ready_date'] != eligible['ready_date']:
                raise ValueError('Hire eligibility or guaranteed paid schedule mismatch')
            if hours != len(all_days) * paid_hours or a['paid_training_hours'] != len(a['training_dates']) * paid_hours:
                raise ValueError('Hire paid hours mismatch')
            if set(a['training_dates']) & set(a['production_dates']) or len(all_days) != len(set(all_days)):
                raise ValueError('Training and production days overlap')
            for production_day in a['production_dates']:
                if production_day < a['ready_date']:
                    raise ValueError('Hire used before ready')
                capacity[site, PICK, production_day] += paid_hours * productive_factor * hire['productive_factor_after_training']
            for d in all_days:
                if sum(0 <= (date.fromisoformat(other) - date.fromisoformat(d)).days < 7 for other in all_days) > 5:
                    raise ValueError('Hire weekly paid-day limit exceeded')
            expected_cost = len(all_days) * paid_hours * wage + hire['recruitment_and_external_training_fee']
        elif kind == 'overtime':
            if day in policy['ot_unavailable_dates'] or hours > policy['ot_daily_hours'] + 1e-8:
                raise ValueError('Overtime availability/cap exceeded')
            weekly_ot[wid, week_start(day)] += hours
            capacity[site, role, day] += hours * productive_factor
            expected_cost = hours * data[site, role, day]['median_hourly_wage'] * policy['ot_wage_multiplier']
        elif kind == 'temporary_shift':
            if day < a['ready_date'] or day in policy['temp_unavailable_dates'] or hours != paid_hours:
                raise ValueError('Temporary readiness/paid shift violation')
            temp_days[wid].add(day)
            capacity[site, role, day] += hours * productive_factor * policy['temp_productivity_factor']
            expected_cost = hours * data[site, role, day]['median_hourly_wage'] * policy['temp_wage_multiplier']
        else:
            raise ValueError('Unknown action')
        if abs(a['incremental_cost'] - expected_cost) > 1e-7:
            raise ValueError('Action cost mismatch')
        total_cost += expected_cost
    for assignments in grouped.values():
        kinds = [a['kind'] for a in assignments]
        if len(kinds) != len(set(kinds)):
            raise ValueError('Duplicate worker action on the same day')
        if any(a['kind'] == 'transfer' for a in assignments) and len(assignments) > 1:
            raise ValueError('Transferred worker double booked')
    for (wid, _), hours in weekly_ot.items():
        if hours > policy['ot_weekly_hours'] + 1e-8 or hours + len(workers[wid]['weekdays']) * paid_hours > policy['weekly_total_hours'] + 1e-8:
            raise ValueError('Weekly paid hours exceeded')
    for days in temp_days.values():
        for start in days:
            if sum(0 <= (date.fromisoformat(d) - date.fromisoformat(start)).days < 7 for d in days) > policy['regular_days_per_week']:
                raise ValueError('Temporary worker rolling-day limit exceeded')
    if abs(total_cost - output['incremental_cost']) > 1e-6:
        raise ValueError('Total cost mismatch')
    results = []
    for key, row in data.items():
        covered = capacity[key] * row['productivity_rate']
        required = float(required_productive_hours(row))
        if capacity[key] + 1e-6 < policy['service_target'] * required:
            raise ValueError(f'Decoded solution creates a shortage at {key}')
        results.append(dict(site_id=key[0], role_id=key[1], date=key[2], demand=row['workload_quantity'],
                            capacity_quantity=covered, target_met=True,
                            demand_basis='productive_hours' if 'productive_demand_hours' in row else 'legacy_quantity',
                            required_productive_hours=required,
                            available_productive_hours=capacity[key]))
        if 'productive_demand_hours' in row:
            # Quantity equivalents are not physical parcels for a time-based scenario.
            results[-1].pop('demand')
            results[-1].pop('capacity_quantity')
    return results

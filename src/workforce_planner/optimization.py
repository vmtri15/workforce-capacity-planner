"""Finite-pool overtime/temporary staffing optimization for a fixed synthetic roster."""
from collections import defaultdict
from datetime import date, timedelta
from fractions import Fraction
from math import isfinite, lcm

from ortools.sat.python import cp_model


def fraction(value):
    return Fraction(str(value))


def validate_policy(policy, paid_hours):
    for key in ('service_target', 'ot_step_hours', 'ot_daily_hours', 'ot_weekly_hours',
                'weekly_total_hours', 'ot_wage_multiplier', 'temp_wage_multiplier',
                'temp_productivity_factor', 'solver_seconds_per_group'):
        if type(policy[key]) not in (float, int) or not isfinite(policy[key]):
            raise ValueError(f'{key} must be a finite number')
    for key in ('regular_days_per_week', 'temp_pool_per_site_role', 'temp_ready_delay_days'):
        value = policy[key]
        if type(value) is not int or value < 0:
            raise ValueError(f'{key} must be a nonnegative integer')
    if not 1 <= policy['regular_days_per_week'] <= 5:
        raise ValueError('regular_days_per_week must be between 1 and 5')
    for key in ('service_target', 'temp_productivity_factor'):
        if not 0 < policy[key] <= 1:
            raise ValueError(f'{key} must be in (0, 1]')
    for key in ('ot_step_hours', 'ot_wage_multiplier', 'temp_wage_multiplier', 'solver_seconds_per_group'):
        if policy[key] <= 0:
            raise ValueError(f'{key} must be positive')
    for key in ('ot_daily_hours', 'ot_weekly_hours', 'weekly_total_hours'):
        if policy[key] < 0:
            raise ValueError(f'{key} must be nonnegative')
    if paid_hours * policy['regular_days_per_week'] > 40:
        raise ValueError('Regular template exceeds the 40-hour prototype baseline')
    if policy['weekly_total_hours'] < paid_hours * policy['regular_days_per_week']:
        raise ValueError('Weekly cap is below regular template hours')
    for key in ('ot_unavailable_dates', 'temp_unavailable_dates'):
        if not isinstance(policy[key], list):
            raise ValueError(f'{key} must be a list of YYYY-MM-DD dates')
        for value in policy[key]:
            if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                raise ValueError(f'{key} must contain canonical YYYY-MM-DD dates')


def week_start(value):
    day = date.fromisoformat(value)
    return (day - timedelta(days=day.weekday())).isoformat()


def solve_group(rows, workers, policy, paid_hours, productive_factor):
    """Exact integer capacity coefficients; daily demand, no backlog or shift timing."""
    dates = [row['planning_date'] for row in rows]
    if dates != sorted(set(dates)) or not dates:
        raise ValueError('Expected sorted unique dates')
    if any(date.fromisoformat(b) - date.fromisoformat(a) != timedelta(days=1)
           for a, b in zip(dates, dates[1:])):
        raise ValueError('Daily rows must be consecutive')
    for field in ('productivity_rate', 'median_hourly_wage', 'site_id', 'role_id'):
        if any(row[field] != rows[0][field] for row in rows):
            raise ValueError(f'Group requires a constant {field}')
    model = cp_model.CpModel()
    paid, productive, step = map(fraction, (paid_hours, productive_factor, policy['ot_step_hours']))
    rate = fraction(rows[0]['productivity_rate'])
    target = fraction(policy['service_target'])
    ot_capacity = step * productive * rate
    temp_capacity = paid * productive * rate * fraction(policy['temp_productivity_factor'])
    scale = lcm(ot_capacity.denominator, temp_capacity.denominator, target.denominator,
                (paid * productive * rate).denominator)
    wage = fraction(rows[0]['median_hourly_wage'])
    ot_cost = step * wage * fraction(policy['ot_wage_multiplier'])
    temp_cost = paid * wage * fraction(policy['temp_wage_multiplier'])
    cost_scale = lcm(ot_cost.denominator, temp_cost.denominator)
    max_daily = int(fraction(policy['ot_daily_hours']) // step)
    ot, temps = {}, {}
    weeks = sorted({week_start(day) for day in dates})
    for worker in workers:
        worker_id = worker['worker_id']
        for day in dates:
            scheduled = date.fromisoformat(day).weekday() in worker['weekdays']
            limit = max_daily if scheduled and day not in policy['ot_unavailable_dates'] else 0
            ot[worker_id, day] = model.new_int_var(0, limit, f'ot_{worker_id}_{day}')
        # Template continues before/after horizon; reserve regular hours for full weeks.
        weekly_budget = min(fraction(policy['ot_weekly_hours']),
                            fraction(policy['weekly_total_hours']) - paid * len(worker['weekdays']))
        for week in weeks:
            model.add(sum(ot[worker_id, day] for day in dates if week_start(day) == week)
                      <= int(weekly_budget // step))
    ready_date = (date.fromisoformat(dates[0]) + timedelta(days=policy['temp_ready_delay_days'])).isoformat()
    for worker_index in range(policy['temp_pool_per_site_role']):
        for day in dates:
            available = day >= ready_date and day not in policy['temp_unavailable_dates']
            temps[worker_index, day] = model.new_bool_var(f'temp_{worker_index}_{day}')
            if not available:
                model.add(temps[worker_index, day] == 0)
        for week in weeks:
            model.add(sum(temps[worker_index, day] for day in dates if week_start(day) == week)
                      <= policy['regular_days_per_week'])
        # Finite worker, at most five shifts in each rolling seven-day window.
        for index in range(len(dates)):
            model.add(sum(temps[worker_index, day] for day in dates[index:index + 7])
                      <= policy['regular_days_per_week'])
    for row in rows:
        day = row['planning_date']
        scheduled = sum(date.fromisoformat(day).weekday() in w['weekdays'] for w in workers)
        if scheduled != row['scheduled_headcount']:
            raise ValueError('Roster does not preserve baseline staffing')
        baseline = scheduled * paid * productive * rate
        demand = target * row['workload_quantity']
        model.add(int(ot_capacity * scale) * sum(ot[w['worker_id'], day] for w in workers)
                  + int(temp_capacity * scale) * sum(temps[i, day] for i in range(policy['temp_pool_per_site_role']))
                  >= int((demand - baseline) * scale))
    model.minimize(int(ot_cost * cost_scale) * sum(ot.values())
                   + int(temp_cost * cost_scale) * sum(temps.values()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = policy['solver_seconds_per_group']
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    result = dict(site_id=rows[0]['site_id'], role_id=rows[0]['role_id'], status=solver.status_name(status),
                  temp_ready_date=ready_date, incremental_cost=None, actions=[], daily_results=[],
                  daily_capacity_upper_bound_shortfalls=[])
    for row in rows:
        day = row['planning_date']
        baseline = row['scheduled_headcount'] * paid * productive * rate
        ot_upper = 0 if day in policy['ot_unavailable_dates'] else row['scheduled_headcount'] * max_daily * ot_capacity
        temp_upper = (policy['temp_pool_per_site_role'] * temp_capacity
                      if day >= ready_date and day not in policy['temp_unavailable_dates'] else 0)
        shortfall = target * row['workload_quantity'] - baseline - ot_upper - temp_upper
        if shortfall > 0:
            result['daily_capacity_upper_bound_shortfalls'].append(
                dict(date=day, missing_workload_quantity=float(shortfall)))
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return result
    actions = result['actions']
    for (worker_id, day), variable in ot.items():
        units = solver.value(variable)
        if units:
            actions.append(dict(worker_id=worker_id, date=day, action='overtime',
                                paid_hours=float(units * step), incremental_cost=float(units * ot_cost)))
    for (index, day), variable in temps.items():
        if solver.value(variable):
            actions.append(dict(worker_id=f"temp_{rows[0]['site_id']}_{rows[0]['role_id']}_{index:03}",
                                date=day, action='temporary_shift', paid_hours=float(paid),
                                incremental_cost=float(temp_cost)))
    result['incremental_cost'] = sum(a['incremental_cost'] for a in actions)
    result['best_bound_cost'] = solver.best_objective_bound / cost_scale
    for row in rows:
        day = row['planning_date']
        extra = sum(a['paid_hours'] * float(productive) * float(rate)
                    * (policy['temp_productivity_factor'] if a['action'] == 'temporary_shift' else 1)
                    for a in actions if a['date'] == day)
        capacity = row['scheduled_headcount'] * float(paid * productive * rate) + extra
        demand = row['workload_quantity']
        result['daily_results'].append(dict(date=day, demand=demand, capacity=capacity,
                                           target_met=capacity + 1e-7 >= demand * float(target)))
    validate_group(result, workers, policy, paid_hours)
    return result


def validate_group(result, workers, policy, paid_hours):
    """Check decoded actions independently of solver variables and constraints."""
    lookup = {w['worker_id']: w for w in workers}
    weekly, temp_dates = defaultdict(float), defaultdict(set)
    seen = set()
    for action in result['actions']:
        worker, day, hours = action['worker_id'], action['date'], action['paid_hours']
        if (worker, day) in seen:
            raise ValueError('Duplicate worker assignment')
        seen.add((worker, day))
        weekly[worker, week_start(day)] += hours
        if action['action'] == 'overtime':
            if date.fromisoformat(day).weekday() not in lookup[worker]['weekdays']:
                raise ValueError('Overtime on an unscheduled day')
            if day in policy['ot_unavailable_dates'] or hours > policy['ot_daily_hours'] + 1e-8:
                raise ValueError('Overtime exceeds availability')
        else:
            if day < result['temp_ready_date'] or day in policy['temp_unavailable_dates']:
                raise ValueError('Temporary worker not ready/available')
            if hours != paid_hours:
                raise ValueError('Temporary shift length mismatch')
            temp_dates[worker].add(date.fromisoformat(day))
    if len(temp_dates) > policy['temp_pool_per_site_role']:
        raise ValueError('Temporary pool exceeded')
    for (worker, _), hours in weekly.items():
        if worker in lookup:
            regular = len(lookup[worker]['weekdays']) * paid_hours
            if hours > policy['ot_weekly_hours'] + 1e-8 or hours + regular > policy['weekly_total_hours'] + 1e-8:
                raise ValueError('Weekly overtime/total cap exceeded')
        elif hours > paid_hours * policy['regular_days_per_week'] + 1e-8:
            raise ValueError('Temporary weekly shift limit exceeded')
    for days in temp_dates.values():
        for start in days:
            if sum(start <= day < start + timedelta(days=7) for day in days) > policy['regular_days_per_week']:
                raise ValueError('Temporary rolling rest limit exceeded')
    if not all(day['target_met'] for day in result['daily_results']):
        raise ValueError('Decoded solution misses service target')


def optimize(rows, roster, policy, paid_hours, productive_factor):
    validate_policy(policy, paid_hours)
    if not rows:
        raise ValueError('No planning inputs')
    if not isfinite(paid_hours) or paid_hours <= 0 or not isfinite(productive_factor) or not 0 < productive_factor <= 1:
        raise ValueError('Invalid paid hours or productive factor')
    groups = defaultdict(list)
    for row in rows:
        groups[row['site_id'], row['role_id']].append(row)
    results = []
    for (site, role), group in sorted(groups.items()):
        workers = [w for w in roster['workers'] if w['site_id'] == site and w['role_id'] == role]
        results.append(solve_group(sorted(group, key=lambda r: r['planning_date']), workers,
                                   policy, paid_hours, productive_factor))
    statuses = {r['status'] for r in results}
    complete = statuses <= {'OPTIMAL', 'FEASIBLE'}
    status = 'OPTIMAL' if statuses == {'OPTIMAL'} else ('FEASIBLE' if complete else
             ('INFEASIBLE' if 'INFEASIBLE' in statuses else 'UNKNOWN'))
    return dict(status=status, incremental_cost=sum(r['incremental_cost'] for r in results) if complete else None,
                policy=policy, groups=results, validated=complete)

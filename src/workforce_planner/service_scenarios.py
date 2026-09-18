"""FIFO unit-service accounting with explicit operating-day deadlines."""
from collections import deque
from datetime import timedelta
from decimal import Decimal


def deadline(arrival, operating_days, weekdays):
    if type(operating_days) is not int or operating_days < 1:
        raise ValueError('Service window must be a positive integer')
    if not weekdays or any(type(d) is not int or d not in range(7) for d in weekdays):
        raise ValueError('Operating weekdays must be nonempty integers 0-6')
    day = arrival
    remaining = operating_days
    while True:
        if day.weekday() in weekdays:
            remaining -= 1
            if remaining == 0:
                return day
        day += timedelta(days=1)


def simulate(demand, workers, absent, rate, service_days, config, capacity_policy=None):
    if not demand or any(type(q) is not int or q < 0 for q in demand.values()):
        raise ValueError('Nonempty nonnegative integer demand required')
    if type(workers) is not int or type(absent) is not int or not 0 <= absent <= workers:
        raise ValueError('Invalid staffing')
    hours, factor, rate = (Decimal(str(v)) for v in (config['paid_hours'], config['productive_factor'], rate))
    if not all(v.is_finite() for v in (hours, factor, rate)) or hours <= 0 or rate <= 0 or not 0 < factor <= 1:
        raise ValueError('Invalid capacity assumptions')
    if config['recovery_calendar_days'] < 0:
        raise ValueError('Invalid recovery window')
    if any(config[k] != 0 for k in ('initial_backlog_units', 'overtime_hours', 'temporary_workers')):
        raise ValueError('This experiment supports zero opening backlog and no interventions')
    weekdays = config['operating_weekdays']
    deadline(min(demand), service_days, weekdays)
    capacity = int((workers-absent) * hours * factor * rate)
    queue = deque()
    day, last = min(demand), max(demand) + timedelta(days=config['recovery_calendar_days'])
    on_time = late = 0
    rows = []
    while day <= last:
        opening = sum(b[1] for b in queue)
        arrivals = demand.get(day, 0)
        if arrivals:
            queue.append([deadline(day, service_days, weekdays), arrivals])
        available = capacity if day.weekday() in weekdays else 0
        policy_fields = {}
        if capacity_policy is not None:
            available, policy_fields = capacity_policy(day, tuple((b[0], b[1]) for b in queue), available)
            if type(available) is not int or available < 0:
                raise ValueError('Policy capacity must be a nonnegative integer')
        remaining = available
        timely_today = late_today = 0
        while queue and remaining:
            batch = queue[0]
            amount = min(batch[1], remaining)
            if day <= batch[0]:
                timely_today += amount
            else:
                late_today += amount
            batch[1] -= amount
            remaining -= amount
            if batch[1] == 0:
                queue.popleft()
        closing = sum(b[1] for b in queue)
        assert opening + arrivals == timely_today + late_today + closing
        on_time += timely_today
        late += late_today
        rows.append(dict(policy_fields, date=str(day), arrivals=arrivals, capacity=available,
                         opening_backlog=opening, completed_on_time=timely_today,
                         completed_late=late_today, closing_backlog=closing,
                         past_due_at_close=sum(b[1] for b in queue if b[0] <= day)))
        day += timedelta(days=1)
    total = sum(demand.values())
    pending = sum(b[1] for b in queue if b[0] > last)
    overdue = sum(b[1] for b in queue if b[0] <= last)
    share = on_time / total if total else None
    return dict(workers=workers, absent=absent, present_workers=workers-absent,
                rate=float(rate), service_days=service_days, arrivals=total,
                completed_on_time=on_time, completed_late=late,
                overdue_unfinished=overdue, pending_not_due=pending,
                on_time_unit_share=share,
                target_met=(share >= config['target_on_time_unit_share']) if share is not None and not pending else None,
                peak_backlog=max(r['closing_backlog'] for r in rows),
                backlog_unit_days=sum(r['closing_backlog'] for r in rows)), rows

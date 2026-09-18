"""Reactive staffing rules using only demand already arrived."""
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING


def make_policy(workers, absent, rate, overtime_limit, temp_limit, lead_days, config, costs):
    if type(lead_days) is not int or lead_days < 1:
        raise ValueError('Temporary lead time must be at least one operating day')
    if overtime_limit < 0 or type(temp_limit) is not int or temp_limit < 0:
        raise ValueError('Invalid action limits')
    d = lambda value: Decimal(str(value))
    hours, factor, throughput = d(config['paid_hours']), d(config['productive_factor']), d(rate)
    regular_rate = d(costs['regular_hourly_cost'])
    overtime_rate = regular_rate * d(costs['overtime_multiplier'])
    temp_rate = d(costs['temporary_hourly_cost'])
    temp_factor = d(costs['temporary_productivity_factor'])
    if any(not v.is_finite() or v <= 0 for v in (regular_rate,overtime_rate,temp_rate,temp_factor)):
        raise ValueError('Costs and temporary productivity must be positive finite values')
    bookings = {}

    def policy(day, queue, base_capacity):
        fields = dict(regular_cost=0.0, overtime_cost=0.0, temporary_cost=0.0,
                      overtime_paid_hours=0, temporary_workers=0, booked_future_workers=0)
        if day.weekday() not in config['operating_weekdays']:
            return base_capacity, fields
        temps = bookings.pop(day, 0)
        capacity = base_capacity + int(d(temps) * hours * factor * throughput * temp_factor)
        due = sum(q for due_date,q in queue if due_date <= day)
        shortfall = max(0, due-capacity)
        ot_hours = min(int((d(shortfall)/(factor*throughput)).to_integral_value(rounding=ROUND_CEILING)),
                       int((workers-absent)*overtime_limit))
        capacity += int(d(ot_hours)*factor*throughput)
        # Book against today's residual queue; no future arrivals are consulted.
        future = day
        for _ in range(lead_days):
            future += timedelta(days=1)
            while future.weekday() not in config['operating_weekdays']:
                future += timedelta(days=1)
        residual = max(0, sum(q for _,q in queue)-capacity)
        already_booked = sum(int(d(n)*hours*factor*throughput*temp_factor) for n in bookings.values())
        need = max(0, residual-base_capacity*lead_days-already_booked)
        per_temp = hours*factor*throughput*temp_factor
        booking = min(temp_limit, int((d(need)/per_temp).to_integral_value(rounding=ROUND_CEILING)))
        if booking:
            bookings[future] = booking
        fields.update(regular_cost=float(d(workers)*hours*regular_rate),
                      overtime_cost=float(d(ot_hours)*overtime_rate),
                      temporary_cost=float(d(temps)*hours*temp_rate),
                      overtime_paid_hours=ot_hours, temporary_workers=temps,
                      booked_future_workers=booking)
        return capacity, fields
    policy.outstanding_shifts = lambda: sum(bookings.values())
    return policy

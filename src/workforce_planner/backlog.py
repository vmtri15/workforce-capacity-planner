"""Daily FIFO simulation in whole units; no inferred employee attendance."""

from collections import deque
from datetime import date, timedelta


def simulate_backlog(days):
    queue = deque()
    results = []
    previous = None
    for row in days:
        current = date.fromisoformat(row['date'])
        if previous is not None and current != previous + timedelta(days=1):
            raise ValueError('Days must be unique, consecutive and ascending')
        previous = current
        for key in ('arrivals', 'capacity'):
            if type(row[key]) is not int or row[key] < 0:
                raise ValueError(f'{key} must be a nonnegative integer')
        opening = sum(batch[1] for batch in queue)
        if row['arrivals']:
            queue.append([current, row['arrivals']])
        remaining = row['capacity']
        completed = 0
        while queue and remaining:
            amount = min(queue[0][1], remaining)
            queue[0][1] -= amount
            remaining -= amount
            completed += amount
            if not queue[0][1]:
                queue.popleft()
        closing = sum(batch[1] for batch in queue)
        assert opening + row['arrivals'] == completed + closing
        results.append(dict(row, opening_backlog=opening, completed=completed,
                            closing_backlog=closing, unused_capacity=remaining,
                            oldest_backlog_days=(current - queue[0][0]).days if queue else 0))
    return results

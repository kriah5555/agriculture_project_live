"""Small reusable helpers shared by the admin analytics pages (Admin Overview
dashboard, Payment History overview) — month bucketing and trend formatting.
No models/queries here, just pure helpers so both pages compute things the
same way."""
from calendar import month_abbr

from django.utils import timezone


def month_buckets(n):
    """Last n calendar months (oldest -> newest) as (year, month) tuples."""
    now = timezone.now()
    buckets = []
    y, m = now.year, now.month
    for _ in range(n):
        buckets.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    buckets.reverse()
    return buckets


def month_labels(buckets):
    return [f'{month_abbr[m]} {y}' for (y, m) in buckets]


def fill_monthly(rows, buckets, value_key='count'):
    """rows: iterable of {'month': datetime, value_key: number} (e.g. from
    .annotate(month=TruncMonth(...)).values('month').annotate(<value_key>=...))."""
    lookup = {(row['month'].year, row['month'].month): row[value_key] for row in rows if row['month']}
    return [lookup.get(b, 0) for b in buckets]


def pct_change(current, previous):
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round((current - previous) / previous * 100, 1)


def trend_fields(prefix, current, previous):
    pct = pct_change(current, previous)
    return {
        f'{prefix}_trend_class': 'up' if pct >= 0 else 'down',
        f'{prefix}_trend_icon' : 'fa-arrow-up' if pct >= 0 else 'fa-arrow-down',
        f'{prefix}_trend_text' : f'{"+" if pct >= 0 else ""}{pct}%',
    }


def format_inr_short(amount):
    amount = float(amount)
    if amount >= 1e7:
        return f'₹{amount / 1e7:.2f}Cr'
    if amount >= 1e5:
        return f'₹{amount / 1e5:.2f}L'
    if amount >= 1e3:
        return f'₹{amount / 1e3:.1f}K'
    return f'₹{amount:.0f}'


def format_count_short(n):
    if n >= 1000:
        return f'{n / 1000:.1f}K'
    return str(n)
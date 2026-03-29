"""
Statistics helpers for owner and group dashboards.

These functions keep route handlers thin and templates simple.
"""

from datetime import date, datetime, timedelta

from . import data_access


def _parse_expense_date(raw_value):
    if not raw_value:
        return None

    for parser in (date.fromisoformat, datetime.fromisoformat):
        try:
            parsed = parser(raw_value)
            return parsed.date() if isinstance(parsed, datetime) else parsed
        except (TypeError, ValueError):
            continue

    return None


def _money(value):
    return round(float(value or 0), 2)


def _build_trend_points(expenses, days=7):
    today = date.today()
    start_date = today - timedelta(days=days - 1)
    buckets = {}

    for offset in range(days):
        current = start_date + timedelta(days=offset)
        buckets[current] = 0.0

    for expense in expenses:
        expense_date = _parse_expense_date(expense.get('date'))
        if expense_date in buckets:
            buckets[expense_date] += _money(expense.get('total_amount'))

    peak = max(buckets.values(), default=0.0)
    points = []
    for current, amount in buckets.items():
        height = 12
        if peak > 0:
            height = max(12, int((amount / peak) * 120))
        points.append({
            'label': current.strftime('%d/%m'),
            'amount': round(amount, 2),
            'height': height,
        })
    return points


def get_home_stats():
    groups = data_access.fetch_all_groups_including_inactive()
    active_groups = [group for group in groups if not group.get('deactivated_at')]
    archived_groups = [group for group in groups if group.get('deactivated_at')]
    all_expenses = data_access.fetch_all_expenses()

    total_members = sum(len(data_access.fetch_users_in_group(group['id'])) for group in active_groups)
    total_spent = sum(_money(expense.get('total_amount')) for expense in all_expenses)
    expense_count = len(all_expenses)

    return {
        'overview': {
            'active_groups': len(active_groups),
            'archived_groups': len(archived_groups),
            'total_members': total_members,
        },
        'volume': {
            'total_spent': round(total_spent, 2),
            'average_expense': round(total_spent / expense_count, 2) if expense_count else 0.0,
            'average_per_group': round(total_spent / len(active_groups), 2) if active_groups else 0.0,
        },
        'timeline': _build_trend_points(all_expenses, days=7),
    }


def get_group_stats(group_id):
    members = data_access.fetch_users_in_group(group_id)
    expenses = data_access.fetch_expenses_in_group(group_id)
    member_names = {member['id']: member['name'] for member in members}
    total_spent = sum(_money(expense.get('total_amount')) for expense in expenses)
    expense_dates = [
        _parse_expense_date(expense.get('date'))
        for expense in expenses
        if _parse_expense_date(expense.get('date'))
    ]
    expense_dates.sort()

    payer_totals = {member['id']: 0.0 for member in members}
    for expense in expenses:
        payer_totals[expense['payer_id']] = payer_totals.get(expense['payer_id'], 0.0) + _money(expense['total_amount'])

    top_payers = []
    peak_paid = max(payer_totals.values(), default=0.0)
    for member in members:
        amount_paid = round(payer_totals.get(member['id'], 0.0), 2)
        height = 12
        if peak_paid > 0:
            height = max(12, int((amount_paid / peak_paid) * 120))
        top_payers.append({
            'name': member_names.get(member['id'], 'Unknown'),
            'amount': amount_paid,
            'height': height,
        })
    top_payers.sort(key=lambda payer: payer['amount'], reverse=True)

    average_gap_days = 0.0
    if len(expense_dates) >= 2:
        deltas = []
        for index in range(1, len(expense_dates)):
            deltas.append((expense_dates[index] - expense_dates[index - 1]).days)
        average_gap_days = round(sum(deltas) / len(deltas), 1) if deltas else 0.0

    return {
        'overview': {
            'total_spent': round(total_spent, 2),
            'expense_count': len(expenses),
            'average_expense': round(total_spent / len(expenses), 2) if expenses else 0.0,
        },
        'top_payers': top_payers,
        'frequency': {
            'expense_count': len(expenses),
            'active_days': len(set(expense_dates)),
            'average_gap_days': average_gap_days,
            'last_activity': expense_dates[-1].isoformat() if expense_dates else None,
            'timeline': _build_trend_points(expenses, days=7),
        },
    }

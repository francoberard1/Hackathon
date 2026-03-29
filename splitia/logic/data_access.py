"""
Data access layer for SplitIA.

This module supports two backends:
- Supabase/Postgres when environment variables are present
- Local in-memory dictionaries as a fallback for local hacking

By isolating storage code here, routes and business logic do not need to
change when the persistence backend changes.
"""

from datetime import date, datetime, timezone

from .supabase_client import get_supabase_client, has_supabase_config

# In-memory storage (local MVP mode)
groups = {}          # {group_id: {'id', 'name', 'members'}}
users = {}           # {user_id: {'id', 'name', 'group_id'}}
expenses = {}        # {expense_id: {'id', 'description', 'total_amount', 'payer_id', 'group_id'}}
expense_shares = {}  # {share_id: {'id', 'expense_id', 'user_id', 'amount'}}

# Mutable counters to generate unique IDs without global statements.
counters = {
    'group': 0,
    'user': 0,
    'expense': 0,
    'share': 0,
}


def _using_supabase():
    """Return True when the app should use Supabase instead of local memory."""
    return has_supabase_config()


def _response_rows(response):
    return getattr(response, 'data', None) or []


def _single_row(response):
    rows = _response_rows(response)
    return rows[0] if rows else None


def _to_group(row, members=None):
    if not row:
        return None
    return {
        'id': row['id'],
        'name': row['name'],
        'members': members if members is not None else [],
        'deactivated_at': row.get('deactivated_at'),
    }


def _to_user(row):
    if not row:
        return None
    return {
        'id': row['id'],
        'name': row['name'],
        'group_id': row['group_id'],
    }


def _to_expense(row):
    if not row:
        return None
    return {
        'id': row['id'],
        'description': row['description'],
        'total_amount': float(row['total_amount']),
        'payer_id': row['payer_id'],
        'group_id': row['group_id'],
        'date': row.get('expense_date'),
    }


def _to_share(row):
    if not row:
        return None
    return {
        'id': row['id'],
        'expense_id': row['expense_id'],
        'user_id': row['user_id'],
        'amount': float(row['amount']),
    }


def insert_group(name):
    """Create a group record."""
    if _using_supabase():
        supabase = get_supabase_client()
        row = _single_row(
            supabase.table('groups')
            .insert({'name': name})
            .execute()
        )
        return row['id']

    counters['group'] += 1
    group_id = counters['group']

    groups[group_id] = {
        'id': group_id,
        'name': name,
        'members': [],
        'deactivated_at': None,
    }
    return group_id


def fetch_group(group_id):
    """Fetch one group by ID."""
    if _using_supabase():
        supabase = get_supabase_client()
        row = _single_row(
            supabase.table('groups')
            .select('id, name, deactivated_at')
            .eq('id', group_id)
            .is_('deactivated_at', 'null')
            .limit(1)
            .execute()
        )
        if not row:
            return None
        members = fetch_users_in_group(group_id)
        return _to_group(row, members=[member['id'] for member in members])

    return groups.get(group_id)


def fetch_all_groups():
    """Fetch all groups."""
    if _using_supabase():
        supabase = get_supabase_client()
        rows = _response_rows(
            supabase.table('groups')
            .select('id, name, deactivated_at')
            .is_('deactivated_at', 'null')
            .order('id')
            .execute()
        )
        groups_with_members = []
        for row in rows:
            members = fetch_users_in_group(row['id'])
            groups_with_members.append(_to_group(row, members=[member['id'] for member in members]))
        return groups_with_members

    return [group for group in groups.values() if not group.get('deactivated_at')]


def fetch_all_groups_including_inactive():
    """Fetch all groups, including soft-deleted ones."""
    if _using_supabase():
        supabase = get_supabase_client()
        rows = _response_rows(
            supabase.table('groups')
            .select('id, name, deactivated_at')
            .order('id')
            .execute()
        )
        groups_with_members = []
        for row in rows:
            members = fetch_users_in_group(row['id'])
            groups_with_members.append(_to_group(row, members=[member['id'] for member in members]))
        return groups_with_members

    return list(groups.values())


def delete_group_record(group_id):
    """Soft-delete one group record."""
    if _using_supabase():
        supabase = get_supabase_client()
        supabase.table('groups').update({
            'deactivated_at': datetime.now(timezone.utc).isoformat(),
        }).eq('id', group_id).execute()
        return

    if group_id in groups:
        groups[group_id]['deactivated_at'] = datetime.now(timezone.utc).isoformat()


def insert_user(name, group_id):
    """Create a user and attach it to the group's member list."""
    if _using_supabase():
        supabase = get_supabase_client()
        row = _single_row(
            supabase.table('users')
            .insert({'name': name, 'group_id': group_id})
            .execute()
        )
        return row['id']

    counters['user'] += 1
    user_id = counters['user']

    users[user_id] = {
        'id': user_id,
        'name': name,
        'group_id': group_id
    }

    groups[group_id]['members'].append(user_id)
    return user_id


def fetch_user(user_id):
    """Fetch one user by ID."""
    if _using_supabase():
        supabase = get_supabase_client()
        row = _single_row(
            supabase.table('users')
            .select('id, name, group_id')
            .eq('id', user_id)
            .limit(1)
            .execute()
        )
        return _to_user(row)

    return users.get(user_id)


def fetch_users_in_group(group_id):
    """Fetch all users that belong to a group."""
    if _using_supabase():
        supabase = get_supabase_client()
        rows = _response_rows(
            supabase.table('users')
            .select('id, name, group_id')
            .eq('group_id', group_id)
            .order('id')
            .execute()
        )
        return [_to_user(row) for row in rows]

    group = groups.get(group_id)
    if not group:
        return []
    return [users[uid] for uid in group['members'] if uid in users]


def delete_user_record(user_id):
    """Delete one user and remove membership reference from its group."""
    if _using_supabase():
        supabase = get_supabase_client()
        supabase.table('users').delete().eq('id', user_id).execute()
        return

    if user_id not in users:
        return

    group_id = users[user_id]['group_id']
    if group_id in groups and user_id in groups[group_id]['members']:
        groups[group_id]['members'].remove(user_id)

    del users[user_id]


def insert_expense(description, total_amount, payer_id, group_id, expense_date=None):
    """Create an expense record."""
    expense_date = expense_date or date.today().isoformat()

    if _using_supabase():
        supabase = get_supabase_client()
        row = _single_row(
            supabase.table('expenses')
            .insert({
                'description': description,
                'total_amount': total_amount,
                'payer_id': payer_id,
                'group_id': group_id,
                'expense_date': expense_date,
            })
            .execute()
        )
        return row['id']

    counters['expense'] += 1
    expense_id = counters['expense']

    expenses[expense_id] = {
        'id': expense_id,
        'description': description,
        'total_amount': total_amount,
        'payer_id': payer_id,
        'group_id': group_id,
        'date': expense_date,
    }
    return expense_id


def fetch_expense(expense_id):
    """Fetch one expense by ID."""
    if _using_supabase():
        supabase = get_supabase_client()
        row = _single_row(
            supabase.table('expenses')
            .select('id, description, total_amount, payer_id, group_id, expense_date')
            .eq('id', expense_id)
            .limit(1)
            .execute()
        )
        return _to_expense(row)

    return expenses.get(expense_id)


def fetch_expenses_in_group(group_id):
    """Fetch all expenses belonging to one group."""
    if _using_supabase():
        supabase = get_supabase_client()
        rows = _response_rows(
            supabase.table('expenses')
            .select('id, description, total_amount, payer_id, group_id, expense_date')
            .eq('group_id', group_id)
            .order('id')
            .execute()
        )
        return [_to_expense(row) for row in rows]

    return [expense for expense in expenses.values() if expense['group_id'] == group_id]


def fetch_all_expenses():
    """Fetch every expense across all groups."""
    if _using_supabase():
        supabase = get_supabase_client()
        rows = _response_rows(
            supabase.table('expenses')
            .select('id, description, total_amount, payer_id, group_id, expense_date')
            .order('expense_date')
            .order('id')
            .execute()
        )
        return [_to_expense(row) for row in rows]

    return list(expenses.values())


def delete_expense_record(expense_id):
    """Delete an expense and all share rows attached to it."""
    if _using_supabase():
        supabase = get_supabase_client()
        supabase.table('expense_shares').delete().eq('expense_id', expense_id).execute()
        supabase.table('expenses').delete().eq('id', expense_id).execute()
        return

    if expense_id not in expenses:
        return

    del expenses[expense_id]
    shares_to_delete = [
        share_id for share_id, share in expense_shares.items()
        if share['expense_id'] == expense_id
    ]
    for share_id in shares_to_delete:
        del expense_shares[share_id]


def update_expense_record(expense_id, description, total_amount, payer_id, expense_date=None):
    """Update the main expense row."""
    expense_date = expense_date or date.today().isoformat()

    if _using_supabase():
        supabase = get_supabase_client()
        supabase.table('expenses').update({
            'description': description,
            'total_amount': total_amount,
            'payer_id': payer_id,
            'expense_date': expense_date,
        }).eq('id', expense_id).execute()
        return

    if expense_id not in expenses:
        return

    expenses[expense_id].update({
        'description': description,
        'total_amount': total_amount,
        'payer_id': payer_id,
        'date': expense_date,
    })


def delete_expense_shares_for_expense(expense_id):
    """Delete all shares for a single expense."""
    if _using_supabase():
        supabase = get_supabase_client()
        supabase.table('expense_shares').delete().eq('expense_id', expense_id).execute()
        return

    shares_to_delete = [
        share_id for share_id, share in expense_shares.items()
        if share['expense_id'] == expense_id
    ]
    for share_id in shares_to_delete:
        del expense_shares[share_id]


def insert_expense_share(expense_id, user_id, amount):
    """Create a share row for one expense participant."""
    if _using_supabase():
        supabase = get_supabase_client()
        row = _single_row(
            supabase.table('expense_shares')
            .insert({
                'expense_id': expense_id,
                'user_id': user_id,
                'amount': amount,
            })
            .execute()
        )
        return row['id']

    counters['share'] += 1
    share_id = counters['share']

    expense_shares[share_id] = {
        'id': share_id,
        'expense_id': expense_id,
        'user_id': user_id,
        'amount': amount
    }
    return share_id


def fetch_shares_for_expense(expense_id):
    """Fetch all shares for one expense."""
    if _using_supabase():
        supabase = get_supabase_client()
        rows = _response_rows(
            supabase.table('expense_shares')
            .select('id, expense_id, user_id, amount')
            .eq('expense_id', expense_id)
            .order('id')
            .execute()
        )
        return [_to_share(row) for row in rows]

    return [share for share in expense_shares.values() if share['expense_id'] == expense_id]


def fetch_shares_for_user_in_group(user_id, group_id):
    """Fetch all shares for one user in one group."""
    if _using_supabase():
        group_expenses = fetch_expenses_in_group(group_id)
        expense_ids = [expense['id'] for expense in group_expenses]
        if not expense_ids:
            return []

        supabase = get_supabase_client()
        rows = _response_rows(
            supabase.table('expense_shares')
            .select('id, expense_id, user_id, amount')
            .eq('user_id', user_id)
            .in_('expense_id', expense_ids)
            .order('id')
            .execute()
        )
        return [_to_share(row) for row in rows]

    user_shares = [share for share in expense_shares.values() if share['user_id'] == user_id]
    return [
        share for share in user_shares
        if share['expense_id'] in expenses and expenses[share['expense_id']]['group_id'] == group_id
    ]


def reset_data_store():
    """Reset all local in-memory data (useful in tests)."""
    if _using_supabase():
        supabase = get_supabase_client()
        supabase.table('expense_shares').delete().neq('id', 0).execute()
        supabase.table('expenses').delete().neq('id', 0).execute()
        supabase.table('users').delete().neq('id', 0).execute()
        supabase.table('groups').delete().neq('id', 0).execute()
        return

    groups.clear()
    users.clear()
    expenses.clear()
    expense_shares.clear()
    counters['group'] = 0
    counters['user'] = 0
    counters['expense'] = 0
    counters['share'] = 0

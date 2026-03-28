"""
Data access layer for SplitIA.

Right now this module uses in-memory Python dictionaries.
Later, this is the place to replace with Supabase/Postgres queries.

By isolating storage code here, routes and business logic do not need to
change when the persistence backend changes.
"""

# In-memory storage (local MVP mode)
groups = {}          # {group_id: {'id', 'name', 'members'}}
users = {}           # {user_id: {'id', 'name', 'group_id'}}
expenses = {}        # {expense_id: {'id', 'description', 'total_amount', 'payer_id', 'group_id', 'date'}}
expense_shares = {}  # {share_id: {'id', 'expense_id', 'user_id', 'amount'}}

# Mutable counters to generate unique IDs without global statements.
counters = {
    'group': 0,
    'user': 0,
    'expense': 0,
    'share': 0,
}


def insert_group(name):
    """Create a group record in local in-memory storage."""
    counters['group'] += 1
    group_id = counters['group']

    groups[group_id] = {
        'id': group_id,
        'name': name,
        'members': []
    }
    return group_id


def fetch_group(group_id):
    """Fetch one group by ID."""
    return groups.get(group_id)


def fetch_all_groups():
    """Fetch all groups."""
    return list(groups.values())


def delete_group_record(group_id):
    """Delete one group record (minimal implementation)."""
    if group_id in groups:
        del groups[group_id]


def insert_user(name, group_id):
    """Create a user and attach it to the group's member list."""
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
    return users.get(user_id)


def fetch_users_in_group(group_id):
    """Fetch all users that belong to a group."""
    group = groups.get(group_id)
    if not group:
        return []
    return [users[uid] for uid in group['members'] if uid in users]


def delete_user_record(user_id):
    """Delete one user and remove membership reference from its group."""
    if user_id not in users:
        return

    group_id = users[user_id]['group_id']
    if group_id in groups and user_id in groups[group_id]['members']:
        groups[group_id]['members'].remove(user_id)

    del users[user_id]


def insert_expense(description, total_amount, payer_id, group_id, expense_date=None):
    """Create an expense record."""
    counters['expense'] += 1
    expense_id = counters['expense']

    expenses[expense_id] = {
        'id': expense_id,
        'description': description,
        'total_amount': total_amount,
        'payer_id': payer_id,
        'group_id': group_id,
        'date': expense_date
    }
    return expense_id


def fetch_expense(expense_id):
    """Fetch one expense by ID."""
    return expenses.get(expense_id)


def fetch_expenses_in_group(group_id):
    """Fetch all expenses belonging to one group."""
    return [expense for expense in expenses.values() if expense['group_id'] == group_id]


def delete_expense_record(expense_id):
    """Delete an expense and all share rows attached to it."""
    if expense_id not in expenses:
        return

    del expenses[expense_id]
    shares_to_delete = [
        share_id for share_id, share in expense_shares.items()
        if share['expense_id'] == expense_id
    ]
    for share_id in shares_to_delete:
        del expense_shares[share_id]


def insert_expense_share(expense_id, user_id, amount):
    """Create a share row for one expense participant."""
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
    return [share for share in expense_shares.values() if share['expense_id'] == expense_id]


def fetch_shares_for_user_in_group(user_id, group_id):
    """Fetch all shares for one user in one group."""
    user_shares = [share for share in expense_shares.values() if share['user_id'] == user_id]
    return [
        share for share in user_shares
        if share['expense_id'] in expenses and expenses[share['expense_id']]['group_id'] == group_id
    ]


def reset_data_store():
    """Reset all local in-memory data (useful in tests)."""
    groups.clear()
    users.clear()
    expenses.clear()
    expense_shares.clear()
    counters['group'] = 0
    counters['user'] = 0
    counters['expense'] = 0
    counters['share'] = 0

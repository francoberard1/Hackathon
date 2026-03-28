"""
Business logic for balance calculation.

This file keeps pure calculations separated from route code and data storage.
That makes migration to a real database easier later.
"""

from . import models


def calculate_balances(group_id):
    """
    Calculate the balance for each user in a group.

    Balance formula:
        balance = total_paid - total_owed

    Positive value: user should receive money.
    Negative value: user should pay money.
    """
    members = models.get_users_in_group(group_id)
    balance_map = {member['id']: 0.0 for member in members}

    group_expenses = models.get_expenses_in_group(group_id)
    for expense in group_expenses:
        payer_id = expense['payer_id']
        balance_map[payer_id] += expense['total_amount']

        shares = models.get_shares_for_expense(expense['id'])
        for share in shares:
            user_id = share['user_id']
            balance_map[user_id] -= share['amount']

    return balance_map

"""
Domain-facing model API.

This module is intentionally simple: routes call these functions,
and these functions delegate storage work to logic.data_access.

Why this split helps:
- routes stay focused on HTTP/UI concerns
- business logic modules (balances/settlement) stay independent
- data_access can be swapped later for Supabase/Postgres queries
"""

from . import data_access


# ============================================================================
# GROUP FUNCTIONS
# ============================================================================

def create_group(name):
    """
    Create a new group.
    Args:
        name (str): Name of the group (e.g., "Trip to Miami")
    Returns:
        int: ID of the newly created group
    """
    # Future Supabase note:
    # This call can later become an INSERT into the "groups" table.
    return data_access.insert_group(name)


def get_group(group_id):
    """Get a group by ID."""
    return data_access.fetch_group(group_id)


def get_all_groups():
    """Get all groups."""
    return data_access.fetch_all_groups()


def delete_group(group_id):
    """Delete a group and all its related data."""
    data_access.delete_group_record(group_id)


# ============================================================================
# USER FUNCTIONS
# ============================================================================

def create_user(name, group_id):
    """
    Create a new user and add them to a group.
    Args:
        name (str): User's name
        group_id (int): ID of the group they belong to
    Returns:
        int: ID of the newly created user
    """
    # Check if group exists
    group = data_access.fetch_group(group_id)
    if not group:
        raise ValueError(f"Group {group_id} does not exist")

    # Future Supabase note:
    # This can become an INSERT into the "users" table.
    return data_access.insert_user(name, group_id)


def get_user(user_id):
    """Get a user by ID."""
    return data_access.fetch_user(user_id)


def get_users_in_group(group_id):
    """Get all users in a group."""
    return data_access.fetch_users_in_group(group_id)


def delete_user(user_id):
    """Remove a user from the system."""
    data_access.delete_user_record(user_id)


# ============================================================================
# EXPENSE FUNCTIONS
# ============================================================================

def create_expense(description, total_amount, payer_id, group_id, participants):
    """
    Create a new expense.
    Args:
        description (str): What was the expense for? (e.g., "Dinner")
        total_amount (float): Total cost
        payer_id (int): Who paid? (user ID)
        group_id (int): Which group?
        participants (list): List of user IDs who share this expense (with equal split)
    Returns:
        int: ID of the newly created expense
    """
    # Check if user and group exist
    if not data_access.fetch_user(payer_id):
        raise ValueError(f"User {payer_id} does not exist")
    if not data_access.fetch_group(group_id):
        raise ValueError(f"Group {group_id} does not exist")

    # Future Supabase note:
    # This can become an INSERT into "expenses" plus many rows in "expense_shares".
    expense_id = data_access.insert_expense(description, total_amount, payer_id, group_id)

    # Create shares (each participant owes equal amount)
    share_amount = total_amount / len(participants)
    for participant_id in participants:
        create_expense_share(expense_id, participant_id, share_amount)

    return expense_id


def get_expense(expense_id):
    """Get an expense by ID."""
    return data_access.fetch_expense(expense_id)


def get_expenses_in_group(group_id):
    """Get all expenses in a group."""
    return data_access.fetch_expenses_in_group(group_id)


def delete_expense(expense_id):
    """Delete an expense and all its shares."""
    data_access.delete_expense_record(expense_id)


# ============================================================================
# EXPENSE SHARE FUNCTIONS
# ============================================================================

def create_expense_share(expense_id, user_id, amount):
    """
    Create a share of an expense for a user.
    This means "user owes $amount for this expense".
    """
    return data_access.insert_expense_share(expense_id, user_id, amount)


def get_shares_for_expense(expense_id):
    """Get all shares for an expense."""
    return data_access.fetch_shares_for_expense(expense_id)


def get_shares_for_user_in_group(user_id, group_id):
    """Get all expense shares for a user in a specific group."""
    return data_access.fetch_shares_for_user_in_group(user_id, group_id)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def reset_data():
    """Clear all data. Useful for testing."""
    data_access.reset_data_store()

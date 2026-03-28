# ============================================================================
# MODELS.PY
# ============================================================================
# This file defines the data structures for SplitIA.
# We use simple in-memory dictionaries to store data (no database yet).
# Each model is stored as a dictionary with an ID as the key.
#
# Models:
# - Group: A group of people sharing expenses
# - User: A person in a group
# - Expense: A payment made by someone
# - ExpenseShare: Who shares an expense and how much they owe
# ============================================================================

# Global storage (in-memory)
# In a real app, you'd use a database like SQLite or PostgreSQL
groups = {}          # Groups: {group_id: {name, members}}
users = {}           # Users: {user_id: {name, group_id}}
expenses = {}        # Expenses: {expense_id: {description, total_amount, payer_id, group_id}}
expense_shares = {}  # Shares: {share_id: {expense_id, user_id, amount}}

# Counter for generating unique IDs
group_counter = 0
user_counter = 0
expense_counter = 0
share_counter = 0


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
    global group_counter
    group_counter += 1
    groups[group_counter] = {
        'id': group_counter,
        'name': name,
        'members': []  # List of user IDs in this group
    }
    return group_counter


def get_group(group_id):
    """Get a group by ID."""
    return groups.get(group_id)


def get_all_groups():
    """Get all groups."""
    return list(groups.values())


def delete_group(group_id):
    """Delete a group and all its related data."""
    if group_id in groups:
        # This is a simple implementation; in real apps, be careful about cascading deletes
        del groups[group_id]


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
    global user_counter
    
    # Check if group exists
    if group_id not in groups:
        raise ValueError(f"Group {group_id} does not exist")
    
    user_counter += 1
    users[user_counter] = {
        'id': user_counter,
        'name': name,
        'group_id': group_id
    }
    
    # Add user to group's member list
    groups[group_id]['members'].append(user_counter)
    
    return user_counter


def get_user(user_id):
    """Get a user by ID."""
    return users.get(user_id)


def get_users_in_group(group_id):
    """Get all users in a group."""
    return [users[uid] for uid in groups[group_id]['members'] if uid in users]


def delete_user(user_id):
    """Remove a user from the system."""
    if user_id in users:
        group_id = users[user_id]['group_id']
        groups[group_id]['members'].remove(user_id)
        del users[user_id]


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
    global expense_counter
    
    # Check if user and group exist
    if payer_id not in users:
        raise ValueError(f"User {payer_id} does not exist")
    if group_id not in groups:
        raise ValueError(f"Group {group_id} does not exist")
    
    # Create the expense
    expense_counter += 1
    expenses[expense_counter] = {
        'id': expense_counter,
        'description': description,
        'total_amount': total_amount,
        'payer_id': payer_id,
        'group_id': group_id
    }
    
    # Create shares (each participant owes equal amount)
    share_amount = total_amount / len(participants)
    for participant_id in participants:
        create_expense_share(expense_counter, participant_id, share_amount)
    
    return expense_counter


def get_expense(expense_id):
    """Get an expense by ID."""
    return expenses.get(expense_id)


def get_expenses_in_group(group_id):
    """Get all expenses in a group."""
    return [exp for exp in expenses.values() if exp['group_id'] == group_id]


def delete_expense(expense_id):
    """Delete an expense and all its shares."""
    if expense_id in expenses:
        del expenses[expense_id]
        # Also delete all shares for this expense
        shares_to_delete = [sid for sid, share in expense_shares.items() if share['expense_id'] == expense_id]
        for share_id in shares_to_delete:
            del expense_shares[share_id]


# ============================================================================
# EXPENSE SHARE FUNCTIONS
# ============================================================================

def create_expense_share(expense_id, user_id, amount):
    """
    Create a share of an expense for a user.
    This means "user owes $amount for this expense".
    """
    global share_counter
    share_counter += 1
    expense_shares[share_counter] = {
        'id': share_counter,
        'expense_id': expense_id,
        'user_id': user_id,
        'amount': amount
    }
    return share_counter


def get_shares_for_expense(expense_id):
    """Get all shares for an expense."""
    return [share for share in expense_shares.values() if share['expense_id'] == expense_id]


def get_shares_for_user_in_group(user_id, group_id):
    """Get all expense shares for a user in a specific group."""
    user_shares = [share for share in expense_shares.values() if share['user_id'] == user_id]
    # Filter to only expenses in this group
    return [share for share in user_shares if expenses[share['expense_id']]['group_id'] == group_id]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def reset_data():
    """Clear all data. Useful for testing."""
    global group_counter, user_counter, expense_counter, share_counter
    groups.clear()
    users.clear()
    expenses.clear()
    expense_shares.clear()
    group_counter = 0
    user_counter = 0
    expense_counter = 0
    share_counter = 0

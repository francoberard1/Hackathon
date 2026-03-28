# ============================================================================
# SETTLEMENT.PY
# ============================================================================
# Core logic for calculating balances and settlement transactions.
#
# Key concepts:
# 1. BALANCE: How much a user has paid/owes
#    - Positive balance = user is owed money (creditor)
#    - Negative balance = user owes money (debtor)
#
# 2. SETTLEMENT: Minimal transactions to settle all debts
#    Uses a greedy algorithm to match creditors with debtors
# ============================================================================

from . import balances
from . import models


def calculate_balances(group_id):
    """Compatibility wrapper around logic.balances.calculate_balances."""
    return balances.calculate_balances(group_id)


def calculate_settlements(group_id):
    """
    Calculate minimal transactions to settle all debts.
    
    Algorithm:
    1. Calculate each user's balance
    2. Separate into creditors (positive balance) and debtors (negative)
    3. Greedily match debtors to creditors until all are settled
    
    Args:
        group_id (int): ID of the group
    
    Returns:
        list: List of transaction dictionaries
        Each transaction: {
            'debtor_id': int,
            'creditor_id': int,
            'amount': float,
            'debtor_name': str,
            'creditor_name': str
        }
    """
    
    # Step 1: Calculate balances
    balance_map = calculate_balances(group_id)
    
    # Step 2: Separate creditors and debtors
    creditors = []  # [{'id': user_id, 'name': name, 'amount': owed_to_them}, ...]
    debtors = []    # [{'id': user_id, 'name': name, 'amount': they_owe}, ...]
    
    members = models.get_users_in_group(group_id)
    
    for member in members:
        user_id = member['id']
        user_name = member['name']
        balance = balance_map.get(user_id, 0.0)
        
        # Round to avoid floating point errors
        balance = round(balance, 2)
        
        if balance > 0.01:  # Small threshold to ignore rounding errors
            creditors.append({'id': user_id, 'name': user_name, 'amount': balance})
        elif balance < -0.01:
            debtors.append({'id': user_id, 'name': user_name, 'amount': abs(balance)})
    
    # Step 3: Greedy matching - match debtors to creditors
    transactions = []
    
    # Make copies to avoid modifying originals
    debtors_copy = debtors.copy()
    creditors_copy = creditors.copy()
    
    # Match each debtor with creditors
    for debtor in debtors_copy:
        debtor_id = debtor['id']
        debtor_name = debtor['name']
        debtor_amount = debtor['amount']
        
        # Keep matching this debtor until they owe nothing
        while debtor_amount > 0.01:
            if not creditors_copy:
                break
            
            # Take the first creditor
            creditor = creditors_copy[0]
            creditor_id = creditor['id']
            creditor_name = creditor['name']
            creditor_amount = creditor['amount']
            
            # Settle as much as possible between these two
            settlement_amount = min(debtor_amount, creditor_amount)
            
            # Record the transaction
            transactions.append({
                'debtor_id': debtor_id,
                'debtor_name': debtor_name,
                'creditor_id': creditor_id,
                'creditor_name': creditor_name,
                'amount': round(settlement_amount, 2)
            })
            
            # Update amounts
            debtor_amount -= settlement_amount
            creditor_amount -= settlement_amount
            
            # If creditor is settled, remove them
            if creditor_amount < 0.01:
                creditors_copy.pop(0)
            else:
                # Update creditor's remaining amount
                creditors_copy[0]['amount'] = creditor_amount
    
    return transactions


def get_balance_summary(group_id):
    """
    Get a user-friendly summary of balances in a group.
    
    Returns:
        list: List of (user_name, balance_str) tuples
              For display on UI
    """
    balance_map = calculate_balances(group_id)
    members = models.get_users_in_group(group_id)
    
    summary = []
    for member in members:
        user_id = member['id']
        user_name = member['name']
        balance = round(balance_map.get(user_id, 0.0), 2)
        
        # Create user-friendly string
        if balance > 0:
            status = f"owed ${balance:.2f}"
        elif balance < 0:
            status = f"owes ${abs(balance):.2f}"
        else:
            status = "settled"
        
        summary.append({
            'name': user_name,
            'balance': balance,
            'status': status
        })
    
    return summary

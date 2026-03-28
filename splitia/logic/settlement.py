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

from collections import Counter

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


def calculate_fairness_data(group_id):
    """
    Calculate fairness metrics and natural-language insights for a group.
    """
    members = models.get_users_in_group(group_id)
    expenses = models.get_expenses_in_group(group_id)
    balance_map = calculate_balances(group_id)

    if not members:
        return {
            'balances': balance_map,
            'fairnessMetrics': [],
            'fairnessInsights': ["Add members to start tracking fairness insights."]
        }

    total_group_spend = sum(expense['total_amount'] for expense in expenses)
    equitable_share = total_group_spend / len(members) if members else 0.0

    total_paid = {member['id']: 0.0 for member in members}
    payment_count = Counter()

    for expense in expenses:
        payer_id = expense['payer_id']
        total_paid[payer_id] += expense['total_amount']
        payment_count[payer_id] += 1

    fairness_metrics = []
    for member in members:
        user_id = member['id']
        paid = round(total_paid.get(user_id, 0.0), 2)
        should_have_paid = round(equitable_share, 2)
        fairness_metrics.append({
            'user_id': user_id,
            'name': member['name'],
            'total_paid': paid,
            'should_have_paid': should_have_paid,
            'net_difference': round(paid - equitable_share, 2),
            'balance': round(balance_map.get(user_id, 0.0), 2),
            'payment_count': payment_count.get(user_id, 0)
        })

    fairness_metrics.sort(key=lambda item: item['name'].lower())

    return {
        'balances': balance_map,
        'fairnessMetrics': fairness_metrics,
        'fairnessInsights': _build_fairness_insights(
            members,
            expenses,
            fairness_metrics,
            equitable_share
        )
    }


def _build_fairness_insights(members, expenses, fairness_metrics, equitable_share):
    """Generate natural-language insights from fairness metrics."""
    if not expenses:
        return ["Add the first expense to unlock fairness insights for this group."]

    insights = []

    highest_payer = max(fairness_metrics, key=lambda item: item['net_difference'])
    if equitable_share > 0 and highest_payer['net_difference'] > 0.01:
        pct_above_average = (highest_payer['net_difference'] / equitable_share) * 100
        insights.append(
            f"{highest_payer['name']} paid {pct_above_average:.0f}% more than the group average."
        )

    most_indebted = min(fairness_metrics, key=lambda item: item['balance'])
    if most_indebted['balance'] < -0.01:
        insights.append(
            f"{most_indebted['name']} is currently the most indebted member, owing ${abs(most_indebted['balance']):.2f}."
        )

    next_payer = min(
        fairness_metrics,
        key=lambda item: (item['net_difference'], item['payment_count'], item['name'].lower())
    )
    insights.append(
        f"It would help to have {next_payer['name']} pay the next expense to rebalance the group."
    )

    frequent_payer = max(fairness_metrics, key=lambda item: (item['payment_count'], item['total_paid']))
    if frequent_payer['payment_count'] > 0:
        suffix = "time" if frequent_payer['payment_count'] == 1 else "times"
        insights.append(
            f"{frequent_payer['name']} has paid most often so far, covering {frequent_payer['payment_count']} {suffix}."
        )

    streak_info = _find_payment_streak(expenses, members)
    if streak_info:
        insights.append(f"{streak_info['name']} paid {streak_info['count']} expenses in a row.")

    for member in fairness_metrics:
        if member['payment_count'] == 0:
            insights.append(f"{member['name']} has not paid any expense yet.")

    return insights


def _find_payment_streak(expenses, members):
    """Return the longest payer streak if someone paid more than 3 times in a row."""
    if len(expenses) < 4:
        return None

    member_names = {member['id']: member['name'] for member in members}
    sorted_expenses = sorted(
        expenses,
        key=lambda expense: (expense.get('date') or '', expense['id'])
    )

    longest_payer_id = None
    longest_streak = 1
    current_payer_id = None
    current_streak = 0

    for expense in sorted_expenses:
        payer_id = expense['payer_id']
        if payer_id == current_payer_id:
            current_streak += 1
        else:
            current_payer_id = payer_id
            current_streak = 1

        if current_streak > longest_streak:
            longest_streak = current_streak
            longest_payer_id = payer_id

    if longest_payer_id and longest_streak > 3:
        return {
            'name': member_names.get(longest_payer_id, 'Unknown'),
            'count': longest_streak
        }

    return None

# ============================================================================
# APP.PY
# ============================================================================
# Main Flask application for SplitIA.
# This file sets up routes and handles user requests.
#
# Key routes:
# - "/" → Show all groups
# - "/group/<id>" → Show group details
# - "/add_group" → Create group
# - "/add_user/<group_id>" → Add user to group
# - "/add_expense/<group_id>" → Add expense
# - "/settle/<group_id>" → Calculate settlements
# ============================================================================

from flask import Flask, render_template, request, redirect, url_for
from logic import models
from logic import settlement

# Create Flask app
app = Flask(__name__)

# ============================================================================
# ROUTES: GROUPS
# ============================================================================

@app.route('/')
def index():
    """
    Home page: Display all groups.
    """
    all_groups = models.get_all_groups()
    return render_template('index.html', groups=all_groups)


@app.route('/add_group', methods=['GET', 'POST'])
def add_group():
    """
    Create a new group.
    GET: Show form
    POST: Process form and create group
    """
    if request.method == 'POST':
        group_name = request.form.get('group_name', '').strip()
        
        if group_name:
            group_id = models.create_group(group_name)
            # Redirect to group details page
            return redirect(url_for('group_detail', group_id=group_id))
        # If name is empty, show form again
    
    return render_template('add_group.html')


@app.route('/group/<int:group_id>')
def group_detail(group_id):
    """
    Show group details:
    - Members
    - Expenses
    - Balances
    """
    group = models.get_group(group_id)
    
    if not group:
        return "Group not found", 404
    
    # Get group members
    members = models.get_users_in_group(group_id)
    
    # Get group expenses
    expenses = models.get_expenses_in_group(group_id)
    
    # Get balances for each member
    balances = settlement.calculate_balances(group_id)
    
    return render_template(
        'group.html',
        group=group,
        members=members,
        expenses=expenses,
        balances=balances
    )


# ============================================================================
# ROUTES: USERS
# ============================================================================

@app.route('/add_user/<int:group_id>', methods=['GET', 'POST'])
def add_user(group_id):
    """
    Add a user to a group.
    GET: Show form
    POST: Process form and create user
    """
    group = models.get_group(group_id)
    
    if not group:
        return "Group not found", 404
    
    if request.method == 'POST':
        user_name = request.form.get('user_name', '').strip()
        
        if user_name:
            models.create_user(user_name, group_id)
            return redirect(url_for('group_detail', group_id=group_id))
    
    return render_template('add_user.html', group=group)


# ============================================================================
# ROUTES: EXPENSES
# ============================================================================

@app.route('/add_expense/<int:group_id>', methods=['GET', 'POST'])
def add_expense(group_id):
    """
    Add an expense to a group.
    GET: Show form
    POST: Process form and create expense
    """
    group = models.get_group(group_id)
    members = models.get_users_in_group(group_id)
    
    if not group:
        return "Group not found", 404
    
    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        total_amount_str = request.form.get('total_amount', '0')
        payer_id = int(request.form.get('payer_id', 0))
        
        # Get participants (which users share this expense)
        # Form sends participant_<user_id> = "on" for checked boxes
        participant_ids = []
        for member in members:
            if request.form.get(f'participant_{member["id"]}'):
                participant_ids.append(member['id'])
        
        # Validate input
        if description and total_amount_str and payer_id and participant_ids:
            try:
                total_amount = float(total_amount_str)
                models.create_expense(description, total_amount, payer_id, group_id, participant_ids)
                return redirect(url_for('group_detail', group_id=group_id))
            except ValueError:
                # Invalid amount, show form again
                pass
    
    return render_template('add_expense.html', group=group, members=members)


# ============================================================================
# ROUTES: SETTLEMENTS
# ============================================================================

@app.route('/settle/<int:group_id>')
def settle(group_id):
    """
    Calculate and display settlement transactions.
    Shows which users should pay whom to settle all debts.
    """
    group = models.get_group(group_id)
    members = models.get_users_in_group(group_id)
    balances = settlement.calculate_balances(group_id)
    
    if not group:
        return "Group not found", 404
    
    # Calculate transactions needed to settle
    transactions = settlement.calculate_settlements(group_id)
    
    return render_template(
        'settle.html',
        group=group,
        members=members,
        balances=balances,
        transactions=transactions
    )


# ============================================================================
# ERROR HANDLING
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return "Page not found", 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors."""
    return "Server error", 500


# ============================================================================
# RUN APP
# ============================================================================

if __name__ == '__main__':
    # Run the Flask development server
    # Debug=True means the server reloads when you change code
    app.run(debug=True, host='127.0.0.1', port=5000)

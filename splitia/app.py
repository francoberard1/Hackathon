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

import os

try:
    from dotenv import load_dotenv
except ImportError:
    # Keep app runnable even before dependencies are installed.
    def load_dotenv():
        return False

from flask import Flask, render_template, request, redirect, url_for

from logic import models
from logic import settlement
from logic.ticket_parser import parse_ticket_text


def create_app():
    """
    Application factory used by:
    - Local development (python app.py)
    - Vercel serverless runtime (imports app object)

    Environment variables are loaded from .env when available.
    """
    load_dotenv()

    flask_app = Flask(__name__)

    # Keep a safe default for local hacking.
    # In production, set SECRET_KEY from environment.
    flask_app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-in-production')

    register_routes(flask_app)
    register_error_handlers(flask_app)
    return flask_app


def register_routes(flask_app):
    """Register all route handlers in one place to keep app creation clean."""

# ============================================================================
# ROUTES: GROUPS
# ============================================================================

    @flask_app.route('/')
    def index():
        """
        Home page: Display all groups.
        """
        all_groups = models.get_all_groups()
        return render_template('index.html', groups=all_groups)


    @flask_app.route('/add_group', methods=['GET', 'POST'])
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


    @flask_app.route('/group/<int:group_id>')
    def group_detail(group_id):
        """
        Show group details:
        - Members
        - Expenses
        - Balances
        """
        group = models.get_group(group_id)

        if not group:
            return 'Group not found', 404

        # Get group members
        members = models.get_users_in_group(group_id)

        # Get group expenses
        expenses = models.get_expenses_in_group(group_id)

        # Get balances plus fairness insights for each member
        fairness_data = settlement.calculate_fairness_data(group_id)

        return render_template(
            'group.html',
            group=group,
            members=members,
            expenses=expenses,
            balances=fairness_data['balances'],
            fairness_metrics=fairness_data['fairnessMetrics'],
            fairness_insights=fairness_data['fairnessInsights']
        )


# ============================================================================
# ROUTES: USERS
# ============================================================================

    @flask_app.route('/add_user/<int:group_id>', methods=['GET', 'POST'])
    def add_user(group_id):
        """
        Add a user to a group.
        GET: Show form
        POST: Process form and create user
        """
        group = models.get_group(group_id)

        if not group:
            return 'Group not found', 404

        if request.method == 'POST':
            user_name = request.form.get('user_name', '').strip()

            if user_name:
                models.create_user(user_name, group_id)
                return redirect(url_for('group_detail', group_id=group_id))

        return render_template('add_user.html', group=group)


# ============================================================================
# ROUTES: EXPENSES
# ============================================================================

    @flask_app.route('/parse_ticket', methods=['GET', 'POST'])
    def parse_ticket():
        """
        Demo-friendly ticket parser flow.
        GET: Show raw ticket text form
        POST: Parse text and show review screen
        """
        if request.method == 'POST':
            ticket_text = request.form.get('ticket_text', '')
            parsed_result = parse_ticket_text(ticket_text)

            # Keep compatibility with templates that still read `total`.
            if 'total' not in parsed_result and 'total_detected' in parsed_result:
                parsed_result = {
                    **parsed_result,
                    'total': parsed_result['total_detected'],
                }

            return render_template(
                'review_ticket.html',
                parsed_result=parsed_result,
                form_action=url_for('parse_ticket')
            )

        return render_template(
            'parse_ticket.html',
            form_action=url_for('parse_ticket'),
            ticket_text=''
        )

    @flask_app.route('/add_expense/<int:group_id>', methods=['GET', 'POST'])
    def add_expense(group_id):
        """
        Add an expense to a group.
        GET: Show form
        POST: Process form and create expense
        """
        group = models.get_group(group_id)
        members = models.get_users_in_group(group_id)

        if not group:
            return 'Group not found', 404

        if request.method == 'POST':
            description = request.form.get('description', '').strip()
            total_amount_str = request.form.get('total_amount', '0')
            payer_id = int(request.form.get('payer_id', 0))
            expense_date = request.form.get('expense_date', '').strip()

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
                    models.create_expense(
                        description,
                        total_amount,
                        payer_id,
                        group_id,
                        participant_ids,
                        expense_date=expense_date
                    )
                    return redirect(url_for('group_detail', group_id=group_id))
                except ValueError:
                    # Invalid amount, show form again
                    pass

        return render_template('add_expense.html', group=group, members=members)


# ============================================================================
# ROUTES: SETTLEMENTS
# ============================================================================

    @flask_app.route('/settle/<int:group_id>')
    def settle(group_id):
        """
        Calculate and display settlement transactions.
        Shows which users should pay whom to settle all debts.
        """
        group = models.get_group(group_id)
        members = models.get_users_in_group(group_id)

        if not group:
            return 'Group not found', 404

        # Calculate transactions needed to settle
        transactions = settlement.calculate_settlements(group_id)
        fairness_data = settlement.calculate_fairness_data(group_id)

        return render_template(
            'settle.html',
            group=group,
            members=members,
            balances=fairness_data['balances'],
            transactions=transactions,
            fairness_metrics=fairness_data['fairnessMetrics'],
            fairness_insights=fairness_data['fairnessInsights']
        )


# ============================================================================
# ERROR HANDLING
# ============================================================================

def register_error_handlers(flask_app):
    """Register app-wide HTTP error handlers."""

    @flask_app.errorhandler(404)
    def not_found(_error):
        """Handle 404 errors."""
        return 'Page not found', 404

    @flask_app.errorhandler(500)
    def server_error(_error):
        """Handle 500 errors."""
        return 'Server error', 500


# Exported for Vercel and other WSGI/ASGI adapters.
app = create_app()


# ============================================================================
# RUN APP
# ============================================================================

if __name__ == '__main__':
    # Run the Flask development server
    # Debug=True means the server reloads when you change code
    app.run(debug=True, host='127.0.0.1', port=5000)

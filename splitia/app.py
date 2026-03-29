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
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    # Keep app runnable even before dependencies are installed.
    def load_dotenv(*args, **kwargs):
        return False

from flask import Flask, jsonify, render_template, request, redirect, url_for

try:
    from logic import models
    from logic import settlement
    from logic.receipt_review import (
        ReceiptReviewValidationError,
        extract_receipt_review_form_state,
        validate_receipt_review_submission,
    )
    from logic.receipt_service import (
        ReceiptDraftError,
        ReceiptConfigurationError,
        ReceiptProviderError,
        ReceiptValidationError,
        build_receipt_draft,
    )
    from logic.ticket_ocr import extract_text_from_image
    from logic.ticket_parser import parse_ticket_text
except ModuleNotFoundError:
    from splitia.logic import models
    from splitia.logic import settlement
    from splitia.logic.receipt_review import (
        ReceiptReviewValidationError,
        extract_receipt_review_form_state,
        validate_receipt_review_submission,
    )
    from splitia.logic.receipt_service import (
        ReceiptDraftError,
        ReceiptConfigurationError,
        ReceiptProviderError,
        ReceiptValidationError,
        build_receipt_draft,
    )
    from splitia.logic.ticket_ocr import extract_text_from_image
    from splitia.logic.ticket_parser import parse_ticket_text


def create_app():
    """
    Application factory used by:
    - Local development (python app.py)
    - Vercel serverless runtime (imports app object)

    Environment variables are loaded from .env when available.
    """
    app_dir = Path(__file__).resolve().parent
    load_dotenv(app_dir / '.env')
    load_dotenv(app_dir.parent / '.env')

    flask_app = Flask(__name__)

    # Keep a safe default for local hacking.
    # In production, set SECRET_KEY from environment.
    flask_app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-in-production')

    register_routes(flask_app)
    register_error_handlers(flask_app)
    return flask_app


def register_routes(flask_app):
    """Register all route handlers in one place to keep app creation clean."""

    def _build_receipt_template_context(group_id, error_message='', review_state=None):
        group = models.get_group(group_id)
        if not group:
            return None

        members = models.get_users_in_group(group_id)
        return {
            'group': group,
            'members': members,
            'error_message': error_message,
            'review_state': review_state or None,
        }

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
            ticket_text = request.form.get('ticket_text', '').strip()
            ticket_image = request.files.get('ticket_image')

            if ticket_text:
                raw_text = ticket_text
            elif ticket_image and ticket_image.filename:
                raw_text = extract_text_from_image(ticket_image)
                if not raw_text:
                    return render_template(
                        'parse_ticket.html',
                        form_action=url_for('parse_ticket'),
                        ticket_text='',
                        error_message='Could not read text from the uploaded image. Try another photo or paste the ticket text manually.'
                    )
            else:
                return render_template(
                    'parse_ticket.html',
                    form_action=url_for('parse_ticket'),
                    ticket_text='',
                    error_message='Paste ticket text or upload a ticket image to continue.'
                )

            parsed_result = parse_ticket_text(raw_text)

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
            ticket_text='',
            error_message=''
        )

    @flask_app.route('/api/receipt/draft', methods=['POST'])
    def receipt_draft():
        """
        Return a Gemini-generated receipt draft from an uploaded image.
        """
        receipt_image = request.files.get('receipt_image') or request.files.get('image')

        try:
            draft = build_receipt_draft(receipt_image)
        except ReceiptDraftError as exc:
            if isinstance(exc, ReceiptValidationError):
                status_code = 400
            elif isinstance(exc, ReceiptConfigurationError):
                status_code = 500
            elif isinstance(exc, ReceiptProviderError):
                status_code = 502
            else:
                status_code = 502
            return jsonify({'error': str(exc), 'error_code': exc.error_code}), status_code

        return jsonify(draft)

    @flask_app.route('/add_expense/<int:group_id>/receipt', methods=['GET'])
    def add_expense_receipt(group_id):
        """
        Show the receipt upload and review flow for a group.
        """
        context = _build_receipt_template_context(group_id)
        if not context:
            return 'Group not found', 404

        return render_template('add_expense_receipt.html', **context)

    @flask_app.route('/add_expense/<int:group_id>/receipt/review', methods=['POST'])
    def add_expense_receipt_review(group_id):
        """
        Validate a reviewed receipt and create an expense using exact shares.
        """
        context = _build_receipt_template_context(
            group_id,
            review_state=extract_receipt_review_form_state(request.form),
        )
        if not context:
            return 'Group not found', 404

        try:
            review_result = validate_receipt_review_submission(
                request.form,
                context['members'],
            )
        except ReceiptReviewValidationError as exc:
            context['error_message'] = str(exc)
            return render_template('add_expense_receipt.html', **context), 400

        models.create_expense(
            review_result['description'],
            review_result['total_amount'],
            review_result['payer_id'],
            group_id,
            participants=review_result['participant_ids'],
            expense_date=review_result['expense_date'],
            share_amounts_by_user=review_result['share_amounts_by_user'],
        )
        return redirect(url_for('group_detail', group_id=group_id))

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
            try:
                payer_id = int(request.form.get('payer_id', 0))
            except (TypeError, ValueError):
                payer_id = 0
            expense_date = request.form.get('expense_date', '').strip()

            # Get participants (which users share this expense)
            # Form sends participant_<user_id> = "on" for checked boxes
            participant_ids = []
            for member in members:
                if request.form.get(f'participant_{member["id"]}'):
                    participant_ids.append(member['id'])

            # Validate input
            share_amounts_by_user = None
            raw_share_amounts = {}
            for member in members:
                share_value = request.form.get(f'share_amount_{member["id"]}', '').strip()
                if not share_value:
                    continue
                try:
                    amount = float(share_value)
                except ValueError:
                    continue
                if amount > 0:
                    raw_share_amounts[member['id']] = amount

            if raw_share_amounts:
                participant_ids = list(raw_share_amounts.keys())
                share_amounts_by_user = raw_share_amounts

            if description and total_amount_str and payer_id and participant_ids:
                try:
                    total_amount = float(total_amount_str)
                    models.create_expense(
                        description,
                        total_amount,
                        payer_id,
                        group_id,
                        participant_ids,
                        expense_date=expense_date,
                        share_amounts_by_user=share_amounts_by_user,
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

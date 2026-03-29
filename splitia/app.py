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
import tempfile

try:
    from dotenv import load_dotenv
except ImportError:
    # Keep app runnable even before dependencies are installed.
    def load_dotenv(*_args, **_kwargs):
        return False

from flask import Flask, jsonify, render_template, request, redirect, url_for

from logic import models
from logic import parser
from logic import settlement


def _has_ai_parser():
    return bool(
        os.getenv('ASSEMBLYAI_API_KEY', '').strip()
        or os.getenv('OPENAI_API_KEY', '').strip()
    )


def _parse_request_group_members(payload, form_data):
    raw_members = payload.get('group_members') if isinstance(payload, dict) else None
    if raw_members is None:
        raw_members = form_data.getlist('group_members')

    if not isinstance(raw_members, list):
        return []

    return [str(member).strip() for member in raw_members if str(member).strip()]


def create_app():
    """
    Application factory used by:
    - Local development (python app.py)
    - Vercel serverless runtime (imports app object)

    Environment variables are loaded from .env when available.
    """
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(env_path)

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
                try:
                    models.create_user(user_name, group_id)
                    return redirect(url_for('group_detail', group_id=group_id))
                except ValueError as exc:
                    return render_template('add_user.html', group=group, error_message=str(exc)), 400
                except Exception:
                    return render_template(
                        'add_user.html',
                        group=group,
                        error_message='No pudimos agregar el miembro. Probá una sola vez más en unos segundos.',
                    ), 502

        return render_template('add_user.html', group=group)


# ============================================================================
# ROUTES: EXPENSES
# ============================================================================

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
            payer_id_raw = request.form.get('payer_id', '').strip()
            expense_date = request.form.get('expense_date', '').strip()

            participant_shares = {}
            for member in members:
                if request.form.get(f'participant_{member["id"]}'):
                    share_amount_raw = request.form.get(f'share_amount_{member["id"]}', '0').strip()
                    try:
                        share_amount = float(share_amount_raw or '0')
                    except ValueError:
                        return render_template(
                            'add_expense.html',
                            group=group,
                            members=members,
                            error_message=f'El monto para {member["name"]} no es válido.',
                        ), 400

                    participant_shares[member['id']] = share_amount

            if not description:
                return render_template(
                    'add_expense.html',
                    group=group,
                    members=members,
                    error_message='Completá la descripción del gasto.',
                ), 400

            try:
                payer_id = int(payer_id_raw)
            except ValueError:
                return render_template(
                    'add_expense.html',
                    group=group,
                    members=members,
                    error_message='Seleccioná quién pagó antes de agregar el gasto.',
                ), 400

            if not participant_shares:
                return render_template(
                    'add_expense.html',
                    group=group,
                    members=members,
                    error_message='Seleccioná al menos una persona para dividir el gasto.',
                ), 400

            try:
                total_amount = float(total_amount_str)
            except ValueError:
                return render_template(
                    'add_expense.html',
                    group=group,
                    members=members,
                    error_message='El monto total no es válido.',
                ), 400

            if any(share_amount < 0 for share_amount in participant_shares.values()):
                return render_template(
                    'add_expense.html',
                    group=group,
                    members=members,
                    error_message='Los montos por persona no pueden ser negativos.',
                ), 400

            shares_total = round(sum(participant_shares.values()), 2)
            if abs(shares_total - total_amount) > 0.01:
                return render_template(
                    'add_expense.html',
                    group=group,
                    members=members,
                    error_message='La suma de los montos por persona debe coincidir con el total del gasto.',
                ), 400

            try:
                models.create_expense(
                    description,
                    total_amount,
                    payer_id,
                    group_id,
                    participant_shares,
                    expense_date=expense_date or None,
                )
                return redirect(url_for('group_detail', group_id=group_id))
            except ValueError as exc:
                return render_template(
                    'add_expense.html',
                    group=group,
                    members=members,
                    error_message=str(exc),
                ), 400
            except Exception:
                return render_template(
                    'add_expense.html',
                    group=group,
                    members=members,
                    error_message='No pudimos guardar el gasto. Revisá payer, participantes y monto, y probá de nuevo.',
                ), 502

        return render_template('add_expense.html', group=group, members=members)


    @flask_app.route('/api/audio/draft', methods=['POST'])
    def create_audio_expense_draft():
        """
        Receive an uploaded audio file, transcribe it, and return an expense draft.
        This endpoint never writes to the database.
        """
        audio_file = request.files.get('audio')

        if not audio_file or not audio_file.filename:
            return jsonify({'error': 'audio file is required in the "audio" form field'}), 400

        suffix = os.path.splitext(audio_file.filename)[1] or '.webm'
        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                audio_file.save(temp_file)
                temp_path = temp_file.name

            transcript, transcription_source = parser.transcribe_audio_with_source(temp_path)
            draft = parser.parse_transcript(
                transcript,
                transcription_used_ai=_has_ai_parser(),
                transcription_source=transcription_source,
            )
            return jsonify({
                'transcript': transcript,
                'source': transcription_source,
                'draft': draft.model_dump(),
            }), 200
        except (FileNotFoundError, ValueError) as exc:
            return jsonify({'error': str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({'error': str(exc)}), 502
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)


    @flask_app.route('/api/audio/transcribe', methods=['POST'])
    def transcribe_audio_message():
        """
        Receive an uploaded audio file and return only the transcript.
        The UI uses this route to let the user edit the transcript before parsing.
        """
        audio_file = request.files.get('audio')

        if not audio_file or not audio_file.filename:
            return jsonify({'error': 'audio file is required in the "audio" form field'}), 400

        suffix = os.path.splitext(audio_file.filename)[1] or '.webm'
        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                audio_file.save(temp_file)
                temp_path = temp_file.name

            transcript, transcription_source = parser.transcribe_audio_with_source(temp_path)
            return jsonify({
                'transcript': transcript,
                'source': transcription_source,
            }), 200
        except (FileNotFoundError, ValueError) as exc:
            return jsonify({'error': str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({'error': str(exc)}), 502
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)


    @flask_app.route('/api/audio/draft/text', methods=['POST'])
    def create_text_expense_draft():
        """
        Parse user-written explanation text into an expense draft.
        This keeps the same draft-review flow as audio, without persisting data.
        """
        payload = request.get_json(silent=True) or {}
        explanation_text = (payload.get('text') or request.form.get('text') or '').strip()
        group_members = _parse_request_group_members(payload, request.form)
        narrator_name = (payload.get('narrator_name') or request.form.get('narrator_name') or '').strip() or None

        if not explanation_text:
            return jsonify({'error': 'text is required'}), 400

        draft = parser.parse_transcript(
            explanation_text,
            transcription_used_ai=_has_ai_parser(),
            transcription_source='manual',
            group_members=group_members,
            narrator_name=narrator_name,
        )
        return jsonify(draft.model_dump()), 200


    @flask_app.route('/api/audio/parse', methods=['POST'])
    def parse_expense_transcript():
        """
        Parse a transcript that the user has already reviewed or edited.
        This route powers the chat-style transcript confirmation flow.
        """
        payload = request.get_json(silent=True) or {}
        transcript = (payload.get('transcript') or request.form.get('transcript') or '').strip()
        group_members = _parse_request_group_members(payload, request.form)
        narrator_name = (payload.get('narrator_name') or request.form.get('narrator_name') or '').strip() or None

        if not transcript:
            return jsonify({'error': 'transcript is required'}), 400

        draft = parser.parse_transcript(
            transcript,
            transcription_used_ai=_has_ai_parser(),
            transcription_source='edited-transcript',
            group_members=group_members,
            narrator_name=narrator_name,
        )
        return jsonify(draft.model_dump()), 200


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
        balances = settlement.calculate_balances(group_id)

        if not group:
            return 'Group not found', 404

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
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', '5001'))
    app.run(debug=True, host=host, port=port)

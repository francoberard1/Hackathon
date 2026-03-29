"""
Helpers for validating reviewed receipt drafts and computing exact shares.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


TWOPLACES = Decimal("0.01")


class ReceiptReviewValidationError(ValueError):
    """Raised when the reviewed receipt payload is invalid."""


def extract_receipt_review_form_state(form) -> dict:
    """
    Extract raw form values so the review template can be repopulated after errors.
    """
    state = {
        'description': (form.get('description') or '').strip(),
        'merchant_name': (form.get('merchant_name') or '').strip(),
        'currency': (form.get('currency') or '').strip().upper(),
        'subtotal_amount': (form.get('subtotal_amount') or '').strip(),
        'tax_amount': (form.get('tax_amount') or '').strip(),
        'tip_amount': (form.get('tip_amount') or '').strip(),
        'total_amount': (form.get('total_amount') or '').strip(),
        'confidence': (form.get('confidence') or '').strip(),
        'notes': (form.get('notes') or '').strip(),
        'payer_id': (form.get('payer_id') or '').strip(),
        'expense_date': (form.get('expense_date') or '').strip(),
        'selected_tax_participants': [value for value in form.getlist('tax_split_participants')],
        'selected_tip_participants': [value for value in form.getlist('tip_split_participants')],
        'items': [],
    }

    item_names = form.getlist('item_name[]')
    item_amounts = form.getlist('item_amount[]')
    item_user_ids = form.getlist('item_user_id[]')
    item_enabled = form.getlist('item_enabled[]')

    max_items = max(len(item_names), len(item_amounts), len(item_user_ids), len(item_enabled))
    for index in range(max_items):
        state['items'].append(
            {
                'name': (item_names[index] if index < len(item_names) else '').strip(),
                'amount': (item_amounts[index] if index < len(item_amounts) else '').strip(),
                'assigned_user_id': (item_user_ids[index] if index < len(item_user_ids) else '').strip(),
                'enabled': (item_enabled[index] if index < len(item_enabled) else '1').strip() != '0',
            }
        )

    return state


def validate_receipt_review_submission(form, members: list[dict]) -> dict:
    """
    Validate the reviewed receipt form and compute exact per-person shares.
    """
    member_ids = {member['id'] for member in members}
    if not member_ids:
        raise ReceiptReviewValidationError("Add at least one group member before using receipt review.")

    description = (form.get('description') or '').strip()
    if not description:
        raise ReceiptReviewValidationError("Description is required.")

    payer_id = _parse_member_id(form.get('payer_id'), member_ids, "Select a valid payer.")
    expense_date = (form.get('expense_date') or '').strip()
    subtotal_amount = _parse_amount(form.get('subtotal_amount'), "Subtotal must be a valid amount.")
    tax_amount = _parse_amount(form.get('tax_amount'), "Tax must be a valid amount.")
    tip_amount = _parse_amount(form.get('tip_amount'), "Tip must be a valid amount.")
    total_amount = _parse_amount(form.get('total_amount'), "Total must be a valid amount.")
    confidence = _parse_optional_decimal(form.get('confidence'))
    notes = (form.get('notes') or '').strip()
    merchant_name = (form.get('merchant_name') or '').strip()
    currency = (form.get('currency') or 'ARS').strip().upper() or 'ARS'

    item_names = form.getlist('item_name[]')
    item_amounts = form.getlist('item_amount[]')
    item_user_ids = form.getlist('item_user_id[]')
    item_enabled = form.getlist('item_enabled[]')
    enabled_items = _build_enabled_items(item_names, item_amounts, item_user_ids, item_enabled, member_ids)
    if not enabled_items:
        raise ReceiptReviewValidationError("Keep at least one receipt item before continuing.")

    item_sum = sum((item['amount'] for item in enabled_items), Decimal("0.00"))
    computed_subtotal = item_sum.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    if subtotal_amount == Decimal("0.00"):
        subtotal_amount = computed_subtotal

    selected_tax_participants = _parse_member_id_list(
        form.getlist('tax_split_participants'),
        member_ids,
        "Select valid participants for tax split.",
    )
    selected_tip_participants = _parse_member_id_list(
        form.getlist('tip_split_participants'),
        member_ids,
        "Select valid participants for tip split.",
    )

    if tax_amount > Decimal("0.00") and not selected_tax_participants:
        raise ReceiptReviewValidationError("Select at least one participant for tax split.")
    if tip_amount > Decimal("0.00") and not selected_tip_participants:
        raise ReceiptReviewValidationError("Select at least one participant for tip split.")

    computed_total = (item_sum + tax_amount + tip_amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    if total_amount <= Decimal("0.00"):
        total_amount = computed_total
    if total_amount != computed_total:
        raise ReceiptReviewValidationError(
            "Total must equal items + tax + tip after your edits."
        )

    share_cents = {}
    for item in enabled_items:
        share_cents[item['assigned_user_id']] = share_cents.get(item['assigned_user_id'], 0) + _to_cents(item['amount'])

    _allocate_even_split(share_cents, selected_tax_participants, tax_amount)
    _allocate_even_split(share_cents, selected_tip_participants, tip_amount)

    if sum(share_cents.values()) != _to_cents(total_amount):
        raise ReceiptReviewValidationError("Exact share calculation does not match the reviewed total.")

    share_amounts_by_user = {
        user_id: _from_cents(cents)
        for user_id, cents in sorted(share_cents.items())
        if cents > 0
    }
    participant_ids = list(share_amounts_by_user.keys())
    if not participant_ids:
        raise ReceiptReviewValidationError("At least one participant must owe part of the receipt.")

    return {
        'description': description,
        'payer_id': payer_id,
        'expense_date': expense_date,
        'subtotal_amount': float(subtotal_amount),
        'tax_amount': float(tax_amount),
        'tip_amount': float(tip_amount),
        'total_amount': float(total_amount),
        'currency': currency,
        'confidence': float(confidence),
        'notes': notes,
        'merchant_name': merchant_name,
        'participant_ids': participant_ids,
        'share_amounts_by_user': share_amounts_by_user,
    }


def _build_enabled_items(item_names, item_amounts, item_user_ids, item_enabled, member_ids):
    max_items = max(len(item_names), len(item_amounts), len(item_user_ids), len(item_enabled))
    enabled_items = []

    for index in range(max_items):
        enabled = (item_enabled[index] if index < len(item_enabled) else '1').strip() != '0'
        if not enabled:
            continue

        name = (item_names[index] if index < len(item_names) else '').strip()
        if not name:
            raise ReceiptReviewValidationError("Each kept item needs a name.")

        amount = _parse_amount(
            item_amounts[index] if index < len(item_amounts) else '',
            "Each kept item needs a valid amount.",
        )
        if amount <= Decimal("0.00"):
            raise ReceiptReviewValidationError("Each kept item must be greater than 0.")

        assigned_user_id = _parse_member_id(
            item_user_ids[index] if index < len(item_user_ids) else '',
            member_ids,
            "Assign every kept item to one participant.",
        )

        enabled_items.append(
            {
                'name': name,
                'amount': amount,
                'assigned_user_id': assigned_user_id,
            }
        )

    return enabled_items


def _allocate_even_split(share_cents, participant_ids, amount):
    if amount <= Decimal("0.00") or not participant_ids:
        return

    total_cents = _to_cents(amount)
    base, remainder = divmod(total_cents, len(participant_ids))
    for index, user_id in enumerate(sorted(participant_ids)):
        cents = base + (1 if index < remainder else 0)
        share_cents[user_id] = share_cents.get(user_id, 0) + cents


def _parse_member_id(raw_value, valid_member_ids, error_message):
    try:
        member_id = int(raw_value)
    except (TypeError, ValueError):
        raise ReceiptReviewValidationError(error_message)

    if member_id not in valid_member_ids:
        raise ReceiptReviewValidationError(error_message)
    return member_id


def _parse_member_id_list(values, valid_member_ids, error_message):
    parsed = []
    seen = set()
    for value in values:
        try:
            member_id = int(value)
        except (TypeError, ValueError):
            raise ReceiptReviewValidationError(error_message)
        if member_id not in valid_member_ids:
            raise ReceiptReviewValidationError(error_message)
        if member_id not in seen:
            parsed.append(member_id)
            seen.add(member_id)
    return parsed


def _parse_amount(value, error_message):
    raw = (value or '').strip()
    if raw == '':
        return Decimal("0.00")

    try:
        amount = Decimal(raw)
    except Exception:
        raise ReceiptReviewValidationError(error_message)

    if amount < Decimal("0.00"):
        raise ReceiptReviewValidationError(error_message)
    return amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _parse_optional_decimal(value):
    raw = (value or '').strip()
    if raw == '':
        return Decimal("0.00")
    try:
        confidence = Decimal(raw)
    except Exception:
        return Decimal("0.00")
    if confidence < Decimal("0.00"):
        return Decimal("0.00")
    if confidence > Decimal("1.00"):
        return Decimal("1.00")
    return confidence.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def _to_cents(amount):
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _from_cents(cents):
    return float((Decimal(cents) / 100).quantize(TWOPLACES, rounding=ROUND_HALF_UP))

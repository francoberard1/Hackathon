"""
Schema helpers for the Gemini-backed receipt draft pipeline.
"""

from __future__ import annotations

from copy import deepcopy


RECEIPT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {
            "type": "string",
            "description": "Short receipt description, usually the merchant and meal context.",
        },
        "total_amount": {
            "type": "number",
            "description": "Receipt total amount. Use 0 when not confidently found.",
        },
        "currency": {
            "type": "string",
            "description": "Three-letter currency code when visible, otherwise infer the most likely local currency conservatively.",
        },
        "payer_name": {
            "type": "string",
            "description": "Leave empty because the receipt does not identify the payer for this phase.",
        },
        "participants": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Leave empty because this phase does not infer diners.",
        },
        "tip_amount": {
            "type": "number",
            "description": "Tip or service amount when visible, otherwise 0.",
        },
        "notes": {
            "type": "string",
            "description": "Short notes about ambiguity, unreadable fields, or missing values.",
        },
        "confidence": {
            "type": "number",
            "description": "Extraction confidence between 0 and 1.",
        },
        "needs_review": {
            "type": "boolean",
            "description": "Always true for this draft extraction phase.",
        },
        "merchant_name": {
            "type": "string",
            "description": "Merchant or restaurant name when visible.",
        },
        "subtotal_amount": {
            "type": "number",
            "description": "Subtotal amount before tax and tip when visible, otherwise 0.",
        },
        "tax_amount": {
            "type": "number",
            "description": "Tax or VAT amount when visible, otherwise 0.",
        },
        "extracted_items": {
            "type": "array",
            "description": "Purchased food and drink line items only. Do not infer ownership.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Receipt line item name.",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Line item amount when visible, otherwise 0.",
                    },
                },
                "required": ["name", "amount"],
                "propertyOrdering": ["name", "amount"],
            },
        },
    },
    "required": [
        "description",
        "total_amount",
        "currency",
        "payer_name",
        "participants",
        "tip_amount",
        "notes",
        "confidence",
        "needs_review",
        "merchant_name",
        "subtotal_amount",
        "tax_amount",
        "extracted_items",
    ],
    "propertyOrdering": [
        "description",
        "total_amount",
        "currency",
        "payer_name",
        "participants",
        "tip_amount",
        "notes",
        "confidence",
        "needs_review",
        "merchant_name",
        "subtotal_amount",
        "tax_amount",
        "extracted_items",
    ],
}


DEFAULT_RECEIPT_DRAFT = {
    "description": "",
    "total_amount": 0.0,
    "currency": "ARS",
    "payer_name": "",
    "participants": [],
    "tip_amount": 0.0,
    "notes": "",
    "confidence": 0.0,
    "needs_review": True,
    "merchant_name": "",
    "subtotal_amount": 0.0,
    "tax_amount": 0.0,
    "extracted_items": [],
}


def empty_receipt_draft() -> dict:
    """Return a new default receipt draft payload."""
    return deepcopy(DEFAULT_RECEIPT_DRAFT)

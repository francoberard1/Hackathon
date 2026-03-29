"""
Schema helpers for the Gemini-backed receipt draft pipeline.
"""

from __future__ import annotations

from copy import deepcopy


RECEIPT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "total_amount": {"type": "number"},
        "currency": {"type": "string"},
        "payer_name": {"type": "string"},
        "participants": {"type": "array", "items": {"type": "string"}},
        "tip_amount": {"type": "number"},
        "notes": {"type": "string"},
        "confidence": {"type": "number"},
        "needs_review": {"type": "boolean"},
        "merchant_name": {"type": "string"},
        "subtotal_amount": {"type": "number"},
        "tax_amount": {"type": "number"},
        "extracted_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "amount": {"type": "number"},
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

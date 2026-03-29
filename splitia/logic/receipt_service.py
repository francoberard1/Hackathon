"""
Gemini-backed restaurant receipt draft extraction.
"""

from __future__ import annotations

import base64
import json
import os
import ssl
from typing import Any
from urllib import error, request

from .receipt_prompt import build_receipt_extraction_prompt
from .receipt_schema import RECEIPT_RESPONSE_SCHEMA, empty_receipt_draft

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None


GEMINI_MODEL = os.getenv("GEMINI_RECEIPT_MODEL", "gemini-2.5-flash")
GEMINI_API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={api_key}"
)
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
PLACEHOLDER_API_KEYS = {
    "PASTE_YOUR_REAL_KEY_HERE",
    "YOUR_GEMINI_API_KEY",
    "YOUR_API_KEY",
    "CHANGE_ME",
}


class ReceiptDraftError(Exception):
    error_code = "receipt_draft_error"


class ReceiptValidationError(ReceiptDraftError):
    error_code = "invalid_receipt_upload"


class ReceiptConfigurationError(ReceiptDraftError):
    error_code = "receipt_configuration_error"


class ReceiptAuthenticationError(ReceiptDraftError):
    error_code = "gemini_auth_error"


class ReceiptTransportError(ReceiptDraftError):
    error_code = "gemini_transport_error"


class ReceiptProviderError(ReceiptDraftError):
    error_code = "gemini_provider_error"


class ReceiptResponseError(ReceiptProviderError):
    error_code = "gemini_response_error"


def build_receipt_draft(file_storage) -> dict[str, Any]:
    payload = _read_upload(file_storage)
    draft = _call_gemini_for_receipt(payload["bytes"], payload["mime_type"])
    return sanitize_receipt_draft(draft)


def sanitize_receipt_draft(raw_draft: Any) -> dict[str, Any]:
    draft = empty_receipt_draft()
    if not isinstance(raw_draft, dict):
        raw_draft = {}

    draft["description"] = _clean_text(raw_draft.get("description"))
    draft["total_amount"] = _clean_amount(raw_draft.get("total_amount"))
    draft["currency"] = _clean_currency(raw_draft.get("currency"))
    draft["payer_name"] = ""
    draft["participants"] = []
    draft["tip_amount"] = _clean_amount(raw_draft.get("tip_amount"))
    draft["notes"] = _clean_text(raw_draft.get("notes"))
    draft["confidence"] = _clean_confidence(raw_draft.get("confidence"))
    draft["needs_review"] = True
    draft["merchant_name"] = _clean_text(raw_draft.get("merchant_name"))
    draft["subtotal_amount"] = _clean_amount(raw_draft.get("subtotal_amount"))
    draft["tax_amount"] = _clean_amount(raw_draft.get("tax_amount"))
    draft["extracted_items"] = _clean_items(raw_draft.get("extracted_items"))

    if not draft["description"] and draft["merchant_name"]:
        draft["description"] = f"Receipt from {draft['merchant_name']}"

    if not draft["notes"]:
        draft["notes"] = "Gemini receipt draft extraction. Review before saving."

    return draft


def _read_upload(file_storage) -> dict[str, Any]:
    if not file_storage or not getattr(file_storage, "filename", ""):
        raise ReceiptValidationError("Missing uploaded image file.")

    mime_type = (file_storage.mimetype or "").lower().strip()
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ReceiptValidationError(
            "Unsupported image type. Use JPEG, PNG, WEBP, HEIC, or HEIF."
        )

    image_bytes = file_storage.read()
    if not image_bytes:
        raise ReceiptValidationError("Uploaded image is empty.")

    try:
        file_storage.stream.seek(0)
    except Exception:
        pass

    return {"bytes": image_bytes, "mime_type": mime_type}


def _call_gemini_for_receipt(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
    api_key = _resolve_gemini_api_key()

    request_body = {
        "contents": [
            {
                "parts": [
                    {"text": build_receipt_extraction_prompt()},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": RECEIPT_RESPONSE_SCHEMA,
            "temperature": 0.1,
        },
    }

    http_request = request.Request(
        GEMINI_API_URL_TEMPLATE.format(model=GEMINI_MODEL, api_key=api_key),
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=45, context=_build_verified_ssl_context()) as response:
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        provider_body = exc.read().decode("utf-8", errors="ignore")
        if exc.code in (401, 403) or _provider_rejected_api_key(exc.code, provider_body):
            raise ReceiptAuthenticationError(
                "Gemini rejected the configured API key. Use a valid Google AI Studio Gemini API key in splitia/.env."
            ) from exc
        raise ReceiptProviderError(_build_http_error_message(exc.code, provider_body)) from exc
    except error.URLError as exc:
        raise _classify_url_error(exc) from exc

    return _parse_gemini_response(response_body)


def _resolve_gemini_api_key() -> str:
    for env_var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_AI_API_KEY"):
        api_key = os.getenv(env_var, "").strip()
        if not api_key:
            continue
        if _looks_like_placeholder_api_key(api_key):
            raise ReceiptConfigurationError(
                f"{env_var} contains a placeholder value. Set a real Gemini API key in splitia/.env."
            )
        return api_key

    raise ReceiptConfigurationError(
        "Gemini API key is not configured. Set GEMINI_API_KEY in splitia/.env."
    )


def _looks_like_placeholder_api_key(api_key: str) -> bool:
    normalized = api_key.strip().strip("\"'")
    if not normalized:
        return True
    uppercase_value = normalized.upper()
    return (
        uppercase_value in PLACEHOLDER_API_KEYS
        or "PASTE" in uppercase_value
        or "YOUR_REAL_KEY" in uppercase_value
        or "YOUR_API_KEY" in uppercase_value
    )


def _parse_gemini_response(response_body: str) -> dict[str, Any]:
    try:
        payload = json.loads(response_body)
        candidates = payload.get("candidates") or []
        first_candidate = candidates[0]
        parts = first_candidate["content"]["parts"]
        text_part = next(
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and part.get("text")
        )
        parsed = json.loads(text_part)
    except (IndexError, KeyError, StopIteration, TypeError, json.JSONDecodeError) as exc:
        raise ReceiptResponseError("Gemini returned an invalid structured response.") from exc

    if not isinstance(parsed, dict):
        raise ReceiptResponseError("Gemini returned a non-object receipt draft.")

    return parsed


def _build_verified_ssl_context() -> ssl.SSLContext:
    default_context = ssl.create_default_context()
    if default_context.get_ca_certs():
        return default_context
    if certifi is not None:
        certifi_bundle = certifi.where()
        if certifi_bundle and os.path.exists(certifi_bundle):
            return ssl.create_default_context(cafile=certifi_bundle)
    raise ReceiptTransportError("TLS certificate verification failed while contacting Gemini.")


def _classify_url_error(exc: error.URLError) -> ReceiptTransportError:
    return ReceiptTransportError(
        f"Could not reach Gemini safely: {getattr(exc, 'reason', 'transport error')}."
    )


def _provider_rejected_api_key(status_code: int, provider_body: str) -> bool:
    if status_code != 400:
        return False
    body = provider_body.lower()
    return "api key not valid" in body or "invalid api key" in body


def _build_http_error_message(status_code: int, provider_body: str) -> str:
    try:
        payload = json.loads(provider_body)
        provider_message = payload.get("error", {}).get("message", "")
    except json.JSONDecodeError:
        provider_message = ""

    if provider_message:
        return f"Gemini returned HTTP {status_code}: {provider_message}"
    return f"Gemini returned HTTP {status_code}."


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_amount(value: Any) -> float:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0
    return round(max(amount, 0), 2)


def _clean_currency(value: Any) -> str:
    currency = str(value or "ARS").strip().upper()
    return currency[:3] or "ARS"


def _clean_confidence(value: Any) -> float:
    try:
        confidence = float(value or 0)
    except (TypeError, ValueError):
        confidence = 0
    return round(min(max(confidence, 0), 1), 3)


def _clean_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    cleaned_items = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = _clean_text(item.get("name"))
        amount = _clean_amount(item.get("amount"))
        if not name and amount <= 0:
            continue
        cleaned_items.append({"name": name, "amount": amount})
    return cleaned_items

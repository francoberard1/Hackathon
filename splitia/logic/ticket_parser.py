"""
Text-first ticket parser for hackathon use.

This module is intentionally simple:
- it works on raw text that may come from OCR later
- it does not depend on Flask routes or app state
- it returns a stable structure that other parts of the app can consume

Current strategy:
1. Normalize OCR-ish text
2. Split into lines
3. Keep only item-like candidate lines
4. Take the last numeric token in each line as the price
5. Return parsed items plus summary metadata

The parser is heuristic-based on purpose. It is designed for demo reliability,
not for production-grade receipt parsing.
"""

from __future__ import annotations

import re
import unicodedata


IGNORED_LINE_KEYWORDS = {
    "TOTAL",
    "SUBTOTAL",
    "TOTALE",
    "SUBTOTALE",
    "IVA",
    "VAT",
    "TAX",
    "DESCUENTO",
    "PROPINA",
    "CAMBIO",
    "TARJETA",
    "EFECTIVO",
}

TOTAL_LINE_KEYWORDS = {
    "TOTAL",
    "TOTALE",
    "AMOUNT",
    "DUE",
}

SUBTOTAL_LINE_KEYWORDS = {
    "SUBTOTAL",
    "SUBTOTALE",
}

HEADER_LINE_KEYWORDS = {
    "ADDRESS",
    "AV",
    "AVDA",
    "AVENIDA",
    "BAR",
    "CALLE",
    "CITY",
    "CONTACT",
    "CUIT",
    "CIF",
    "COUNTRY",
    "DELIVERY",
    "FAX",
    "FISCAL",
    "GUEST",
    "GUESTS",
    "HOSTERIA",
    "HOTEL",
    "INVOICE",
    "LINEA",
    "LLC",
    "LOCAL",
    "LTD",
    "MESA",
    "MOVIL",
    "MOBILE",
    "NIF",
    "ORDER",
    "OSPITE",
    "PAGER",
    "PHONE",
    "PIZZERIA",
    "RESTAURANT",
    "RISTORANTE",
    "ROAD",
    "SA",
    "SRL",
    "SRLS",
    "ST",
    "STREET",
    "TABLE",
    "TAVOLO",
    "TEL",
    "TELEFONO",
    "TICKET",
    "VAT",
    "VIA",
}

MIN_NAME_LENGTH = 2
DEFAULT_CONFIDENCE = 0.72
MAX_REASONABLE_PRICE = 99999.99
MAX_DIGITS_WITHOUT_SEPARATORS = 5
CURRENCY_TOKENS = {"EUR", "EURO", "USD", "GBP", "ARS", "MXN"}
PRICE_TOKEN_RE = re.compile(r"(?<!\w)(?:[$€£]\s*)?\d[\d\.,]*")
QUANTITY_PREFIX_RE = re.compile(r"^\s*\d+(?:[\.,]\d+)?(?:\s*[Xx])?\s+")
TRAILING_PRICE_RE = re.compile(r"(?:[$€£¥]?\s*[=:;.,*~\\-]*\s*)(\d[\d\.,]*)\s*$")
ADDRESS_HINT_RE = re.compile(
    r"\b(?:VIA|CALLE|AV(?:DA|ENIDA)?|ROAD|STREET|RD|AVE|PIAZZA|PLAZA)\b"
)
TAX_ID_HINT_RE = re.compile(r"\b(?:P\.?\s*IVA|CUIT|CIF|NIF|VAT)\b")
ITEM_WARNING_DELTA = 0.01


def normalize_ocr_text(raw_text: str) -> str:
    """
    Normalize raw ticket text into a line-oriented string.

    Keeps line breaks because line boundaries are useful to detect items.
    """
    if not raw_text:
        return ""

    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\t", " ")
    text = text.replace("\u00a0", " ")

    normalized_lines = []
    for line in text.split("\n"):
        clean_line = re.sub(r"\s+", " ", line).strip()
        if clean_line:
            normalized_lines.append(clean_line)

    return "\n".join(normalized_lines)


def strip_accents(value: str) -> str:
    """Return an accent-insensitive version of a string."""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def is_ignored_line(line: str) -> bool:
    """Return True when a line matches a known non-item ticket concept."""
    upper_line = strip_accents(line).upper()
    tokens = set(re.findall(r"[A-Z]+", upper_line))
    if not any(keyword in tokens for keyword in IGNORED_LINE_KEYWORDS):
        return False

    if looks_like_quantity_prefixed_item(line):
        return False

    final_price = extract_final_price_candidate(line)
    if final_price is None:
        return True

    _, price_start, _ = final_price
    name_part = strip_quantity_prefix(line[:price_start].strip())
    name_tokens = set(re.findall(r"[A-Z]+", strip_accents(name_part).upper()))
    non_ignored_tokens = name_tokens.difference(IGNORED_LINE_KEYWORDS | CURRENCY_TOKENS)
    return not non_ignored_tokens


def has_long_numeric_sequence(line: str) -> bool:
    """Return True when a line contains long digit runs typical of phone/tax ids."""
    compact = re.sub(r"[^\d]", "", line)
    return len(compact) > MAX_DIGITS_WITHOUT_SEPARATORS


def has_metadata_keywords(line: str) -> bool:
    """Return True for common business header/legal/contact lines across languages."""
    upper_line = strip_accents(line).upper()
    tokens = set(re.findall(r"[A-Z]+", upper_line))
    return any(keyword in tokens for keyword in HEADER_LINE_KEYWORDS)


def has_strong_metadata_signal(line: str) -> bool:
    """Return True for lines that are very likely header/contact metadata."""
    upper_line = strip_accents(line).upper()

    if "@" in line or "WWW." in upper_line or ".COM" in upper_line:
        return True

    if TAX_ID_HINT_RE.search(upper_line) and has_long_numeric_sequence(line):
        return True

    if re.search(r"\b(?:TEL|PHONE|MOBILE|MOVIL|FAX)\b", upper_line) and has_long_numeric_sequence(line):
        return True

    if ADDRESS_HINT_RE.search(upper_line) and re.search(r"\d", line):
        return True

    if re.search(r"\b[A-Z]{1,4}\s+\d{3,6}\b", upper_line):
        return True

    return False


def looks_like_address_or_contact_line(line: str) -> bool:
    """Filter obvious address, website, contact, or tax-id style lines."""
    upper_line = strip_accents(line).upper()

    if re.search(r"\b(?:TABLE|TAVOLO|MESA)\b", upper_line):
        return True

    if re.search(r"\b(?:NO|NRO|NUM|NUMBER)\b", upper_line) and has_long_numeric_sequence(line):
        return True

    if has_strong_metadata_signal(line):
        return True

    if has_metadata_keywords(line) and not has_reasonable_trailing_price(line):
        return True

    return False


def has_price_candidate(line: str) -> bool:
    """Return True if the line contains at least one number-like token."""
    return bool(_find_price_matches(line))


def looks_like_item_name(line: str) -> bool:
    """
    Heuristic: candidate item lines should include some alphabetic content.
    """
    letters_only = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]", "", line).strip()
    return len(letters_only.replace(" ", "")) >= MIN_NAME_LENGTH


def strip_quantity_prefix(line: str) -> str:
    """Remove leading quantity markers like '2 ', '3x ', or '1.5 ' from an item line."""
    return QUANTITY_PREFIX_RE.sub("", line, count=1).strip()


def looks_like_quantity_prefixed_item(line: str) -> bool:
    """
    Accept item lines that start with a quantity and end with a valid price.

    Examples:
    - 3 COPERTO CENA 6.00
    - 2 WATER 5.00
    - 1x CAFE 2.50
    """
    if not QUANTITY_PREFIX_RE.match(line):
        return False

    final_price = extract_final_price_candidate(line)
    if final_price is None:
        return False

    _, price_start, _ = final_price
    middle_text = strip_quantity_prefix(line[:price_start].strip())
    return looks_like_item_name(middle_text)


def is_plausible_item_line(line: str) -> bool:
    """
    Return True for lines that strongly resemble item entries.

    A valid item line must have alphabetic content plus a plausible trailing
    price, with or without an explicit quantity prefix.
    """
    if not line or not has_price_candidate(line):
        return False

    if looks_like_quantity_prefixed_item(line):
        return True

    if not has_reasonable_trailing_price(line):
        return False

    final_price = extract_final_price_candidate(line)
    if final_price is None:
        return False

    _, price_start, _ = final_price
    name_part = line[:price_start].strip()
    return looks_like_item_name(name_part)


def extract_candidate_lines(normalized_text: str) -> list[str]:
    """
    Return lines that look like parseable ticket items.
    """
    if not normalized_text:
        return []

    candidates = []
    for line in normalized_text.split("\n"):
        if is_ignored_line(line):
            continue
        if looks_like_address_or_contact_line(line) and not looks_like_quantity_prefixed_item(line):
            continue
        plausible_item = is_plausible_item_line(line)
        if not plausible_item:
            continue
        candidates.append(line)

    return candidates


def _find_price_matches(line: str) -> list[re.Match[str]]:
    """
    Find number-like tokens that can represent prices.

    Supported examples:
    - 12000
    - 12.000
    - 12,000
    - 12000.50
    - 12000,50
    - $ 12.000,50
    """
    return list(PRICE_TOKEN_RE.finditer(line))


def _parse_price_token(token: str) -> float | None:
    """
    Convert a price-like token into float.

    Heuristic rules:
    - if both '.' and ',' exist, the last separator is treated as decimal
    - if only one separator exists once and has 1-2 digits after it, treat as decimal
    - otherwise separators are treated as thousands separators
    """
    if not token:
        return None

    cleaned = re.sub(r"[^\d\.,]", "", token)
    if not cleaned:
        return None

    if "." in cleaned and "," in cleaned:
        last_dot = cleaned.rfind(".")
        last_comma = cleaned.rfind(",")
        decimal_sep = "." if last_dot > last_comma else ","
        thousands_sep = "," if decimal_sep == "." else "."
        normalized = cleaned.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif cleaned.count(".") == 1 and cleaned.count(",") == 0:
        left, right = cleaned.split(".")
        normalized = cleaned if len(right) in (1, 2) else left + right
    elif cleaned.count(",") == 1 and cleaned.count(".") == 0:
        left, right = cleaned.split(",")
        normalized = cleaned.replace(",", ".") if len(right) in (1, 2) else left + right
    else:
        normalized = cleaned.replace(".", "").replace(",", "")

    try:
        return float(normalized)
    except ValueError:
        return None


def extract_final_price_candidate(line: str) -> tuple[float, int, int] | None:
    """
    Extract the final plausible price from a line, tolerating light OCR noise.
    """
    if not line:
        return None

    match = TRAILING_PRICE_RE.search(line)
    if not match:
        return None

    token = match.group(1)
    price = _parse_price_token(token)
    if price is None or price <= 0 or price > MAX_REASONABLE_PRICE:
        return None

    raw_digits = re.sub(r"[^\d]", "", token)
    if len(raw_digits) > MAX_DIGITS_WITHOUT_SEPARATORS and "." not in token and "," not in token:
        return None

    return price, match.start(1), match.end(1)


def has_reasonable_trailing_price(line: str) -> bool:
    """
    Keep lines whose last numeric token looks like a plausible item price.

    This helps reject phones, tax ids, postal codes, and other long numbers
    that OCR may place in otherwise parseable header lines.
    """
    final_price = extract_final_price_candidate(line)
    if final_price is None:
        return False

    _, price_start, _ = final_price
    name_part = line[:price_start].strip()
    return looks_like_item_name(name_part)


def _cleanup_item_name(name: str) -> str:
    """Remove noisy punctuation and collapse whitespace in an item name."""
    cleaned = re.sub(r"[-_=*#]+", " ", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_:;,.")
    return cleaned


def parse_line_item(line: str) -> dict | None:
    """
    Parse one item line into {'name': str, 'price': float}.

    Strategy:
    - take the last price-like token as the price
    - everything before that token becomes the candidate name
    """
    final_price = extract_final_price_candidate(line)
    if final_price is None:
        return None

    price, price_start, _ = final_price
    name_part = line[:price_start].strip()
    name = _cleanup_item_name(name_part)

    if len(name) < MIN_NAME_LENGTH:
        return None

    return {
        "name": name,
        "price": price,
    }


def extract_total_detected(normalized_text: str) -> float | None:
    """
    Extract an explicit ticket total when present.

    This is intentionally simple and hackathon-friendly:
    - prefer lines that mention TOTAL
    - ignore subtotal-like lines
    - take the last price-like token from the matching line
    """
    if not normalized_text:
        return None

    total_candidates = []
    for line in normalized_text.split("\n"):
        upper_line = strip_accents(line).upper()
        tokens = set(re.findall(r"[A-Z]+", upper_line))

        if not any(keyword in tokens for keyword in TOTAL_LINE_KEYWORDS):
            continue
        if any(keyword in tokens for keyword in SUBTOTAL_LINE_KEYWORDS):
            continue

        final_price = extract_final_price_candidate(line)
        if final_price is not None:
            total_candidates.append(final_price[0])

    return total_candidates[-1] if total_candidates else None


def summarize_ticket_items(items: list[dict], total_detected: float | None = None) -> dict:
    """Build summary fields derived from parsed items."""
    subtotal = round(sum(item["price"] for item in items), 2)
    return {
        "subtotal": subtotal,
        "total_detected": round(total_detected, 2) if total_detected is not None else subtotal,
        "warnings": [],
        "confidence": DEFAULT_CONFIDENCE if items else 0.0,
    }


def parse_ticket_text(raw_text: str) -> dict:
    """
    Parse raw ticket text and return a stable, integration-friendly payload.
    """
    normalized_text = normalize_ocr_text(raw_text)
    candidate_lines = extract_candidate_lines(normalized_text)
    detected_total = extract_total_detected(normalized_text)

    items = []
    rejected_lines = 0

    for line in candidate_lines:
        parsed_item = parse_line_item(line)
        if parsed_item is None:
            rejected_lines += 1
            continue
        items.append(parsed_item)

    summary = summarize_ticket_items(items, total_detected=detected_total)
    warnings = list(summary["warnings"])

    if not normalized_text.strip():
        warnings.append("No text provided to parse.")
    elif not candidate_lines:
        warnings.append("No candidate item lines detected in the ticket text.")
    elif rejected_lines:
        warnings.append(f"{rejected_lines} candidate line(s) could not be parsed cleanly.")

    if items and detected_total is not None and summary["subtotal"] + ITEM_WARNING_DELTA < detected_total:
        warnings.append(
            "Detected total is higher than the parsed items subtotal. Some item lines may be missing from OCR or parsing."
        )

    status = "ok" if items else "empty"
    confidence = summary["confidence"]
    if rejected_lines and items:
        confidence = round(max(0.3, confidence - 0.12), 2)

    return {
        "status": status,
        "source": "text",
        "raw_text": raw_text,
        "normalized_text": normalized_text,
        "items": items,
        "subtotal": summary["subtotal"],
        "total_detected": summary["total_detected"],
        "warnings": warnings,
        "confidence": confidence,
    }


if __name__ == "__main__":
    sample_text = """
    HAMBURGUESA DOBLE      12500
    PAPAS FRITAS           4500
    GASEOSA 500ML          3200
    SUBTOTAL               20200
    IVA                    0
    TOTAL                  20200
    """

    parsed = parse_ticket_text(sample_text)

    print("Parsed items:")
    for item in parsed["items"]:
        print(f"- {item['name']}: {item['price']}")

    print("\nFull payload:")
    print(parsed)

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
    "IVA",
    "DESCUENTO",
    "PROPINA",
    "CAMBIO",
    "TARJETA",
    "EFECTIVO",
}

MIN_NAME_LENGTH = 2
DEFAULT_CONFIDENCE = 0.72
PRICE_TOKEN_RE = re.compile(r"(?<!\w)(?:[$€£]\s*)?\d[\d\.,]*")


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
    return any(keyword in tokens for keyword in IGNORED_LINE_KEYWORDS)


def has_price_candidate(line: str) -> bool:
    """Return True if the line contains at least one number-like token."""
    return bool(_find_price_matches(line))


def looks_like_item_name(line: str) -> bool:
    """
    Heuristic: candidate item lines should include some alphabetic content.
    """
    letters_only = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]", "", line).strip()
    return len(letters_only.replace(" ", "")) >= MIN_NAME_LENGTH


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
        if not has_price_candidate(line):
            continue
        if not looks_like_item_name(line):
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
    matches = _find_price_matches(line)
    if not matches:
        return None

    last_match = matches[-1]
    price = _parse_price_token(last_match.group(0))
    if price is None:
        return None

    name_part = line[: last_match.start()].strip()
    name = _cleanup_item_name(name_part)

    if len(name) < MIN_NAME_LENGTH:
        return None

    return {
        "name": name,
        "price": price,
    }


def summarize_ticket_items(items: list[dict]) -> dict:
    """Build summary fields derived from parsed items."""
    subtotal = round(sum(item["price"] for item in items), 2)
    return {
        "subtotal": subtotal,
        "total_detected": subtotal,
        "warnings": [],
        "confidence": DEFAULT_CONFIDENCE if items else 0.0,
    }


def parse_ticket_text(raw_text: str) -> dict:
    """
    Parse raw ticket text and return a stable, integration-friendly payload.
    """
    normalized_text = normalize_ocr_text(raw_text)
    candidate_lines = extract_candidate_lines(normalized_text)

    items = []
    rejected_lines = 0

    for line in candidate_lines:
        parsed_item = parse_line_item(line)
        if parsed_item is None:
            rejected_lines += 1
            continue
        items.append(parsed_item)

    summary = summarize_ticket_items(items)
    warnings = list(summary["warnings"])

    if not normalized_text.strip():
        warnings.append("No text provided to parse.")
    elif not candidate_lines:
        warnings.append("No candidate item lines detected in the ticket text.")
    elif rejected_lines:
        warnings.append(f"{rejected_lines} candidate line(s) could not be parsed cleanly.")

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

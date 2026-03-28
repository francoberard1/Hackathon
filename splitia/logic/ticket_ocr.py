"""
Simple OCR helper for ticket images.

This module is intentionally minimal and isolated from the parser logic.
It turns an uploaded image into raw text so the existing text parser can
reuse the same flow for both manual input and ticket photos.
"""

from __future__ import annotations

from io import BytesIO
import re

try:
    from PIL import Image, ImageFilter, ImageOps
except ImportError:
    Image = None
    ImageFilter = None
    ImageOps = None

try:
    import pytesseract
except ImportError:
    pytesseract = None


DEFAULT_OCR_LANGS = ("eng", "spa", "ita")
OCR_CONFIGS = (
    "--oem 3 --psm 4",
    "--oem 3 --psm 6",
    "--oem 3 --psm 11",
)
TRAILING_PRICE_RE = re.compile(r"\d[\d\.,]*\s*$")


def _prepare_image_variants(image):
    """
    Build a small set of OCR-friendly image variants.

    Variants stay intentionally simple: upscale, normalize contrast, and try a
    binary pass to help light thermal receipt text.
    """
    grayscale = image.convert("L")
    base = ImageOps.autocontrast(grayscale)
    upscaled = grayscale.resize(
        (max(1, grayscale.width * 2), max(1, grayscale.height * 2)),
        resample=Image.Resampling.LANCZOS,
    )
    normalized = ImageOps.autocontrast(upscaled)
    sharpened = normalized.filter(ImageFilter.SHARPEN)
    thresholded = sharpened.point(lambda px: 255 if px > 160 else 0)
    return [grayscale, base, normalized, sharpened, thresholded]


def _get_available_languages() -> list[str]:
    """Return installed Tesseract languages, or an empty list when unavailable."""
    if pytesseract is None:
        return []

    try:
        return pytesseract.get_languages(config="")
    except Exception:
        return []


def _build_language_candidates(available_languages: list[str]) -> list[str]:
    """
    Return OCR language combinations, favoring multilingual runs when possible.
    """
    available = [lang for lang in DEFAULT_OCR_LANGS if lang in available_languages]
    if not available:
        available = ["eng"]

    candidates = []
    joined = "+".join(available)
    if joined:
        candidates.append(joined)

    for lang in available:
        if lang not in candidates:
            candidates.append(lang)

    return candidates


def _score_ocr_text(text: str) -> tuple[int, int, int]:
    """
    Prefer OCR results that look more like line-item receipts.
    """
    if not text:
        return (0, 0, 0)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    price_lines = sum(1 for line in lines if TRAILING_PRICE_RE.search(line))
    alpha_chars = sum(char.isalpha() for char in text)
    return (price_lines, len(lines), alpha_chars)


def _score_ocr_candidate_text(text: str) -> tuple[int, int, float, int, int, int]:
    """
    Prefer OCR results that also produce a coherent parsed receipt.
    """
    if not text:
        return (0, 0, float("-inf"), 0, 0, 0)

    try:
        from .ticket_parser import parse_ticket_text
    except ImportError:
        from logic.ticket_parser import parse_ticket_text

    parsed = parse_ticket_text(text)
    item_count = len(parsed["items"])
    subtotal = float(parsed["subtotal"])
    total_detected = parsed.get("total_detected")
    subtotal_gap = 0.0
    if total_detected is not None:
        subtotal_gap = abs(float(total_detected) - subtotal)

    price_lines, line_count, alpha_chars = _score_ocr_text(text)
    return (
        item_count,
        -len(parsed["warnings"]),
        -subtotal_gap,
        price_lines,
        line_count,
        alpha_chars,
    )


def extract_text_from_image(file_storage) -> str:
    """
    Extract OCR text from a Flask/Werkzeug uploaded file.

    Returns an empty string when OCR dependencies are unavailable, the upload
    is invalid, or text cannot be extracted cleanly.
    """
    if not file_storage or not getattr(file_storage, "filename", ""):
        return ""

    if Image is None or ImageOps is None or ImageFilter is None or pytesseract is None:
        return ""

    try:
        image_bytes = file_storage.read()
        if not image_bytes:
            return ""

        image = Image.open(BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)
        language_candidates = _build_language_candidates(_get_available_languages())

        best_text = ""
        best_score = (0, 0, float("-inf"), 0, 0, 0)

        for prepared_image in _prepare_image_variants(image):
            for language in language_candidates:
                for ocr_config in OCR_CONFIGS:
                    try:
                        ocr_text = pytesseract.image_to_string(
                            prepared_image,
                            lang=language,
                            config=ocr_config,
                        ).strip()
                    except Exception:
                        continue

                    score = _score_ocr_candidate_text(ocr_text)
                    if score > best_score:
                        best_text = ocr_text
                        best_score = score

        return best_text
    except Exception:
        return ""
    finally:
        try:
            file_storage.stream.seek(0)
        except Exception:
            pass

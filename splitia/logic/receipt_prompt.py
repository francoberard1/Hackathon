"""
Prompt builder for restaurant receipt draft extraction.
"""

from __future__ import annotations


def build_receipt_extraction_prompt() -> str:
    """
    Return the extraction prompt for Gemini.
    """
    return """
You are extracting a draft expense from a restaurant receipt image.

Return only data supported by the image. Do not invent or guess missing values.
This is a draft extraction step, not a final booking step.

Rules:
- Focus on restaurant, cafe, bar, and food delivery receipts.
- Extract purchased food/drink items when they are readable.
- Do not infer who consumed each item.
- Leave payer_name as an empty string.
- Leave participants as an empty array.
- Set needs_review to true.
- If a value is missing or unclear, use 0 for numeric amounts and an empty string for text.
- Keep confidence between 0 and 1.
- Use notes to mention uncertainty or unreadable totals.
- Use a 3-letter currency code when visible or strongly implied by the receipt.
- description should be a short human-readable summary like "Dinner at La Parolaccia".

Amount mapping:
- subtotal_amount: amount before tax and before tip when present.
- tax_amount: VAT/sales tax amount when present.
- tip_amount: gratuity/service/tip when present.
- total_amount: final total charged or due.

Item mapping:
- extracted_items should include only item rows for purchased food/drink.
- Exclude metadata like table number, waiter, discounts, payment method, and legal/tax lines unless the tax line belongs in tax_amount.
""".strip()

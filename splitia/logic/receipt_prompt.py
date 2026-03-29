"""
Prompt builder for structured receipt extraction.
"""


def build_receipt_extraction_prompt() -> str:
    return """
You are extracting a structured restaurant receipt draft from an uploaded image.

Return only valid JSON that matches the provided schema.

Rules:
- Extract only information visible in the receipt image.
- Keep payer_name empty because the receipt does not identify who in the group paid.
- Keep participants empty because the receipt does not identify diners reliably.
- Set needs_review to true.
- Use 0 for numeric fields that are not visible or not confident.
- extracted_items should include food and drink line items only.
- Do not infer item owners.
- Keep notes short and mention ambiguity if text is hard to read.
""".strip()

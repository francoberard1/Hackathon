"""
Minimal Pydantic schemas for structured expense draft responses.
"""

from pydantic import BaseModel, Field


class ExpenseParticipantDraft(BaseModel):
    name: str
    amount: float = Field(default=0)


class ExpenseDraft(BaseModel):
    description: str
    total_amount: float = Field(default=0)
    currency: str = Field(default='ARS')
    payer_name: str
    participants: list[ExpenseParticipantDraft] = Field(default_factory=list)
    tip_amount: float = Field(default=0)
    notes: str = Field(default='')
    confidence: float = Field(default=0)
    needs_review: bool = Field(default=True)

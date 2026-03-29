"""
Minimal Pydantic schemas for structured expense draft responses.
"""

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover - fallback for environments without pydantic installed
    class BaseModel:
        def __init__(self, **kwargs):
            annotations = getattr(self, '__annotations__', {})
            for field_name in annotations:
                default_value = getattr(self.__class__, field_name, None)
                if field_name in kwargs:
                    value = kwargs[field_name]
                elif isinstance(default_value, list):
                    value = list(default_value)
                elif isinstance(default_value, dict):
                    value = dict(default_value)
                else:
                    value = default_value
                setattr(self, field_name, value)

        def model_dump(self):
            return {
                field_name: getattr(self, field_name)
                for field_name in getattr(self, '__annotations__', {})
            }

    def Field(default=None, default_factory=None):
        if default_factory is not None:
            return default_factory()
        return default


class ExpenseParticipantDraft(BaseModel):
    name: str
    amount: float = Field(default=0)


class ExpenseDraft(BaseModel):
    description: str
    total_amount: float = Field(default=0)
    currency: str = Field(default='ARS')
    payer_name: str
    expense_date: str = Field(default='')
    participants: list[ExpenseParticipantDraft] = Field(default_factory=list)
    tip_amount: float = Field(default=0)
    notes: str = Field(default='')
    confidence: float = Field(default=0)
    needs_review: bool = Field(default=True)

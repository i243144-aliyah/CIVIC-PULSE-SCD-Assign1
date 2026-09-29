"""
app/schemas/triage.py
─────────────────────
Pydantic schema representing the outcome of a complaint triage operation.
Used across all TriageProvider implementations and AI services.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import ComplaintCategory, ComplaintPriority


class TriageResult(BaseModel):
    """
    Standardized result contract for all triage providers.

    Attributes
    ----------
    category : ComplaintCategory
        Civic service domain classified from complaint text.
    priority : ComplaintPriority
        Urgency level: high, normal, low.
    summary : str
        Single-sentence summary, maximum 140 characters.
    confidence : float
        Confidence score between 0.0 and 1.0.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    category: ComplaintCategory = Field(
        ...,
        description="Classified civic complaint category.",
    )
    priority: ComplaintPriority = Field(
        ...,
        description="Assigned urgency level: high, normal, or low.",
    )
    summary: str = Field(
        ...,
        max_length=140,
        description="Concise one-line summary (maximum 140 chars).",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence level of classification (0.0 to 1.0).",
    )

    @field_validator("summary", mode="before")
    @classmethod
    def enforce_summary_length(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip()
            if len(v) > 140:
                return v[:137] + "..."
        return v

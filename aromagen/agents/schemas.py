from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ValidationError, field_validator

from .settings import settings

SEQUENCE_TOTAL_SECONDS = settings.sequence_total_seconds
SCENT_DURATION_MAX = settings.scent_duration_max


class ComposeRequest(BaseModel):
    sentence: str = Field(min_length=1)


def scent_name_literal(choices: list[str]):
    # Utility to create a Literal type dynamically for static tooling awareness isn't possible at runtime,
    # but we keep this for clarity; we will validate via enum in OpenAI schema and Pydantic validator.
    return Literal[tuple(choices)]  # type: ignore[misc]


class ScentItem(BaseModel):
    scent_name: str
    scent_duration: float = Field(gt=0, le=SCENT_DURATION_MAX)


class ComposeResponse(BaseModel):
    scent_sequence: List[ScentItem]
    justification: str
    pulse_sequence: List[ScentItem] = []
    session_id: str = ""

    @field_validator("scent_sequence")
    @classmethod
    def validate_total_duration(cls, value: List[ScentItem]):
        total = sum(item.scent_duration for item in value)
        if total != SEQUENCE_TOTAL_SECONDS:
            raise ValueError(
                f"Total duration must equal {SEQUENCE_TOTAL_SECONDS}, got {total}"
            )
        return value


class FeedbackRound(BaseModel):
    feedback_text: str
    changes_made: str
    resulting_sequence: List[ScentItem]


class FeedbackRequest(BaseModel):
    original_sentence: str = Field(min_length=1)
    original_sequence: List[ScentItem]
    prior_rounds: List[FeedbackRound] = []
    latest_feedback: str = Field(min_length=1)
    session_id: Optional[str] = None


class FeedbackResponse(BaseModel):
    scent_sequence: List[ScentItem]
    justification: str
    changes_made: str
    pulse_sequence: List[ScentItem] = []
    session_id: str = ""

    @field_validator("scent_sequence")
    @classmethod
    def validate_total_duration(cls, value: List[ScentItem]):
        total = sum(item.scent_duration for item in value)
        if total != SEQUENCE_TOTAL_SECONDS:
            raise ValueError(
                f"Total duration must equal {SEQUENCE_TOTAL_SECONDS}, got {total}"
            )
        return value


class AcceptRequest(BaseModel):
    original_sentence: str = Field(min_length=1)
    final_sequence: List[ScentItem]
    feedback_rounds: List[FeedbackRound] = []
    session_id: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)

    @field_validator("final_sequence")
    @classmethod
    def validate_total_duration(cls, value: List[ScentItem]):
        total = sum(item.scent_duration for item in value)
        if total != SEQUENCE_TOTAL_SECONDS:
            raise ValueError(
                f"Total duration must equal {SEQUENCE_TOTAL_SECONDS}, got {total}"
            )
        return value


class AcceptResponse(BaseModel):
    success: bool = True
    example_id: str
    session_id: str = ""
    message: str = "Composition saved for future learning"


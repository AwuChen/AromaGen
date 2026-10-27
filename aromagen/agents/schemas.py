from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ValidationError, field_validator

from .settings import settings

log = logging.getLogger(__name__)

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
    ratio: float = Field(default=1.0, gt=0, le=1)


class ComposeResponse(BaseModel):
    scent_sequence: List[ScentItem]
    justification: str
    validated_sequence: List[ScentItem] = []
    removed_scents: List[str] = []
    validation_reasoning: str = ""
    compatibility_warnings: List[str] = []
    pulse_sequence: List[ScentItem] = []
    request_category: str = ""
    ensemble_stability: Optional[Dict[str, Any]] = None
    session_id: str = ""


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
    validated_sequence: List[ScentItem] = []
    removed_scents: List[str] = []
    validation_reasoning: str = ""
    compatibility_warnings: List[str] = []
    pulse_sequence: List[ScentItem] = []
    session_id: str = ""


class AcceptRequest(BaseModel):
    original_sentence: str = Field(min_length=1)
    final_sequence: List[ScentItem]
    feedback_rounds: List[FeedbackRound] = []
    session_id: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)


class ValidationResponse(BaseModel):
    # Only kept_scent_names is asked of the model -- removed is derived in code
    # as the complement, so the model can't produce a self-contradictory
    # response where the same name appears in both lists.
    kept_scent_names: List[str] = Field(min_length=1)
    reasoning: str


class ClassificationResponse(BaseModel):
    category: Literal["concrete", "abstract"]


class EnsembleValidationResponse(BaseModel):
    # Unlike ValidationResponse, an empty list is a legitimate outcome here --
    # the strong-consensus set may already fully cover the target, in which
    # case every moderate/weak candidate is correctly rejected.
    kept_scent_names: List[str] = []
    reasoning: str


class AcceptResponse(BaseModel):
    success: bool = True
    example_id: str
    session_id: str = ""
    message: str = "Composition saved for future learning"


class LogInteractionRequest(BaseModel):
    target_smell: str = Field(min_length=1)
    aromagen_ratio: str = Field(min_length=1)
    similarity: int = Field(ge=1, le=7)
    feedback: str = ""
    session_id: Optional[str] = None


class LogInteractionResponse(BaseModel):
    success: bool = True


class SimplexAnchor(BaseModel):
    token: str = Field(min_length=1, max_length=8)
    label: str = ""
    scent_sequence: List[ScentItem] = Field(min_length=1)


class SimplexInterpolateRequest(BaseModel):
    anchors: List[SimplexAnchor] = Field(min_length=3, max_length=3)
    weights: List[float] = Field(min_length=3, max_length=3)
    use_corpus_nearest: bool = False


class SimplexPointRequest(BaseModel):
    anchors: List[SimplexAnchor] = Field(min_length=3, max_length=3)
    point_x: float
    point_y: float
    use_corpus_nearest: bool = False


class SimplexPrepareAnchorsRequest(BaseModel):
    target: str = Field(min_length=1)
    corner_mode: Literal["preset", "cluster", "llm"] = "preset"
    neutral_labels: bool = False


class TriangleDirectionItem(BaseModel):
    short_label: str = Field(min_length=1, max_length=48)
    facet: str = Field(min_length=1)


class TriangleDirectionPlan(BaseModel):
    directions: List[TriangleDirectionItem] = Field(min_length=3, max_length=3)


class DevicePlayItem(BaseModel):
    scent_id: int = Field(ge=1, le=12)
    duration: float = Field(gt=0, le=60)


class DevicePlaySequenceRequest(BaseModel):
    sequence: List[DevicePlayItem] = Field(min_length=1)


class SimplexBlendResponse(BaseModel):
    weights: List[float]
    scent_sequence: List[ScentItem]
    validated_sequence: List[ScentItem] = []
    pulse_sequence: List[ScentItem] = []
    vector: Dict[str, float] = {}
    compatibility_warnings: List[str] = []
    corpus_match: Optional[Dict[str, Any]] = None
    source: Literal["blend", "corpus"] = "blend"


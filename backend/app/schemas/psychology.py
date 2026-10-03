"""Validated multi-label evidence and raw, uncalibrated model outputs."""
from typing import Annotated, Any
from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator, field_validator
from backend.app.config.context_config import MAX_MESSAGE_LENGTH
from backend.app.utils.psychology_labels import get_psychology_labels, validate_technique

class ManipulationScores(RootModel[dict[str, Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]]]):
    @model_validator(mode='after')
    def complete_taxonomy(self):
        if set(self.root) != set(get_psychology_labels()):
            raise ValueError('Scores must contain exactly the psychology taxonomy')
        return self

class PsychologyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str | None = Field(default=None, max_length=MAX_MESSAGE_LENGTH)
    @field_validator('message')
    @classmethod
    def trim_message(cls, value):
        return value.strip() or None if value is not None else None

class PsychologyResult(BaseModel):
    psychology_risk: float = Field(ge=0, le=100)
    scores: ManipulationScores
    rule_scores: ManipulationScores
    ml_probabilities: ManipulationScores | None
    thresholds: ManipulationScores
    detected_techniques: list[str]
    reason_codes: list[str] = Field(min_length=1)
    evidence: dict[str, Any]
    model_available: bool
    message_available: bool
    scores_kind: str = 'hybrid_evidence_not_calibrated_probabilities'
    @field_validator('detected_techniques')
    @classmethod
    def valid_techniques(cls, values):
        for value in values:
            validate_technique(value)
        return values

class PsychologyOverlapAdjustment(BaseModel):
    adjusted_psychology_risk: float = Field(ge=0, le=100)
    discount_factor: float = Field(ge=.5, le=1)
    overlapping_techniques: list[str]
    reason_code: str

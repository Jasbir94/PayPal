"""Preliminary risk API contracts reuse the Day 1 payment schema."""
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.transaction import Transaction, PaymentReason


class PreliminaryRiskRequest(Transaction):
    transaction_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    first_time_recipient: bool = False  # recalculated from server history
    payment_reason: PaymentReason = PaymentReason.other  # excluded from Day 2 predictors


class RiskComponent(BaseModel):
    score: float = Field(ge=0, le=100)
    ml_probability: float = Field(ge=0, le=1)
    rule_score: float = Field(ge=0, le=100)
    reasons: list[str] = Field(min_length=1)


class PreliminaryRiskResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    transaction_risk: float = Field(ge=0, le=100)
    recipient_risk: float = Field(ge=0, le=100)
    preliminary_risk: float = Field(ge=0, le=100)
    risk_level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    reasons: list[str] = Field(min_length=1)
    transaction_details: RiskComponent
    recipient_details: RiskComponent


from typing import Any
from pydantic import model_validator, field_validator
from backend.app.schemas.context import PaymentContext
from backend.app.config.context_config import MAX_MESSAGE_LENGTH
from backend.app.utils.scenario_labels import validate_scenario_label


class ContextualRiskRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    transaction: PreliminaryRiskRequest
    context: PaymentContext
    message: str | None = Field(default=None, max_length=MAX_MESSAGE_LENGTH)

    @field_validator('message')
    @classmethod
    def trim_message(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode='after')
    def unambiguous_message(self) -> 'ContextualRiskRequest':
        if self.message and self.context.user_message and self.message != self.context.user_message:
            raise ValueError('Provide one message source, or identical message/context.user_message values')
        return self


class EvidenceRiskComponent(RiskComponent):
    evidence: dict[str, float] = Field(default_factory=dict)


class ExplainedScore(BaseModel):
    score: float = Field(ge=0, le=100)
    reasons: list[str] = Field(min_length=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    context_available: bool | None = None


class ScenarioCandidate(BaseModel):
    scenario: str
    score: float = Field(ge=0, le=1)
    _valid_label = field_validator('scenario')(validate_scenario_label)


class ScenarioResult(BaseModel):
    type: str
    confidence: float = Field(ge=0, le=1)
    confidence_kind: str
    top_scenarios: list[ScenarioCandidate] = Field(min_length=1, max_length=3)
    reason_codes: list[str] = Field(min_length=1)
    evidence: dict[str, Any]
    _valid_type = field_validator('type')(validate_scenario_label)


from backend.app.schemas.psychology import PsychologyResult, PsychologyOverlapAdjustment


class ContextualRiskResponse(BaseModel):
    transaction_risk: EvidenceRiskComponent
    recipient_risk: EvidenceRiskComponent
    context_risk: ExplainedScore
    scenario: ScenarioResult
    scenario_risk: ExplainedScore
    psychology: PsychologyResult
    scenario_psychology_alignment: float = Field(ge=0, le=1)
    psychology_overlap_adjustment: PsychologyOverlapAdjustment
    extended_risk: float = Field(ge=0, le=100)
    graph_risk: dict[str, Any] | None = None
    grouped_scores: dict[str, float]
    overall_risk: float = Field(ge=0, le=100)
    fusion_policy: str
    overall_risk_level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    extended_risk_level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    extended_preliminary_risk: float = Field(ge=0, le=100)
    risk_level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    reason_codes: list[str] = Field(min_length=1)

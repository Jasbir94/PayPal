"""Request and response contracts for the final payment assessment."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.app.schemas.risk import PreliminaryRiskRequest
from backend.app.schemas.context import PaymentContext
from backend.app.config.context_config import MAX_MESSAGE_LENGTH

class AnalyzePaymentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    transaction: PreliminaryRiskRequest
    context: PaymentContext = Field(default_factory=PaymentContext)
    message: str | None = Field(default=None, max_length=MAX_MESSAGE_LENGTH)

    @model_validator(mode='after')
    def message_sources_match(self):
        if self.message and self.context.user_message and self.message != self.context.user_message:
            raise ValueError('Provide one message source, or identical message/context.user_message values')
        return self

class GroupAssessment(BaseModel):
    score: float | None = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    available: bool

class UserIntervention(BaseModel):
    level: int = Field(ge=0, le=4)
    type: str
    title: str
    message: str
    recommended_action: str

class FraudAssessment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    transaction_id: str
    app_scam_risk: float = Field(ge=0, le=100)
    calibrated_probability: float | None = Field(default=None, ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    risk_level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    likely_scam_scenario: str
    user_side_risk: GroupAssessment
    recipient_network_risk: GroupAssessment
    manipulation_risk: GroupAssessment
    detected_psychological_techniques: list[str]
    decision: str
    intervention: UserIntervention
    top_reasons: list[dict[str, Any]]
    protective_evidence: list[str]
    normalized_evidence: list[dict[str, Any]]
    missing_evidence: list[str]
    scenario_psychology_alignment: float = Field(ge=0, le=1)
    model_versions: dict[str, str]
    component_scores: dict[str, float | None]
    component_latency_ms: dict[str, float | None]
    reason_codes: list[str]
    latency_ms: float = Field(ge=0)

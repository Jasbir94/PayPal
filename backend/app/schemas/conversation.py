"""Bounded, ordered conversation input for cumulative manipulation analysis."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.app.schemas.risk import PreliminaryRiskRequest
from backend.app.schemas.context import PaymentContext
from backend.app.schemas.fraud_result import FraudAssessment
from backend.app.config.risk_config import (MAX_CONVERSATION_MESSAGES,
    MAX_CONVERSATION_MESSAGE_LENGTH, MAX_CONVERSATION_TOTAL_CHARS)

class ConversationMessage(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    speaker: Literal['other','user']
    text: str=Field(min_length=1,max_length=MAX_CONVERSATION_MESSAGE_LENGTH)
    payment_amount: float | None=Field(default=None,gt=0,allow_inf_nan=False)

class AnalyzeConversationRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    transaction: PreliminaryRiskRequest
    context: PaymentContext=Field(default_factory=PaymentContext)
    messages: list[ConversationMessage]=Field(min_length=1,max_length=MAX_CONVERSATION_MESSAGES)

    @model_validator(mode='after')
    def total_text_is_bounded(self):
        if sum(len(item.text) for item in self.messages)>MAX_CONVERSATION_TOTAL_CHARS:
            raise ValueError('Conversation text exceeds the total character limit')
        return self

class ConversationEvidence(BaseModel):
    other_message_count:int=Field(ge=0)
    user_message_count:int=Field(ge=0)
    detected_techniques:list[str]
    technique_scores:dict[str,float]
    conversation_psychology_risk:float=Field(ge=0,le=100)
    manipulation_progression_score:float=Field(ge=0,le=100)
    progression_stages:list[str]
    payment_escalation_ratio:float | None=Field(default=None,ge=0)
    normalization_applied:bool

class AnalyzeConversationResponse(BaseModel):
    assessment:FraudAssessment
    conversation_evidence:ConversationEvidence

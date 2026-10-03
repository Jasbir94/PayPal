"""Validated preliminary scoring endpoint; no training or disk reads per request."""
from fastapi import APIRouter, HTTPException, Request
from backend.app.schemas.risk import PreliminaryRiskRequest, PreliminaryRiskResponse, ContextualRiskRequest, ContextualRiskResponse
from backend.app.schemas.fraud_result import AnalyzePaymentRequest, FraudAssessment
from backend.app.services.fraud_engine import FraudEngine
from backend.app.schemas.conversation import AnalyzeConversationRequest, AnalyzeConversationResponse
from backend.app.services.conversation_service import ConversationService

router = APIRouter(prefix='/api/v1/risk', tags=['preliminary risk'])
final_router = APIRouter(prefix='/api/v1', tags=['final assessment'])


@router.post('/preliminary', response_model=PreliminaryRiskResponse)
def preliminary_risk(payment: PreliminaryRiskRequest, request: Request) -> dict:
    service = getattr(request.app.state, 'risk_service', None)
    if service is None:
        raise HTTPException(status_code=503, detail=getattr(request.app.state, 'risk_error',
            'Risk models unavailable. Run both Day 2 training commands and restart the service.'))
    try:
        return service.score(payment.model_dump())
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post('/contextual', response_model=ContextualRiskResponse)
def contextual_risk(payment: ContextualRiskRequest, request: Request) -> dict:
    service = getattr(request.app.state, 'risk_service', None)
    if service is None:
        raise HTTPException(status_code=503, detail=getattr(request.app.state, 'risk_error', 'Risk engine unavailable'))
    try:
        return service.score_contextual(payment.transaction.model_dump(), payment.context, payment.message)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@final_router.post('/analyze-payment', response_model=FraudAssessment)
def analyze_payment(payment: AnalyzePaymentRequest, request: Request) -> dict:
    """Return the final grouped, explainable APP scam assessment."""
    risk_service = getattr(request.app.state, 'risk_service', None)
    if risk_service is None:
        raise HTTPException(status_code=503, detail=getattr(request.app.state, 'risk_error', 'Risk engine unavailable'))
    engine = getattr(request.app.state, 'fraud_engine', None)
    if engine is None:
        engine = FraudEngine(risk_service)
        request.app.state.fraud_engine = engine
    try:
        return engine.analyze_payment(payment.transaction.model_dump(), payment.context, payment.message)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@final_router.post('/analyze-conversation', response_model=AnalyzeConversationResponse)
def analyze_conversation(payment: AnalyzeConversationRequest, request: Request) -> dict:
    """Analyze a bounded ordered transcript and return one payment assessment."""
    risk_service=getattr(request.app.state,'risk_service',None)
    if risk_service is None:
        raise HTTPException(status_code=503,detail=getattr(request.app.state,'risk_error','Risk engine unavailable'))
    conversation_service=getattr(request.app.state,'conversation_service',None)
    if conversation_service is None:
        conversation_service=ConversationService(risk_service.psychology)
        request.app.state.conversation_service=conversation_service
    evidence=conversation_service.analyze(payment.messages,payment.transaction.amount)
    engine=getattr(request.app.state,'fraud_engine',None)
    if engine is None:
        engine=FraudEngine(risk_service)
        request.app.state.fraud_engine=engine
    try:
        context=payment.context.model_copy(update={'user_message':None})
        assessment=engine.analyze_payment(payment.transaction.model_dump(),context,evidence['analysis_message'])
        public={key:value for key,value in evidence.items() if key not in ('analysis_message','turn_evidence')}
        return {'assessment':assessment,'conversation_evidence':public}
    except KeyError as error:
        raise HTTPException(status_code=404,detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422,detail=str(error)) from error
    except Exception as error:
        from logging import getLogger
        getLogger(__name__).error('conversation_analysis_failed type=%s',type(error).__name__)
        raise HTTPException(status_code=503,detail='Conversation analysis is temporarily unavailable.') from None

"""FastAPI service with startup-cached data and trained Day 2 baselines."""
from contextlib import asynccontextmanager
import logging
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.risk_routes import router, final_router
from backend.app.database.repository import DataRepository
from backend.app.models.transaction_model import TransactionModel
from backend.app.models.recipient_model import RecipientModel
from backend.app.services.transaction_service import TransactionService
from backend.app.services.recipient_service import RecipientService
from backend.app.services.risk_service import RiskService
from backend.app.models.scenario_model import ScenarioModel
from backend.app.services.scenario_service import ScenarioService
from backend.app.models.psychology_model import PsychologyModel
from backend.app.services.psychology_service import PsychologyService
from backend.app.api.psychology_routes import router as psychology_router
from backend.app.api.graph_routes import router as graph_router
from backend.app.graph.data import load_graph_builder
from backend.app.models.graph_model import GraphModel
from backend.app.services.graph_service import GraphService
from backend.app.services.conversation_service import ConversationService
from backend.app.security.request_guard import RequestGuardMiddleware
from backend.app.config.risk_config import (MAX_REQUEST_BODY_BYTES,API_RATE_LIMIT_REQUESTS,
    API_RATE_LIMIT_WINDOW_SECONDS,PROJECT_ROOT)
from backend.app.api.simulation_routes import router as simulation_router
from backend.app.simulation.payment_simulator import PaymentSimulator
from backend.app.api.day9_routes import feedback_router,review_router,monitor_router,research_router
from backend.app.feedback.service import FeedbackService
from backend.app.review.review_service import ReviewService
from backend.app.api.conversation_routes import router as conversation_router
from backend.app.api.banking_routes import router as banking_router
from backend.app.rag.knowledge_store import HybridRetriever
from backend.app.conversation.payment_conversation_agent import PaymentConversationAgent
from backend.app.services.demo_banking_service import DemoBankingService


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.risk_service = None
    application.state.graph_service = None
    psychology = PsychologyService()
    try:
        psychology = PsychologyService(PsychologyModel())
    except (OSError, ValueError) as error:
        logging.getLogger(__name__).warning('Psychology model unavailable; rules remain active: %s', error)
    application.state.psychology_service = psychology
    application.state.psychology_model_available = psychology.model is not None
    try:
        repository = DataRepository.load()
        scenario = ScenarioService()
        try:
            scenario = ScenarioService(ScenarioModel())
        except (OSError, ValueError) as error:
            logging.getLogger(__name__).warning('Scenario text model unavailable; structured rules remain active: %s', error)
        application.state.scenario_text_available = scenario.model is not None
        graph_model = None
        try:
            graph_model = GraphModel()
        except (OSError, ValueError) as error:
            logging.getLogger(__name__).warning('Graph model unavailable; interpretable rules remain active: %s', error)
        graph = GraphService(load_graph_builder(repository), graph_model)
        application.state.graph_service = graph
        application.state.risk_service = RiskService(repository,
            TransactionService(TransactionModel()), RecipientService(RecipientModel(), repository), scenario, psychology, graph)
        application.state.conversation_service = ConversationService(psychology)
        try:
            application.state.feedback_service=FeedbackService()
            application.state.review_service=ReviewService(application.state.feedback_service.repository)
        except OSError as error:
            application.state.feedback_service=None
            application.state.review_service=None
            logging.getLogger(__name__).warning('Research feedback persistence unavailable: %s',type(error).__name__)
        application.state.payment_simulator = PaymentSimulator(application.state.risk_service,
            application.state.feedback_service,application.state.review_service)
        simulator=application.state.payment_simulator
        senders=[{'alias':alias,'account_id':item['account_id'],'display_name':item['display_name']}
            for alias,item in simulator._scenario_data['senders'].items()]
        application.state.demo_banking_service=DemoBankingService(senders,simulator.catalog()['recipients'])
        simulator.banking_service=application.state.demo_banking_service
        application.state.knowledge_retriever=HybridRetriever()
        application.state.payment_conversation_agent=PaymentConversationAgent(
            application.state.payment_simulator,application.state.knowledge_retriever,
            application.state.demo_banking_service)
    except (OSError, ValueError) as error:
        application.state.risk_error = f'Risk engine unavailable: {error}. Run both training commands and restart.'
        logging.getLogger(__name__).warning(application.state.risk_error)
    yield


def create_app() -> FastAPI:
    application = FastAPI(title='APP Shield', version='0.4.0', lifespan=lifespan)
    application.include_router(router)
    application.include_router(final_router)
    application.include_router(psychology_router)
    application.include_router(graph_router)
    application.include_router(simulation_router)
    application.include_router(conversation_router)
    application.include_router(banking_router)
    application.include_router(feedback_router)
    application.include_router(review_router)
    application.include_router(monitor_router)
    application.include_router(research_router)
    application.add_middleware(RequestGuardMiddleware,max_body_bytes=MAX_REQUEST_BODY_BYTES,
        rate_limit=API_RATE_LIMIT_REQUESTS,window_seconds=API_RATE_LIMIT_WINDOW_SECONDS)
    allowed_origins=[item.strip() for item in os.getenv('APP_SHIELD_CORS_ORIGINS','').split(',') if item.strip()]
    application.add_middleware(CORSMiddleware,allow_origins=allowed_origins,allow_credentials=False,
        allow_methods=['GET','POST'],allow_headers=['Content-Type','Authorization'])
    application.add_api_route('/', root, methods=['GET'])
    application.add_api_route('/health', health, methods=['GET'])
    application.add_api_route('/ready', ready, methods=['GET'])
    application.add_api_route('/api/v1/model-info', model_info, methods=['GET'], tags=['health'])
    @application.exception_handler(Exception)
    async def safe_unexpected_error(_request, error):
        logging.getLogger(__name__).error('api_unhandled_exception type=%s',type(error).__name__)
        return JSONResponse({'detail':'The request could not be completed.'},status_code=500)
    return application


def root() -> dict[str, str]:
    return {'project': 'APP Shield', 'status': 'running'}


def health() -> dict[str, str]:
    """Liveness only; readiness is exposed separately."""
    return {'status': 'healthy'}


def ready(request: Request):
    from fastapi.responses import JSONResponse
    available = getattr(request.app.state, 'risk_service', None) is not None
    return JSONResponse({'status': 'ready' if available else 'unavailable'}, status_code=200 if available else 503)


def model_info(request: Request) -> dict:
    """Expose safe component availability and contract versions, never local paths."""
    risk_available = getattr(request.app.state, 'risk_service', None) is not None
    registry_path=PROJECT_ROOT/'models'/'registry'/'registry.json'
    active_fusion='unavailable'
    try:
        import json
        with open(registry_path,encoding='utf-8') as handle:
            active_fusion=json.load(handle)['models']['fusion']['active_version']
    except (OSError,KeyError,ValueError,TypeError):
        active_fusion='fusion-logistic-platt-v1'
    return {'api_version': request.app.version, 'policy_version': 'day9-v1',
        'active_fusion_version':active_fusion,
        'components': {
            'transaction': {'available': risk_available},
            'recipient': {'available': risk_available},
            'scenario_text': {'available': bool(getattr(request.app.state, 'scenario_text_available', False))},
            'psychology_text': {'available': bool(getattr(request.app.state, 'psychology_model_available', False))},
            'graph': {'available': getattr(request.app.state, 'graph_service', None) is not None},
            'payment_conversation': {'available':getattr(request.app.state,'payment_conversation_agent',None) is not None},
            'local_rag': {'available':getattr(request.app.state,'knowledge_retriever',None) is not None},
        }, 'score_semantics': 'evidence index; not a calibrated probability'}


app = create_app()

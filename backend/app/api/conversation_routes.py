"""Structured chat API; the chat model cannot independently authorize payment actions."""
from fastapi import APIRouter,Header,HTTPException,Request
from backend.app.conversation.session_schemas import StartChatSession,ChatMessage

router=APIRouter(prefix='/api/v1/chat',tags=['payment conversation'])

def agent(request):
    value=getattr(request.app.state,'payment_conversation_agent',None)
    if value is None:raise HTTPException(503,'Conversational payment safety is unavailable. No payment was made.')
    return value

def owner(request,authorization):
    banking=getattr(request.app.state,'demo_banking_service',None)
    if banking is None:raise HTTPException(503,'Simulated account sessions are unavailable.')
    token=authorization.split(' ',1)[1].strip() if authorization and authorization.lower().startswith('bearer ') else None
    return banking.resolve_token(token)

@router.get('/health')
def chat_health(request:Request):
    value=getattr(request.app.state,'payment_conversation_agent',None)
    return {'available':value is not None,'session_storage':'process-memory demo only',
        'retrieval':'local source-attributed hybrid search' if value else 'unavailable',
        'language_model':'not configured; evidence-bound templates are used'}

@router.post('/sessions')
def start_session(payload:StartChatSession,request:Request,authorization:str|None=Header(default=None)):
    selected=agent(request);account=owner(request,authorization)
    return selected.idempotent_request(scope='start',owner=account,key=payload.idempotency_key,
        payload={'message':payload.message},operation=lambda:selected.start(payload.message,account))

@router.get('/sessions/{session_id}')
def get_session(session_id:str,request:Request,authorization:str|None=Header(default=None)):
    return agent(request).get(session_id,owner(request,authorization))

@router.post('/sessions/{session_id}/messages')
def send_message(session_id:str,payload:ChatMessage,request:Request,authorization:str|None=Header(default=None)):
    selected=agent(request);account=owner(request,authorization)
    return selected.idempotent_request(scope=f'message:{session_id}',owner=account,
        key=payload.idempotency_key,payload={'message':payload.message},
        operation=lambda:selected.message(session_id,payload.message,account))

@router.post('/sessions/{session_id}/actions/{action}')
def payment_action(session_id:str,action:str,request:Request,authorization:str|None=Header(default=None)):
    return agent(request).action(session_id,action,owner(request,authorization))

"""Authenticated demo-wallet sessions and ledger-backed read operations."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from zoneinfo import ZoneInfo

router=APIRouter(prefix='/api/v1/banking',tags=['simulated banking'])

class DemoSessionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    account_alias:str=Field(min_length=1,max_length=16)

def banking(request:Request):
    service=getattr(request.app.state,'demo_banking_service',None)
    if service is None:raise HTTPException(503,'Simulated banking is unavailable.')
    return service

def authenticated_account(request:Request,authorization:str|None=Header(default=None)):
    token=authorization.split(' ',1)[1].strip() if authorization and authorization.lower().startswith('bearer ') else None
    return banking(request).resolve_token(token)

def period_bounds(period):
    if period not in ('today','week'):raise HTTPException(422,'Supported transaction periods are today and week.')
    local=datetime.now(timezone.utc).astimezone(ZoneInfo('Asia/Kolkata'))
    start=local.replace(hour=0,minute=0,second=0,microsecond=0)
    if period=='week':start=(start-timedelta(days=start.weekday()))
    return start,start+timedelta(days=1 if period=='today' else 7)

@router.get('/profiles')
def demo_profiles(request:Request):
    return {'environment':'SIMULATED DEMO','profiles':banking(request).profiles()}

@router.post('/demo-sessions')
def create_demo_session(payload:DemoSessionRequest,request:Request):
    return banking(request).create_demo_session(payload.account_alias)

@router.get('/session')
def current_session(account=Depends(authenticated_account)):
    return {'account':{'alias':account['account_alias'],'display_name':account['display_name']},
        'environment':'SIMULATED DEMO ACCOUNT'}

@router.get('/balance')
def get_balance(request:Request,account=Depends(authenticated_account)):
    return {'account':{'alias':account['account_alias'],'display_name':account['display_name']},
        **banking(request).balance(account['account_id'])}

@router.get('/transactions')
def get_transactions(request:Request,limit:int=Query(5,ge=1,le=100),direction:str|None=None,
        payee:str|None=None,period:str|None=None,largest:bool=False,account=Depends(authenticated_account)):
    direction=direction.upper() if direction else None
    if direction not in (None,'DEBIT','CREDIT'):raise HTTPException(422,'Direction must be debit or credit.')
    start,end=period_bounds(period) if period else (None,None)
    result=banking(request).transactions(account['account_id'],limit=limit,direction=direction,
        payee=payee,start=start,end=end,largest=largest)
    return {'account':{'alias':account['account_alias'],'display_name':account['display_name']},**result}

@router.get('/transactions/{transaction_id}')
def get_transaction(transaction_id:str,request:Request,account=Depends(authenticated_account)):
    return banking(request).transaction(account['account_id'],transaction_id)

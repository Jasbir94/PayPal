"""Pre-payment simulation API; all operations remain local and simulated."""
from fastapi import APIRouter, HTTPException, Request
from backend.app.simulation.schemas import (CreatePaymentAttempt, AnalyzePaymentAttempt,
    ContinuePaymentAttempt, VerifyPaymentAttempt)

router=APIRouter(prefix='/api/v1/simulated-payments',tags=['simulated payments'])

def simulator(request:Request):
    service=getattr(request.app.state,'payment_simulator',None)
    if service is None: raise HTTPException(503,'Payment simulation is unavailable; no payment was executed.')
    return service

@router.get('/accounts')
def get_simulated_accounts(request:Request): return simulator(request).catalog()

@router.get('/scenarios')
def get_demo_scenarios(request:Request): return {'scenarios':simulator(request).scenarios()}

@router.get('/scenarios/{scenario_id}')
def get_demo_scenario(scenario_id:str,request:Request): return simulator(request).scenario(scenario_id)

@router.post('')
def create_payment_attempt(payload:CreatePaymentAttempt,request:Request):
    result,created=simulator(request).create(payload)
    return {**result,'created':created}

@router.get('/analytics')
def get_simulation_analytics(request:Request): return simulator(request).analytics()

@router.get('/analyst/analytics')
def get_analyst_analytics(request:Request): return simulator(request).analytics(analyst=True)

@router.get('/{attempt_id}/analyst')
def get_analyst_assessment(attempt_id:str,request:Request): return simulator(request).analyst(attempt_id)

@router.get('/{attempt_id}/network')
def get_analyst_network(attempt_id:str,request:Request): return simulator(request).graph_neighborhood(attempt_id)

@router.post('/{attempt_id}/ablation')
def rerun_context_ablation(attempt_id:str,request:Request):
    return simulator(request).ablate_context(attempt_id)

@router.post('/{attempt_id}/analyze')
def analyze_payment_attempt(attempt_id:str,payload:AnalyzePaymentAttempt,request:Request):
    return simulator(request).analyze(attempt_id,payload)

@router.post('/{attempt_id}/continue')
def continue_payment_attempt(attempt_id:str,payload:ContinuePaymentAttempt,request:Request):
    return simulator(request).continue_payment(attempt_id,payload.acknowledged_warning)

@router.post('/{attempt_id}/verify')
def verify_payment_attempt(attempt_id:str,payload:VerifyPaymentAttempt,request:Request):
    return simulator(request).verify(attempt_id,payload.action)

@router.post('/{attempt_id}/cancel')
def cancel_payment_attempt(attempt_id:str,request:Request): return simulator(request).cancel(attempt_id)

@router.get('/{attempt_id}')
def get_payment_attempt(attempt_id:str,request:Request): return simulator(request).get(attempt_id)

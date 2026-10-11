import pandas as pd
import pytest
from fastapi import HTTPException
from threading import RLock

from backend.app.fusion.evidence_consistency_engine import (
    build_evidence_records, compare_claims, merge_reported_answer,
)
from backend.app.fusion.protective_evidence import assess_protective_evidence
from backend.app.conversation.payment_conversation_agent import PaymentConversationAgent
from backend.app.simulation.payment_simulator import PaymentSimulator


def test_unrecorded_relationship_is_uncertain_not_deception():
    result = compare_claims(payment_id='p-1',
        context={'user_message':'I paid this recipient before; this is my regular landlord.'},
        history=pd.DataFrame(columns=['timestamp']), backend_history_available=True)
    assert result[0]['code'] == 'RELATIONSHIP_NOT_VERIFIED'
    assert 'does not prove deception' in result[0]['detail']


def test_repeated_monthly_history_supports_relationship_without_verifying_identity():
    history=pd.DataFrame({'timestamp':pd.date_range('2025-01-01',periods=12,freq='MS',tz='UTC')})
    result=compare_claims(payment_id='p-2',context={'user_message':'This is my regular landlord.'},
        history=history)
    assert result[0]['code']=='HISTORICAL_RELATIONSHIP_SUPPORTED'
    assert 'not recipient identity' in result[0]['detail']


def test_authority_claim_stays_unverified_without_authorized_identity_service():
    result=compare_claims(payment_id='p-3',context={'user_message':'This account belongs to the police department.'},
        history=pd.DataFrame(columns=['timestamp']))
    assert result==[{'code':'IDENTITY_UNVERIFIED',
        'detail':'No authorized identity-verification source is connected; names or customer reports do not verify an official identity.'}]


def test_provenance_ledger_marks_user_reports_and_trusted_references_separately():
    records=build_evidence_records(payment_id='p-4',
        transaction={'amount':3500,'receiver_id':'R1','sender_id':'U1'},
        context={'urgent_payment_requested':True,'user_message':'An officer told me to pay now.'},
        history=pd.DataFrame(columns=['timestamp']),
        assessment={'decision':'STEP_UP_VERIFICATION','app_scam_risk':64,'confidence':.7},
        trusted_references=[{'source_reference':'https://rbi.example/guidance','title':'RBI guidance'}])
    assert {item['source_type'] for item in records}=={
        'VERIFIED_BACKEND','USER_REPORTED','UNVERIFIED_EXTERNAL','TRUSTED_REFERENCE','MODEL_INFERRED'}
    assert all({'evidence_id','source_type','source_reference','timestamp','confidence',
        'verification_status','payment_id','supported_interpretation'}<=item.keys() for item in records)
    assert all(item['payment_id']=='p-4' for item in records)
    assert all(item['verification_status']!='verified' for item in records if item['source_type']=='USER_REPORTED')


def test_later_denial_does_not_erase_earlier_pressure_report():
    context={'urgent_payment_requested':True}
    effective,conflict=merge_reported_answer(context,'urgent_payment_requested',False)
    assert effective is True
    assert context['urgent_payment_requested'] is True
    assert conflict in context['reported_contradictions'][0]


def test_chat_idempotency_replay_returns_original_result_and_rejects_key_reuse():
    agent=PaymentConversationAgent.__new__(PaymentConversationAgent)
    agent._lock=RLock();agent._request_cache={}
    owner={'account_id':'demo-account'};calls=[]
    operation=lambda:(calls.append('called') or {'session_id':'session-1'})
    first=agent.idempotent_request(scope='start',owner=owner,key='phase15-key-001',
        payload={'message':'Send INR 500'},operation=operation)
    replay=agent.idempotent_request(scope='start',owner=owner,key='phase15-key-001',
        payload={'message':'Send INR 500'},operation=lambda:pytest.fail('replay re-executed'))
    assert first==replay=={'session_id':'session-1'}
    assert calls==['called']
    with pytest.raises(HTTPException) as error:
        agent.idempotent_request(scope='start',owner=owner,key='phase15-key-001',
            payload={'message':'Send INR 50000'},operation=operation)
    assert error.value.status_code==409


def test_user_reported_absence_cannot_subtract_independent_protective_evidence():
    transaction={'evidence':{'recipient_seen_before':True,'prior_payments_to_recipient':4,
        'baseline_available':True,'amount_ratio':1.0}}
    recipient={'evidence':{'account_age_days':800}}
    empty=assess_protective_evidence(transaction,recipient,{'available':False,'evidence':{}})
    reassured=assess_protective_evidence(transaction,recipient,{'available':True,'evidence':{
        'contacted_by_unknown_person':False,'urgent_payment_requested':False,
        'threatened_consequences':False,'claimed_authority':False,'requested_secrecy':False,
        'asked_to_install_remote_access':False}})
    assert reassured==empty


def _simulator_with_attempt(state):
    simulator=PaymentSimulator.__new__(PaymentSimulator)
    simulator._lock=RLock()
    attempt={'payment_attempt_id':'phase15-attempt','state':state,
        'sender_alias':'U101','sender_name':'Demo sender','recipient_alias':'R201',
        'recipient_id':'account-2','recipient_name':'Demo recipient','sender_id':'account-1',
        'amount':500.0,'currency':'INR','payment_reason':'friend','payment_type':'upi',
        'note':'','created_at':'2026-01-01T00:00:00+00:00','context_questions':[],
        'assessment':{'decision':'STEP_UP_VERIFICATION','intervention':None,'top_reasons':[],
            'protective_evidence':[]},'user_action':None,'simulated_status':'NOT_EXECUTED',
        'verified':False,'verification_claimed':False,'evidence_records':[],
        'ledger_receipt':None,'wallet_account_id':None,'payment_detail_version':1,
        'payment_fingerprint':None,'assessment_fingerprint':None}
    attempt['payment_fingerprint']=simulator._payment_fingerprint(attempt)
    simulator._attempts={attempt['payment_attempt_id']:attempt}
    return simulator,attempt


def test_user_click_cannot_satisfy_backend_verification_requirement():
    simulator,attempt=_simulator_with_attempt('VERIFICATION_REQUIRED')
    attempt_id=attempt['payment_attempt_id']
    result=simulator.verify(attempt_id,'verified_independently')
    assert result['state']=='VERIFICATION_REQUIRED'
    assert result['verification_claimed'] is True
    assert attempt['verified'] is False
    assert attempt['user_action']=='USER_REPORTED_INDEPENDENT_VERIFICATION'
    with pytest.raises(HTTPException):
        simulator.continue_payment(attempt_id,True)
    assert simulator.get(attempt_id)['simulated_status']=='NOT_EXECUTED'


def test_payment_detail_mutation_invalidates_prior_assessment_before_settlement():
    simulator,attempt=_simulator_with_attempt('READY')
    attempt_id=attempt['payment_attempt_id']
    attempt['assessment']['decision']='ALLOW'
    attempt['assessment_fingerprint']=attempt['payment_fingerprint']
    original_version=attempt['payment_detail_version']
    attempt['amount']=50000
    with pytest.raises(HTTPException) as error:
        simulator.continue_payment(attempt_id,True)
    assert error.value.status_code==409
    assert attempt['state']=='ERROR'
    assert attempt['simulated_status']=='NOT_EXECUTED'
    assert attempt['payment_detail_version']==original_version

\n
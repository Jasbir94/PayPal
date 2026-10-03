from datetime import datetime, timezone
from backend.app.services.fraud_engine import FraudEngine
from backend.app.schemas.context import PaymentContext
from backend.app.schemas.fraud_result import FraudAssessment

class FakeRiskService:
    def score_contextual(self, transaction, context, message):
        return {
          'transaction_risk':{'score':15,'reasons':['within_expected_transaction_pattern'],'evidence':{'baseline_available':1,'amount_ratio':1.1,'first_time_recipient':0,'recipient_seen_before':1}},
          'recipient_risk':{'score':10,'reasons':['no_recipient_rule_signals'],'evidence':{'history_count':5,'account_age_days':900}},
          'context_risk':{'score':0,'reasons':['no_reported_context_risk_signals'],'evidence':{},'context_available':False},
          'scenario':{'type':'normal_or_unknown','confidence':.8,'reason_codes':['normal_or_unknown_scenario'],'evidence':{'message_available':False}},
          'scenario_risk':{'score':0,'reasons':['normal_or_unknown_scenario'],'evidence':{}},
          'psychology':{'psychology_risk':0,'detected_techniques':[],'reason_codes':['psychology_message_unavailable'],'message_available':False,'model_available':False,'evidence':{}},
          'scenario_psychology_alignment':0,
          'psychology_overlap_adjustment':{'adjusted_psychology_risk':0,'discount_factor':1,'overlapping_techniques':[]},
          'graph_risk':None,
        }

def test_full_engine_returns_schema_valid_result_and_protective_evidence():
    payment={'transaction_id':'T1','sender_id':'A1','receiver_id':'A2','amount':100,
        'timestamp':datetime(2026,1,1,tzinfo=timezone.utc),'device_id':'D1','payment_type':'upi',
        'first_time_recipient':False,'payment_reason':'family'}
    result=FraudEngine(FakeRiskService()).analyze_payment(payment,PaymentContext())
    validated=FraudAssessment.model_validate(result)
    assert 0<=validated.app_scam_risk<=100
    assert 0<=validated.confidence<=1
    assert validated.user_side_risk.available
    assert validated.recipient_network_risk.available

from fastapi.testclient import TestClient
from backend.app.main import app

def create_attempt(client,key='create-day8-test-001'):
    return client.post('/api/v1/simulated-payments',json={
      'sender_alias':'U101','recipient_alias':'R203','amount':3500,
      'payment_reason':'government','payment_type':'upi','idempotency_key':key})

def test_accounts_scenarios_and_pre_payment_analysis_use_actual_backend():
    with TestClient(app) as client:
        accounts=client.get('/api/v1/simulated-payments/accounts')
        scenarios=client.get('/api/v1/simulated-payments/scenarios')
        assert accounts.status_code==200
        assert accounts.json()['environment'].startswith('SIMULATED PAYMENT')
        assert len(scenarios.json()['scenarios'])>=10
        assert all('is_known_mule' not in str(row) and 'is_suspicious' not in str(row)
                   for row in accounts.json()['recipients'])
        created=create_attempt(client)
        assert created.status_code==200
        attempt_id=created.json()['payment_attempt_id']
        assert created.json()['state']=='DRAFT'
        first=client.post(f'/api/v1/simulated-payments/{attempt_id}/analyze',json={})
        assert first.status_code==200
        assert first.json()['payment']['state'] in ('CONTEXT_REQUIRED','WARNING','VERIFICATION_REQUIRED','READY','SIMULATED_HELD')
        assert first.json()['payment']['simulated_status']=='NOT_EXECUTED'

def test_creation_idempotency_and_no_automatic_payment_execution():
    with TestClient(app) as client:
        one=create_attempt(client,'same-idempotency-key-001')
        two=create_attempt(client,'same-idempotency-key-001')
        assert one.status_code==two.status_code==200
        assert one.json()['payment_attempt_id']==two.json()['payment_attempt_id']
        assert one.json()['created'] is True
        assert two.json()['created'] is False
        assert two.json()['simulated_status']=='NOT_EXECUTED'

def test_idempotency_key_cannot_be_reused_for_a_different_payment():
    with TestClient(app) as client:
        first=create_attempt(client,'reused-different-payload-001')
        assert first.status_code==200
        different=client.post('/api/v1/simulated-payments',json={
          'sender_alias':'U101','recipient_alias':'R203','amount':9999,
          'payment_reason':'government','payment_type':'upi',
          'idempotency_key':'reused-different-payload-001'})
        assert different.status_code==409

def test_sensitive_credentials_are_rejected_and_duplicate_analysis_is_blocked():
    with TestClient(app) as client:
        attempt=create_attempt(client,'sensitive-idempotency-key-001').json()['payment_attempt_id']
        bad=client.post(f'/api/v1/simulated-payments/{attempt}/analyze',json={
          'context':{'user_message':'My OTP: 123456'}})
        assert bad.status_code==422
        assert client.get(f'/api/v1/simulated-payments/{attempt}').json()['state']=='DRAFT'
        first=client.post(f'/api/v1/simulated-payments/{attempt}/analyze',json={})
        assert first.status_code==200
        if first.json()['context_required']:
            second=client.post(f'/api/v1/simulated-payments/{attempt}/analyze',json={
              'context':{'contacted_by_unknown_person':False}})
            assert second.status_code==200
        repeated=client.post(f'/api/v1/simulated-payments/{attempt}/analyze',json={})
        assert repeated.status_code==409

def test_cancel_records_simulated_action_without_completing_payment():
    with TestClient(app) as client:
        attempt=create_attempt(client,'cancel-idempotency-key-001').json()['payment_attempt_id']
        client.post(f'/api/v1/simulated-payments/{attempt}/analyze',json={})
        cancelled=client.post(f'/api/v1/simulated-payments/{attempt}/cancel')
        assert cancelled.status_code==200
        assert cancelled.json()['state']=='CANCELLED'
        assert cancelled.json()['simulated_status']=='CANCELLED'

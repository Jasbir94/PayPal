from fastapi.testclient import TestClient
from backend.app.main import app


def test_flagship_runs_real_engine_and_returns_scenario_matched_intervention():
    with TestClient(app) as client:
        preset=client.get('/api/v1/simulated-payments/scenarios/government_impersonation').json()
        created=client.post('/api/v1/simulated-payments',json={
          'sender_alias':preset['sender_alias'],'recipient_alias':preset['recipient_alias'],
          'amount':preset['amount'],'payment_reason':preset['payment_reason'],'payment_type':'upi',
          'idempotency_key':'flagship-real-engine-test-001'}).json()
        result=client.post(f"/api/v1/simulated-payments/{created['payment_attempt_id']}/analyze",json={
          'context':preset['context'],'messages':preset['messages']})
        assert result.status_code==200
        payment=result.json()['payment']
        assert payment['decision'] in {'ALLOW_WITH_WARNING','WARN_AND_REVIEW','STEP_UP_VERIFICATION','BLOCK_AND_ESCALATE'}
        assert payment['intervention']['type']=='GOVERNMENT_IMPERSONATION_WARNING'
        assert payment['intervention']['level']>=3
        assert 'app_scam_risk' not in payment
        analyst=client.get(f"/api/v1/simulated-payments/{created['payment_attempt_id']}/analyst").json()
        assessment=analyst['attempt']['assessment']
        assert assessment['app_scam_risk']>assessment['component_scores']['transaction']
        assert all('new recipient authority scam pattern' not in item.lower()
                   for item in payment['top_reasons'])
        assert analyst['attempt']['contextual_result']['scenario']['type']=='government_impersonation'


def test_backend_unavailable_fails_closed_for_simulated_payment():
    with TestClient(app) as client:
        original=app.state.payment_simulator
        app.state.payment_simulator=None
        try:
            response=client.post('/api/v1/simulated-payments',json={
              'sender_alias':'U101','recipient_alias':'R201','amount':100,
              'idempotency_key':'backend-unavailable-test-001'})
            assert response.status_code==503
            assert 'no payment was executed' in response.json()['detail']
        finally:
            app.state.payment_simulator=original

from fastapi.testclient import TestClient
from backend.app.main import app


def test_warning_requires_acknowledgement_and_records_user_action():
    with TestClient(app) as client:
        scenario=client.get('/api/v1/simulated-payments/scenarios/normal_friend').json()
        created=client.post('/api/v1/simulated-payments',json={
          'sender_alias':scenario['sender_alias'],'recipient_alias':scenario['recipient_alias'],
          'amount':scenario['amount'],'payment_reason':scenario['payment_reason'],'payment_type':'upi',
          'idempotency_key':'warning-ack-test-001'}).json()
        attempt_id=created['payment_attempt_id']
        scored=client.post(f'/api/v1/simulated-payments/{attempt_id}/analyze',json={'context':{},'messages':[]})
        assert scored.status_code==200
        state=scored.json()['payment']['state']
        if state=='WARNING':
            blocked=client.post(f'/api/v1/simulated-payments/{attempt_id}/continue',json={})
            assert blocked.status_code==422
            completed=client.post(f'/api/v1/simulated-payments/{attempt_id}/continue',json={'acknowledged_warning':True})
        else:
            assert state=='READY'
            completed=client.post(f'/api/v1/simulated-payments/{attempt_id}/continue',json={})
        assert completed.status_code==200
        assert completed.json()['state']=='SIMULATED_COMPLETED'
        assert completed.json()['simulated_status']=='SIMULATED_SUCCESS'
        duplicate=client.post(f'/api/v1/simulated-payments/{attempt_id}/continue',json={'acknowledged_warning':True})
        assert duplicate.status_code==409

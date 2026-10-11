from uuid import uuid4
from fastapi.testclient import TestClient
from backend.app.main import app


def _create(client,scenario,key):
    return client.post('/api/v1/simulated-payments',json={
        'sender_alias':scenario['sender_alias'],'recipient_alias':scenario['recipient_alias'],
        'amount':scenario['amount'],'payment_reason':scenario['payment_reason'],
        'payment_type':'upi','note':'Phase 11 flow test','idempotency_key':key}).json()


def test_flagship_government_case_context_warning_cancel_keeps_label_unknown():
    with TestClient(app) as client:
        scenario=client.get('/api/v1/simulated-payments/scenarios/government_impersonation').json()
        created=_create(client,scenario,'phase11-government-'+uuid4().hex[:12])
        attempt_id=created['payment_attempt_id']

        first=client.post(f'/api/v1/simulated-payments/{attempt_id}/analyze',json={})
        assert first.status_code==200
        assert first.json()['context_required'] is True
        assert 1<=len(first.json()['context_questions'])<=2

        final=client.post(f'/api/v1/simulated-payments/{attempt_id}/analyze',json={
            'context':scenario['context'],'messages':scenario['messages']})
        assert final.status_code==200
        payment=final.json()['payment']
        assert payment['state'] in ('WARNING','VERIFICATION_REQUIRED','SIMULATED_HELD')
        assert payment['simulated_status']=='NOT_EXECUTED'
        assert payment['decision']!='ALLOW'
        assert len(payment['top_reasons'])<=4

        ablation=client.post(f'/api/v1/simulated-payments/{attempt_id}/ablation',json={})
        assert ablation.status_code==200
        replay=ablation.json()
        assert replay['ablated_assessment']['app_scam_risk'] is not None
        assert replay['ablated_assessment']['decision']
        assert 'message evidence' in replay['method']
        assert client.get(f'/api/v1/simulated-payments/{attempt_id}').json()['simulated_status']=='NOT_EXECUTED'

        cancelled=client.post(f'/api/v1/simulated-payments/{attempt_id}/cancel')
        assert cancelled.status_code==200
        assert cancelled.json()['state']=='CANCELLED'
        feedback=client.get(f'/api/v1/feedback/{attempt_id}')
        assert feedback.status_code==200
        assert feedback.json()['fraud_labels']==[]
        assert any(row['action']=='USER_CANCELLED' for row in feedback.json()['user_actions'])


def test_legitimate_family_emergency_is_in_demo_library_with_observed_relationship():
    with TestClient(app) as client:
        scenario=client.get('/api/v1/simulated-payments/scenarios/legitimate_family_emergency').json()
        assert scenario['amount']==20000
        assert scenario['recipient_alias']=='R201'
        assert scenario['context']['contacted_by_unknown_person'] is False
        result=client.get('/api/v1/simulated-payments/scenarios').json()['scenarios']
        assert any(item['id']=='legitimate_family_emergency' for item in result)
        created=_create(client,scenario,'phase11-family-'+uuid4().hex[:12])
        assessment=client.post(f"/api/v1/simulated-payments/{created['payment_attempt_id']}/analyze",json={
            'context':scenario['context'],'messages':scenario['messages']})
        assert assessment.status_code==200
        payment=assessment.json()['payment']
        assert 'You have paid this recipient before.' in payment['protective_reasons']


def test_emergency_demo_distinguishes_urgency_from_social_engineering():
    with TestClient(app) as client:
        results = {}
        for scenario_id in ('family_emergency', 'legitimate_family_emergency'):
            scenario = client.get(f'/api/v1/simulated-payments/scenarios/{scenario_id}').json()
            created = _create(client, scenario, f'phase11-emergency-pair-{uuid4().hex[:12]}')
            attempt_id = created['payment_attempt_id']
            analyzed = client.post(f'/api/v1/simulated-payments/{attempt_id}/analyze', json={
                'context': scenario['context'], 'messages': scenario['messages']})
            assert analyzed.status_code == 200
            results[scenario_id] = {
                'assessment': client.get(
                    f'/api/v1/simulated-payments/{attempt_id}/analyst').json()['attempt']['assessment'],
                'network': client.get(f'/api/v1/simulated-payments/{attempt_id}/network').json(),
            }

        scam = results['family_emergency']['assessment']
        legitimate = results['legitimate_family_emergency']['assessment']
        assert legitimate['app_scam_risk'] < scam['app_scam_risk']
        assert legitimate['decision'] == 'ALLOW'
        assert scam['decision'] != 'ALLOW'
        assert any(item['code'] == 'CTX_URGENT_REQUEST' for item in legitimate['top_reasons'])
        assert 'KNOWN_RECIPIENT_LONG_TERM' in legitimate['protective_evidence']
        assert 'NO_UNKNOWN_CONTACT_REPORTED' not in legitimate['protective_evidence']
        network = results['legitimate_family_emergency']['network']
        assert network['available'] is True
        recipient = next(node for node in network['nodes'] if node['role'] == 'recipient')
        assert 'no_graph_rule_signals' in recipient['details']['risk_indicators']

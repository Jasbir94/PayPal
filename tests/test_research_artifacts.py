from fastapi.testclient import TestClient
from backend.app.main import app


def test_failure_replay_uses_measured_rows_and_marks_unavailable_fields():
    with TestClient(app) as client:
        response=client.get('/api/v1/research/failures')
    assert response.status_code==200
    payload=response.json()
    assert 'SYNTHETIC' in payload['label']
    assert payload['count']==payload['false_positives']+payload['false_negatives']
    if payload['cases']:
        assert payload['cases'][0]['risk'] is None
        assert payload['cases'][0]['confidence'] is None

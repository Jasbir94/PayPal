from fastapi.testclient import TestClient
from backend.app.main import app


def test_model_info_reports_safe_versions_without_local_paths():
    with TestClient(app) as client:
        response=client.get('/api/v1/model-info')
    assert response.status_code==200
    data=response.json()
    assert data['policy_version']=='day9-v1'
    assert data['active_fusion_version']=='fusion-logistic-platt-v1'
    assert 'components' in data
    assert 'score_semantics' in data
    assert 'C:\\' not in response.text

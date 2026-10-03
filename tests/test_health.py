from fastapi.testclient import TestClient
from backend.app.main import app

def test_endpoints():
    with TestClient(app) as client:
        assert client.get('/').json() == {'project': 'APP Shield', 'status': 'running'}
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json() == {'status': 'healthy'}
        assert client.get('/predict').status_code == 404

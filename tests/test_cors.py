from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_cors_preflight_allows_configured_frontend_and_required_api_headers(monkeypatch):
    origin = 'https://pay-pal-uwoa.vercel.app'
    monkeypatch.setenv('DATABASE_URL', 'sqlite://')
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('APP_SHIELD_CORS_ORIGINS', origin)
    with TestClient(create_app()) as client:
        response = client.options('/api/v1/chat/sessions', headers={
            'Origin': origin,
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'authorization,content-type',
        })
        profiles = client.get('/api/v1/banking/profiles', headers={'Origin': origin})
        protected_balance = client.get('/api/v1/banking/balance', headers={'Origin': origin})
        missing_route = client.get('/api/v1/not-a-route', headers={'Origin': origin})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == origin
    assert 'POST' in response.headers['access-control-allow-methods']
    assert 'authorization' in response.headers['access-control-allow-headers'].lower()
    assert 'content-type' in response.headers['access-control-allow-headers'].lower()
    assert profiles.status_code == 200
    assert profiles.json()['profiles']
    assert profiles.headers['access-control-allow-origin'] == origin
    assert protected_balance.status_code == 401
    assert protected_balance.headers['access-control-allow-origin'] == origin
    assert missing_route.status_code == 404
    assert missing_route.headers['access-control-allow-origin'] == origin


def test_cors_preflight_rejects_unconfigured_origin(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'sqlite://')
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('APP_SHIELD_CORS_ORIGINS', 'https://pay-pal-84xr.vercel.app')
    with TestClient(create_app()) as client:
        response = client.options('/api/v1/chat/sessions', headers={
            'Origin': 'https://untrusted.example',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'authorization,content-type',
        })
        profiles = client.get('/api/v1/banking/profiles', headers={'Origin':'https://untrusted.example'})
    assert response.status_code == 400
    assert 'access-control-allow-origin' not in response.headers
    assert profiles.status_code == 200
    assert 'access-control-allow-origin' not in profiles.headers
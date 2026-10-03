from backend.app.main import create_app

def test_final_route_is_versioned_and_legacy_routes_remain_registered():
    paths=create_app().openapi()['paths']
    assert '/api/v1/analyze-payment' in paths
    assert '/api/v1/risk/preliminary' in paths
    assert '/api/v1/risk/contextual' in paths
    assert 'post' in paths['/api/v1/analyze-payment']

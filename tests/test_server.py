from fastapi.testclient import TestClient
from swarmlab.server import app


def test_configuration_status_never_exposes_credentials(monkeypatch):
    monkeypatch.setenv("FALKORDB_PASSWORD", "private-test-db")
    monkeypatch.setenv("MODEL_API_KEY", "private-test-model")
    response = TestClient(app).get("/api/config-status")
    assert response.status_code == 200
    assert "private-test" not in response.text
    assert response.json()["database_password_configured"] is True



def test_preview_and_static_dashboard():
    client = TestClient(app)
    assert client.get('/').status_code == 200
    assert client.get('/static/app.js').status_code == 200
    preview = client.get('/api/world-preview?seed=11')
    assert preview.status_code == 200
    assert preview.json()['tick'] == 0
    assert client.get('/api/world-preview?seed=-1').status_code == 422


def test_cross_origin_write_rejected():
    response = TestClient(app).post('/api/config', json={}, headers={'Origin': 'https://elsewhere.example'})
    assert response.status_code == 403


def test_validation_does_not_echo_secrets():
    response = TestClient(app).post('/api/config', json={'api_key': {'secret': 'private-input'}})
    assert response.status_code == 422
    assert 'private-input' not in response.text


def test_sleep_endpoint_validates_source_and_dispatches(monkeypatch):
    from swarmlab import server
    class Source:
        def __init__(self, settings): pass
        def get_episode(self, episode_id):
            return {'kind':'discovery' if episode_id=='discovery' else 'evaluation','status':'discovery_budget_complete'}
    monkeypatch.setattr(server,'Memory',Source)
    monkeypatch.setattr(server.jobs,'start',lambda action,params:{'action':action,'episode_id':params['episode_id']})
    client=TestClient(app)
    assert client.post('/api/jobs',json={'action':'sleep'}).status_code==422
    assert client.post('/api/jobs',json={'action':'sleep','episode_id':'transfer'}).status_code==422
    response=client.post('/api/jobs',json={'action':'sleep','episode_id':'discovery'})
    assert response.status_code==200
    assert response.json()['episode_id']=='discovery'

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy", "service": "ai-banking-api", "version": "1.0.0"}

def test_admin_url(settings, client):
    r = client.get("/admintest/login/")
    assert r.status_code == 200

def test_admin_url(client):
    r = client.get("/admintest/login/")
    assert r.status_code == 200

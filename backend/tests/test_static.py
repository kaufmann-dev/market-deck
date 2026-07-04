def test_root_serves_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text


def test_unknown_path_spa_fallback(client):
    response = client.get("/some/client/route")
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text


def test_path_traversal_blocked(client):
    response = client.get("/..%2f..%2fetc%2fpasswd")
    assert response.status_code == 404

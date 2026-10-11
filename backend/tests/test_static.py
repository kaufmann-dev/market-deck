def test_root_serves_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text


def test_client_routes_serve_index(client):
    for path in ("/list/core", "/stock/AAPL", "/stock/BRK.B/"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "<!DOCTYPE html>" in response.text


def test_unknown_path_renders_404_page(client):
    response = client.get("/some/unknown/route")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "<h1>Page not found</h1>" in response.text


def test_unknown_api_path_returns_json_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


def test_error_page_copy_matches_status():
    from app.error_pages import render_error_page

    assert "<h1>Access denied</h1>" in render_error_page(403)
    assert "<h1>Something went wrong</h1>" in render_error_page(500)
    assert "<h1>Something went wrong</h1>" in render_error_page(503)
    assert "<h1>Request could not be completed</h1>" in render_error_page(400)


def test_path_traversal_blocked(client):
    response = client.get("/..%2f..%2fetc%2fpasswd")
    assert response.status_code == 404

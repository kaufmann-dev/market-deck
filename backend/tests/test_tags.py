COLORS = {"bg": "#111", "text": "#eee", "border": "#333"}


def _setup_list(client, admin_headers):
    response = client.post(
        "/api/lists",
        headers=admin_headers,
        json={"slug": "tag-list", "name": "Tag List", "short_name": "Tags"},
    )
    assert response.status_code == 200


def test_create_tag_normalizes(client, admin_headers):
    _setup_list(client, admin_headers)
    response = client.post(
        "/api/lists/tag-list/tags", headers=admin_headers, json={"tag": "  new   tech ", **COLORS}
    )
    assert response.status_code == 200
    assert response.json() == {"tag": "NEW TECH"}


def test_create_tag_duplicate(client, admin_headers):
    _setup_list(client, admin_headers)
    client.post("/api/lists/tag-list/tags", headers=admin_headers, json={"tag": "TECH", **COLORS})
    response = client.post(
        "/api/lists/tag-list/tags", headers=admin_headers, json={"tag": "tech", **COLORS}
    )
    assert response.status_code == 400


def test_create_tag_empty(client, admin_headers):
    _setup_list(client, admin_headers)
    response = client.post(
        "/api/lists/tag-list/tags", headers=admin_headers, json={"tag": "   ", **COLORS}
    )
    assert response.status_code == 400


def test_update_tag_colors(client, admin_headers):
    _setup_list(client, admin_headers)
    client.post("/api/lists/tag-list/tags", headers=admin_headers, json={"tag": "TECH", **COLORS})
    response = client.put(
        "/api/lists/tag-list/tags/TECH",
        headers=admin_headers,
        json={"bg": "#222", "text": "#fff", "border": "#444"},
    )
    assert response.status_code == 200
    tags = client.get("/api/init", headers=admin_headers).json()["lists"]["tag-list"]["tags"]
    assert tags == [{"tag": "TECH", "bg": "#222", "text": "#fff", "border": "#444", "sortOrder": 0}]


def test_update_missing_tag(client, admin_headers):
    _setup_list(client, admin_headers)
    response = client.put("/api/lists/tag-list/tags/NOPE", headers=admin_headers, json=COLORS)
    assert response.status_code == 404


def test_delete_unused_tag(client, admin_headers):
    _setup_list(client, admin_headers)
    client.post("/api/lists/tag-list/tags", headers=admin_headers, json={"tag": "TECH", **COLORS})
    assert client.delete("/api/lists/tag-list/tags/TECH", headers=admin_headers).status_code == 200


def test_delete_tag_in_use(client, admin_headers):
    _setup_list(client, admin_headers)
    client.post("/api/lists/tag-list/tags", headers=admin_headers, json={"tag": "TECH", **COLORS})
    client.post(
        "/api/lists/tag-list/tickers",
        headers=admin_headers,
        json={"symbol": "AAPL", "name": "Apple", "tag": "TECH"},
    )
    response = client.delete("/api/lists/tag-list/tags/TECH", headers=admin_headers)
    assert response.status_code == 400


def test_delete_missing_tag(client, admin_headers):
    _setup_list(client, admin_headers)
    assert client.delete("/api/lists/tag-list/tags/NOPE", headers=admin_headers).status_code == 404


def test_tag_writes_forbidden_for_demo(client, demo_headers):
    response = client.post(
        "/api/lists/us-sectors/tags", headers=demo_headers, json={"tag": "X", **COLORS}
    )
    assert response.status_code == 403

import pytest

NEW_LIST = {"slug": "test-list", "name": "Test List", "short_name": "Test"}


def _create_list(client, admin_headers, **overrides):
    response = client.post("/api/lists", headers=admin_headers, json={**NEW_LIST, **overrides})
    assert response.status_code == 200, response.text
    return response.json()


def _add_tag(client, admin_headers, slug="test-list", tag="TECH"):
    response = client.post(
        f"/api/lists/{slug}/tags",
        headers=admin_headers,
        json={"tag": tag, "bg": "#111", "text": "#eee", "border": "#333"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_create_list(client, admin_headers):
    body = _create_list(client, admin_headers)
    assert body["slug"] == "test-list"
    lists = client.get("/api/init", headers=admin_headers).json()["lists"]
    created = lists["test-list"]
    assert created["name"] == "Test List"
    assert created["category"] == "OTHER"
    assert created["showTag"] is True


def test_create_list_duplicate_slug(client, admin_headers):
    _create_list(client, admin_headers)
    response = client.post("/api/lists", headers=admin_headers, json=NEW_LIST)
    assert response.status_code == 400


def test_update_list_normalizes_category(client, admin_headers):
    _create_list(client, admin_headers)
    response = client.put(
        "/api/lists/test-list",
        headers=admin_headers,
        json={"category": "  fancy   etfs "},
    )
    assert response.status_code == 200
    lists = client.get("/api/init", headers=admin_headers).json()["lists"]
    assert lists["test-list"]["category"] == "FANCY ETFS"


def test_update_list_no_fields(client, admin_headers):
    _create_list(client, admin_headers)
    response = client.put("/api/lists/test-list", headers=admin_headers, json={})
    assert response.status_code == 400


def test_update_missing_list(client, admin_headers):
    response = client.put("/api/lists/nope", headers=admin_headers, json={"name": "X"})
    assert response.status_code == 404


def test_delete_list_cascades(client, admin_headers):
    _create_list(client, admin_headers)
    _add_tag(client, admin_headers)
    client.post(
        "/api/lists/test-list/tickers",
        headers=admin_headers,
        json={"symbol": "AAPL", "name": "Apple", "tag": "TECH"},
    )
    response = client.delete("/api/lists/test-list", headers=admin_headers)
    assert response.status_code == 200
    lists = client.get("/api/init", headers=admin_headers).json()["lists"]
    assert "test-list" not in lists


def test_delete_missing_list(client, admin_headers):
    assert client.delete("/api/lists/nope", headers=admin_headers).status_code == 404


def test_add_ticker_assigns_sort_order(client, admin_headers):
    _create_list(client, admin_headers)
    _add_tag(client, admin_headers)
    first = client.post(
        "/api/lists/test-list/tickers",
        headers=admin_headers,
        json={"symbol": "AAPL", "name": "Apple", "tag": "TECH"},
    )
    second = client.post(
        "/api/lists/test-list/tickers",
        headers=admin_headers,
        json={"symbol": "MSFT", "name": "Microsoft", "tag": "tech", "currency": "USD"},
    )
    assert first.status_code == 200 and second.status_code == 200
    items = client.get("/api/init", headers=admin_headers).json()["lists"]["test-list"]["items"]
    assert [item["ticker"] for item in items] == ["AAPL", "MSFT"]
    assert items[1]["tag"] == "TECH"  # normalized


def test_add_ticker_unknown_tag(client, admin_headers):
    _create_list(client, admin_headers)
    response = client.post(
        "/api/lists/test-list/tickers",
        headers=admin_headers,
        json={"symbol": "AAPL", "name": "Apple", "tag": "NOPE"},
    )
    assert response.status_code == 400


def test_update_ticker(client, admin_headers):
    _create_list(client, admin_headers)
    _add_tag(client, admin_headers)
    ticker_id = client.post(
        "/api/lists/test-list/tickers",
        headers=admin_headers,
        json={"symbol": "AAPL", "name": "Apple", "tag": "TECH"},
    ).json()["id"]

    response = client.put(
        f"/api/tickers/{ticker_id}", headers=admin_headers, json={"name": "Apple Inc."}
    )
    assert response.status_code == 200
    items = client.get("/api/init", headers=admin_headers).json()["lists"]["test-list"]["items"]
    assert items[0]["name"] == "Apple Inc."


def test_update_ticker_rejects_unknown_tag(client, admin_headers):
    _create_list(client, admin_headers)
    _add_tag(client, admin_headers)
    ticker_id = client.post(
        "/api/lists/test-list/tickers",
        headers=admin_headers,
        json={"symbol": "AAPL", "name": "Apple", "tag": "TECH"},
    ).json()["id"]

    response = client.put(
        f"/api/tickers/{ticker_id}", headers=admin_headers, json={"tag": "MISSING"}
    )
    assert response.status_code == 400


def test_update_missing_ticker(client, admin_headers):
    response = client.put("/api/tickers/999999", headers=admin_headers, json={"name": "X"})
    assert response.status_code == 404


def test_delete_ticker(client, admin_headers):
    _create_list(client, admin_headers)
    _add_tag(client, admin_headers)
    ticker_id = client.post(
        "/api/lists/test-list/tickers",
        headers=admin_headers,
        json={"symbol": "AAPL", "name": "Apple", "tag": "TECH"},
    ).json()["id"]

    assert client.delete(f"/api/tickers/{ticker_id}", headers=admin_headers).status_code == 200
    assert client.delete(f"/api/tickers/{ticker_id}", headers=admin_headers).status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/lists", NEW_LIST),
        ("put", "/api/lists/us-sectors", {"name": "X"}),
        ("delete", "/api/lists/us-sectors", None),
        ("post", "/api/lists/us-sectors/tickers", {"symbol": "A", "name": "A", "tag": "X"}),
        ("put", "/api/tickers/1", {"name": "X"}),
        ("delete", "/api/tickers/1", None),
    ],
)
def test_writes_forbidden_for_demo(client, demo_headers, method, path, payload):
    kwargs = {"headers": demo_headers}
    if payload is not None:
        kwargs["json"] = payload
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 403

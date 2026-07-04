def test_init_requires_auth(client):
    assert client.get("/api/init").status_code == 401


def test_init_shape(client, admin_headers):
    body = client.get("/api/init", headers=admin_headers).json()
    assert body["settings"]["GLOBAL_BASE_CURRENCY"] == "EUR"
    assert len(body["lists"]) == 5

    for slug, wl in body["lists"].items():
        assert set(wl) == {
            "id", "name", "shortName", "category", "description",
            "currency", "showTag", "tags", "items",
        }
        assert wl["items"], f"list {slug} seeded without tickers"
        for item in wl["items"]:
            assert set(item) == {"id", "ticker", "name", "tag", "currency"}
        for tag in wl["tags"]:
            assert set(tag) == {"tag", "bg", "text", "border", "sortOrder"}
        # every ticker tag has a color definition (sync_watchlist_tags invariant)
        defined = {tag["tag"] for tag in wl["tags"]}
        used = {item["tag"] for item in wl["items"] if item["tag"]}
        assert used <= defined


def test_get_settings(client, demo_headers):
    body = client.get("/api/settings", headers=demo_headers).json()
    assert body["GLOBAL_BASE_CURRENCY"] == "EUR"


def test_put_setting_upserts(client, admin_headers):
    created = client.put(
        "/api/settings/SOME_KEY", headers=admin_headers, json={"value": "one"}
    )
    assert created.status_code == 200
    updated = client.put(
        "/api/settings/SOME_KEY", headers=admin_headers, json={"value": "two"}
    )
    assert updated.status_code == 200
    body = client.get("/api/settings", headers=admin_headers).json()
    assert body["SOME_KEY"] == "two"


def test_put_setting_demo_forbidden(client, demo_headers):
    response = client.put(
        "/api/settings/GLOBAL_BASE_CURRENCY", headers=demo_headers, json={"value": "USD"}
    )
    assert response.status_code == 403

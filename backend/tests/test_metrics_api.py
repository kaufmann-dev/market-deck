"""Metrics endpoint tests with Yahoo mocked via respx."""
import re
from datetime import UTC, datetime

import httpx
import pytest
import respx

CHART_URL = re.compile(r"https://query1\.finance\.yahoo\.com/v8/finance/chart/(?P<symbol>[^?]+)")


def chart_payload(pairs):
    timestamps = [
        int(datetime.fromisoformat(f"{day}T12:00:00+00:00").timestamp()) for day, _ in pairs
    ]
    closes = [close for _, close in pairs]
    return {
        "chart": {
            "result": [
                {
                    "meta": {"exchangeTimezoneName": "UTC"},
                    "timestamp": timestamps,
                    "indicators": {"adjclose": [{"adjclose": closes}]},
                }
            ],
            "error": None,
        }
    }


AAPL_SERIES = [("2025-08-01", 100.0), ("2026-06-01", 200.0), ("2026-07-01", 220.0)]
FX_SERIES = [("2025-08-01", 0.5), ("2026-05-01", 0.9)]

SYMBOL_PAYLOADS = {
    "AAPL": chart_payload(AAPL_SERIES),
    "USDEUR%3DX": chart_payload(FX_SERIES),
}


def yahoo_responder(request, symbol):
    payload = SYMBOL_PAYLOADS.get(symbol)
    if payload is None:
        return httpx.Response(404, json={"chart": {"result": None, "error": {"code": "Not Found"}}})
    return httpx.Response(200, json=payload)


@pytest.fixture
def yahoo_mock():
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route(url__regex=CHART_URL)
        route.side_effect = yahoo_responder
        yield route


@pytest.fixture
def metrics_list(client, admin_headers):
    client.post(
        "/api/lists",
        headers=admin_headers,
        json={"slug": "metrics-list", "name": "Metrics", "short_name": "Met"},
    )
    client.post(
        "/api/lists/metrics-list/tags",
        headers=admin_headers,
        json={"tag": "TECH", "bg": "#111", "text": "#eee", "border": "#333"},
    )
    for symbol in ("AAPL", "BAD"):
        client.post(
            "/api/lists/metrics-list/tickers",
            headers=admin_headers,
            json={"symbol": symbol, "name": symbol, "tag": "TECH", "currency": "USD"},
        )
    return "metrics-list"


def test_metrics_shape_and_conversion(client, admin_headers, yahoo_mock, metrics_list):
    response = client.get(f"/api/lists/{metrics_list}/metrics", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["baseCurrency"] == "EUR"
    assert body["asOf"] == datetime.now(UTC).date().isoformat()
    assert body["failed"] == ["BAD"]

    aapl, bad = body["tickers"]
    assert aapl["symbol"] == "AAPL"
    assert aapl["ok"] is True
    assert aapl["currentPrice"] == 220.0 * 0.9  # converted with latest FX rate
    assert set(aapl["lookbacks"]) == {"1", "3", "6", "12"}
    assert len(aapl["monthly"]) == 12
    assert bad["ok"] is False
    assert bad["currentPrice"] is None


def test_second_call_hits_cache(client, admin_headers, yahoo_mock, metrics_list):
    client.get(f"/api/lists/{metrics_list}/metrics", headers=admin_headers)
    calls_after_first = yahoo_mock.call_count
    assert calls_after_first == 3  # AAPL + USDEUR=X + BAD

    response = client.get(f"/api/lists/{metrics_list}/metrics", headers=admin_headers)
    assert response.status_code == 200
    # AAPL/FX cached; BAD held back by the failure cooldown -> zero new requests
    assert yahoo_mock.call_count == calls_after_first
    assert response.json()["failed"] == ["BAD"]


def test_base_override_skips_fx(client, admin_headers, yahoo_mock, metrics_list):
    response = client.get(f"/api/lists/{metrics_list}/metrics?base=USD", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["baseCurrency"] == "USD"
    assert body["tickers"][0]["currentPrice"] == 220.0  # unconverted
    requested = {str(call.request.url) for call in yahoo_mock.calls}
    assert not any("USDEUR" in url for url in requested)


def test_cache_is_per_account(client, admin_headers, demo_headers, yahoo_mock, metrics_list):
    client.get(f"/api/lists/{metrics_list}/metrics", headers=admin_headers)
    admin_calls = yahoo_mock.call_count

    client.get(f"/api/lists/{metrics_list}/metrics", headers=demo_headers)
    # demo has its own cache key -> refetches non-cooldown symbols
    assert yahoo_mock.call_count > admin_calls


def test_clear_cache_forces_refetch(client, admin_headers, yahoo_mock, metrics_list):
    client.get(f"/api/lists/{metrics_list}/metrics", headers=admin_headers)
    calls_after_first = yahoo_mock.call_count

    cleared = client.delete("/api/prices/cache", headers=admin_headers)
    assert cleared.status_code == 200
    assert cleared.json()["deleted"] == 2  # AAPL + FX series were cached

    client.get(f"/api/lists/{metrics_list}/metrics", headers=admin_headers)
    assert yahoo_mock.call_count > calls_after_first


def test_metrics_missing_list(client, admin_headers, yahoo_mock):
    assert client.get("/api/lists/nope/metrics", headers=admin_headers).status_code == 404


def test_metrics_requires_auth(client, yahoo_mock, metrics_list):
    assert client.get(f"/api/lists/{metrics_list}/metrics").status_code == 401

"""Stock endpoint tests with Yahoo mocked via respx."""
import re
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

CHART_URL = re.compile(r"https://query1\.finance\.yahoo\.com/v8/finance/chart/(?P<symbol>[^?]+)")
SEARCH_URL = re.compile(r"https://query1\.finance\.yahoo\.com/v1/finance/search")
SUMMARY_URL = re.compile(
    r"https://query2\.finance\.yahoo\.com/v10/finance/quoteSummary/(?P<symbol>[^?]+)"
)
TIMESERIES_URL = re.compile(
    r"https://query2\.finance\.yahoo\.com/ws/fundamentals-timeseries/v1/finance/timeseries/(?P<symbol>[^?]+)"
)
CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
COOKIE_URL = "https://fc.yahoo.com/"


def chart_payload(symbol="AAPL", count=260):
    start = datetime(2025, 7, 1, 12, tzinfo=UTC)
    timestamps = [int((start + timedelta(days=index)).timestamp()) for index in range(count)]
    closes = [100 + index for index in range(count)]
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "symbol": symbol,
                        "longName": "Apple Inc.",
                        "currency": "USD",
                        "exchangeName": "NMS",
                        "fullExchangeName": "NasdaqGS",
                        "exchangeTimezoneName": "UTC",
                        "regularMarketPrice": closes[-1],
                        "chartPreviousClose": closes[-2],
                        "fiftyTwoWeekHigh": closes[-1] + 1,
                        "fiftyTwoWeekLow": closes[0] - 1,
                        "regularMarketVolume": 123456,
                    },
                    "timestamp": timestamps,
                    "indicators": {
                        "quote": [
                            {
                                "open": [close - 1 for close in closes],
                                "high": [close + 1 for close in closes],
                                "low": [close - 2 for close in closes],
                                "close": closes,
                                "volume": [1000 + index for index in range(count)],
                            }
                        ],
                        "adjclose": [{"adjclose": closes}],
                    },
                }
            ],
            "error": None,
        }
    }


def summary_payload(symbol="AAPL"):
    return {
        "quoteSummary": {
            "result": [
                {
                    "price": {
                        "symbol": symbol,
                        "longName": "Apple Inc.",
                        "currency": "USD",
                        "regularMarketPrice": {"raw": 359.0},
                        "regularMarketPreviousClose": {"raw": 358.0},
                        "regularMarketChange": {"raw": 1.0},
                        "regularMarketChangePercent": {"raw": 0.28},
                        "marketCap": {"raw": 3000000000000},
                        "exchangeName": "NMS",
                    },
                    "summaryProfile": {"sector": "Technology", "longBusinessSummary": "Consumer hardware."},
                    "summaryDetail": {
                        "trailingPE": {"raw": 29.5},
                        "dividendYield": {"raw": 0.005},
                        "fiftyTwoWeekHigh": {"raw": 360.0},
                        "fiftyTwoWeekLow": {"raw": 160.0},
                        "averageVolume": {"raw": 50000000},
                    },
                    "defaultKeyStatistics": {"beta": {"raw": 1.2}},
                    "financialData": {
                        "targetMeanPrice": {"raw": 370.0},
                        "recommendationMean": {"raw": 1.8},
                    },
                    "calendarEvents": {"earnings": {"earningsDate": [{"fmt": "2026-08-01"}]}},
                    "recommendationTrend": {"trend": [{"period": "0m", "strongBuy": 8}]},
                    "earnings": {"financialsChart": {"yearly": []}},
                    "earningsTrend": {"trend": []},
                }
            ],
            "error": None,
        }
    }


def search_payload():
    return {
        "quotes": [
            {
                "symbol": "AAPL",
                "longname": "Apple Inc.",
                "exchDisp": "NASDAQ",
                "quoteType": "EQUITY",
                "typeDisp": "Equity",
                "currency": "USD",
            }
        ],
        "news": [
            {
                "title": "Apple headline",
                "publisher": "Wire",
                "link": "https://example.com/apple",
                "providerPublishTime": 1780000000,
                "thumbnail": {"resolutions": [{"url": "https://example.com/thumb.jpg"}]},
            }
        ],
    }


def _ts_block(type_name, points):
    return {
        "meta": {"symbol": ["AAPL"], "type": [type_name]},
        type_name: [
            {"asOfDate": date, "reportedValue": {"raw": value, "fmt": str(value)}}
            for date, value in points
        ],
    }


def financials_payload():
    return {
        "timeseries": {
            "result": [
                _ts_block("annualTotalRevenue", [("2024-12-31", 20), ("2025-12-31", 30)]),
                _ts_block("annualNetIncome", [("2024-12-31", 5), ("2025-12-31", 8)]),
                _ts_block("quarterlyTotalRevenue", [("2025-09-30", 9)]),
                _ts_block("annualTotalAssets", [("2025-12-31", 100)]),
                _ts_block("annualOperatingCashFlow", [("2025-12-31", 40)]),
            ],
            "error": None,
        }
    }


def install_yahoo_mocks(mock, crumb_status=200, summary_status=200):
    chart_route = mock.route(url__regex=CHART_URL)
    chart_route.return_value = httpx.Response(200, json=chart_payload())

    search_route = mock.route(url__regex=SEARCH_URL)

    def search_responder(request):
        if request.url.params.get("quotesCount") == "0":
            return httpx.Response(200, json={"news": search_payload()["news"]})
        return httpx.Response(200, json=search_payload())

    search_route.side_effect = search_responder

    cookie_route = mock.get(COOKIE_URL).mock(
        return_value=httpx.Response(200, headers={"set-cookie": "A1=test; Path=/"})
    )
    crumb_route = mock.get(CRUMB_URL).mock(return_value=httpx.Response(crumb_status, text="crumb"))

    summary_route = mock.route(url__regex=SUMMARY_URL)

    def summary_responder(request, symbol):
        if summary_status != 200:
            return httpx.Response(summary_status, json={"quoteSummary": {"result": None, "error": {}}})
        return httpx.Response(200, json=summary_payload(symbol))

    summary_route.side_effect = summary_responder

    timeseries_route = mock.route(url__regex=TIMESERIES_URL)
    timeseries_route.return_value = httpx.Response(200, json=financials_payload())

    return {
        "chart": chart_route,
        "search": search_route,
        "cookie": cookie_route,
        "crumb": crumb_route,
        "summary": summary_route,
        "timeseries": timeseries_route,
    }


def test_search_shape(client, admin_headers):
    with respx.mock(assert_all_called=False) as mock:
        routes = install_yahoo_mocks(mock)
        response = client.get("/api/search?q=AAPL", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["quotes"][0]["symbol"] == "AAPL"
    assert body["quotes"][0]["name"] == "Apple Inc."
    assert body["news"][0]["title"] == "Apple headline"
    assert routes["search"].call_count == 1


def test_search_upstream_failure_is_not_cached(client, admin_headers):
    with respx.mock(assert_all_called=False) as mock:
        search_route = mock.route(url__regex=SEARCH_URL)
        calls = 0

        def search_responder(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(429, text="Too Many Requests")
            return httpx.Response(200, json=search_payload())

        search_route.side_effect = search_responder
        first = client.get("/api/search?q=AAPL", headers=admin_headers)
        second = client.get("/api/search?q=AAPL", headers=admin_headers)

    assert first.status_code == 200
    assert first.json() == {"quotes": [], "news": []}
    assert second.status_code == 200
    assert second.json()["quotes"][0]["symbol"] == "AAPL"
    assert search_route.call_count == 2


def test_empty_search_response_is_refetched(client, admin_headers):
    with respx.mock(assert_all_called=False) as mock:
        search_route = mock.route(url__regex=SEARCH_URL)
        calls = 0

        def search_responder(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(200, json={"quotes": [], "news": []})
            return httpx.Response(200, json=search_payload())

        search_route.side_effect = search_responder
        first = client.get("/api/search?q=AAPL", headers=admin_headers)
        second = client.get("/api/search?q=AAPL", headers=admin_headers)

    assert first.status_code == 200
    assert first.json() == {"quotes": [], "news": []}
    assert second.status_code == 200
    assert second.json()["quotes"][0]["symbol"] == "AAPL"
    assert search_route.call_count == 2


def test_overview_with_fundamentals(client, admin_headers):
    with respx.mock(assert_all_called=False) as mock:
        install_yahoo_mocks(mock)
        response = client.get("/api/stocks/AAPL", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["quote"]["symbol"] == "AAPL"
    assert body["quote"]["regularMarketPrice"] == 359.0
    assert body["profile"]["sector"] == "Technology"
    assert body["keyStats"]["beta"] == 1.2
    assert body["fundamentalsAvailable"] is True


@pytest.mark.parametrize(("crumb_status", "summary_status"), [(404, 200), (200, 404)])
def test_overview_graceful_when_fundamentals_unavailable(
    client, admin_headers, crumb_status, summary_status
):
    with respx.mock(assert_all_called=False) as mock:
        install_yahoo_mocks(mock, crumb_status=crumb_status, summary_status=summary_status)
        response = client.get("/api/stocks/AAPL", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["quote"]["symbol"] == "AAPL"
    assert body["quote"]["regularMarketPrice"] == 359
    assert body["fundamentalsAvailable"] is False
    assert body["profile"] is None


def test_financials_from_timeseries(client, admin_headers):
    with respx.mock(assert_all_called=False) as mock:
        install_yahoo_mocks(mock)
        response = client.get("/api/stocks/AAPL/financials", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["financialsAvailable"] is True

    income = body["incomeAnnual"]
    assert [row["endDate"] for row in income] == [
        int(datetime(2025, 12, 31, tzinfo=UTC).timestamp()),
        int(datetime(2024, 12, 31, tzinfo=UTC).timestamp()),
    ]
    assert income[0]["totalRevenue"] == 30
    assert income[0]["netIncome"] == 8
    # Metrics with no data are omitted rather than rendered as empty columns.
    assert "costOfRevenue" not in income[0]

    assert body["balanceAnnual"][0]["totalAssets"] == 100
    assert body["cashflowAnnual"][0]["operatingCashFlow"] == 40
    assert len(body["incomeQuarterly"]) == 1


def test_financials_unavailable_when_upstream_fails(client, admin_headers):
    with respx.mock(assert_all_called=False) as mock:
        install_yahoo_mocks(mock, crumb_status=404)
        response = client.get("/api/stocks/AAPL/financials", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["financialsAvailable"] is False
    assert body["incomeAnnual"] == []


def test_chart_and_technicals(client, admin_headers):
    with respx.mock(assert_all_called=False) as mock:
        routes = install_yahoo_mocks(mock)
        response = client.get("/api/stocks/AAPL/chart?range=1y&interval=1d", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["ohlc"]) == 260
    assert body["meta"]["currency"] == "USD"
    assert body["technicals"]["sma20"] == 349.5
    assert body["technicals"]["rsi14"] == 100.0
    assert routes["chart"].call_count == 1


def test_news_upstream_failure_is_not_cached(client, admin_headers):
    with respx.mock(assert_all_called=False) as mock:
        news_route = mock.route(url__regex=SEARCH_URL)
        calls = 0

        def news_responder(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(429, text="Too Many Requests")
            return httpx.Response(200, json={"news": search_payload()["news"]})

        news_route.side_effect = news_responder
        first = client.get("/api/stocks/AAPL/news", headers=admin_headers)
        second = client.get("/api/stocks/AAPL/news", headers=admin_headers)

    assert first.status_code == 200
    assert first.json() == {"news": []}
    assert second.status_code == 200
    assert second.json()["news"][0]["title"] == "Apple headline"
    assert news_route.call_count == 2


def test_empty_news_response_is_refetched(client, admin_headers):
    with respx.mock(assert_all_called=False) as mock:
        news_route = mock.route(url__regex=SEARCH_URL)
        calls = 0

        def news_responder(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(200, json={"news": []})
            return httpx.Response(200, json={"news": search_payload()["news"]})

        news_route.side_effect = news_responder
        first = client.get("/api/stocks/AAPL/news", headers=admin_headers)
        second = client.get("/api/stocks/AAPL/news", headers=admin_headers)

    assert first.status_code == 200
    assert first.json() == {"news": []}
    assert second.status_code == 200
    assert second.json()["news"][0]["title"] == "Apple headline"
    assert news_route.call_count == 2


def test_second_call_hits_global_cache(client, admin_headers):
    with respx.mock(assert_all_called=False) as mock:
        routes = install_yahoo_mocks(mock)
        first = client.get("/api/stocks/AAPL", headers=admin_headers)
        counts_after_first = {name: route.call_count for name, route in routes.items()}
        second = client.get("/api/stocks/AAPL", headers=admin_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert {name: route.call_count for name, route in routes.items()} == counts_after_first


def test_stock_endpoints_require_auth(client):
    assert client.get("/api/search?q=AAPL").status_code == 401
    assert client.get("/api/stocks/AAPL").status_code == 401
    assert client.get("/api/stocks/AAPL/chart").status_code == 401
    assert client.get("/api/stocks/AAPL/news").status_code == 401
    assert client.get("/api/stocks/AAPL/financials").status_code == 401


def test_demo_can_read(client, demo_headers):
    with respx.mock(assert_all_called=False) as mock:
        install_yahoo_mocks(mock)
        response = client.get("/api/stocks/AAPL", headers=demo_headers)
    assert response.status_code == 200, response.text
    assert response.json()["quote"]["symbol"] == "AAPL"

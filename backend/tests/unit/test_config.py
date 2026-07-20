import pytest
from pydantic import ValidationError

from app.config import Settings

BASE_SETTINGS = {
    "DATABASE_URL": "postgresql://user:password@database.test/marketdeck",
    "MARKETDECK_PUBLIC_URL": "https://market-deck.test",
    "MARKETDECK_OIDC_ISSUER_URL": "https://identity.test/application/o/market-deck",
    "MARKETDECK_OIDC_CLIENT_ID": "market-deck-test",
    "MARKETDECK_OIDC_CLIENT_SECRET": "test-client-secret",
    "MARKETDECK_OIDC_STATE_SECRET": "test-state-secret-0123456789abcdef",
}


def _settings(**overrides: str) -> Settings:
    return Settings(**(BASE_SETTINGS | overrides))


@pytest.mark.parametrize(
    "public_url",
    [
        "http://localhost:5173/",
        "http://127.0.0.1:5173/",
        "http://[::1]:5173/",
    ],
)
def test_public_url_allows_http_only_on_explicit_loopback_hosts(public_url: str):
    settings = _settings(MARKETDECK_PUBLIC_URL=public_url)

    assert settings.public_url == public_url.rstrip("/")
    assert settings.secure_cookies is False


@pytest.mark.parametrize(
    "issuer_url",
    [
        "http://localhost:8000/application/o/market-deck/",
        "http://127.0.0.1:8000/application/o/market-deck/",
        "http://[::1]:8000/application/o/market-deck/",
    ],
)
def test_oidc_issuer_allows_http_only_on_explicit_loopback_hosts(issuer_url: str):
    settings = _settings(MARKETDECK_OIDC_ISSUER_URL=issuer_url)

    assert settings.oidc_issuer_url == issuer_url.rstrip("/")


@pytest.mark.parametrize(
    ("field", "url"),
    [
        ("MARKETDECK_PUBLIC_URL", "http://market-deck.test"),
        (
            "MARKETDECK_OIDC_ISSUER_URL",
            "http://identity.test/application/o/market-deck",
        ),
    ],
)
def test_auth_urls_require_https_outside_loopback(field: str, url: str):
    with pytest.raises(ValidationError, match="must use HTTPS"):
        _settings(**{field: url})


@pytest.mark.parametrize("field", ["MARKETDECK_PUBLIC_URL", "MARKETDECK_OIDC_ISSUER_URL"])
@pytest.mark.parametrize(
    "url",
    [
        "https://@example.test",
        "https://user:password@example.test",
        "https://example.test?tenant=one",
        "https://example.test#fragment",
        "https://example.test\\@attacker.test",
    ],
)
def test_auth_urls_reject_credentials_queries_and_fragments(field: str, url: str):
    with pytest.raises(
        ValidationError,
        match="must not contain credentials, a query, or a fragment",
    ):
        _settings(**{field: url})


def test_public_url_is_origin_only_but_oidc_issuer_may_have_a_path():
    with pytest.raises(ValidationError, match="must be an origin without a path"):
        _settings(MARKETDECK_PUBLIC_URL="https://market-deck.test/app")

    settings = _settings(
        MARKETDECK_PUBLIC_URL="HTTPS://market-deck.test/",
        MARKETDECK_OIDC_ISSUER_URL="https://identity.test/application/o/market-deck/",
    )

    assert settings.public_url == "https://market-deck.test"
    assert settings.oidc_issuer_url == "https://identity.test/application/o/market-deck"
    assert settings.secure_cookies is True

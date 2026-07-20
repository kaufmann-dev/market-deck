from datetime import UTC, datetime, timedelta
from hashlib import sha256
from urllib.parse import parse_qs, urlsplit

import httpx
import respx
from authlib.integrations.base_client import OAuthError
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from .conftest import PUBLIC_URL

ISSUER_URL = "https://idp.test/application/o/marketdeck"
DISCOVERY_URL = f"{ISSUER_URL}/.well-known/openid-configuration"


def _metadata() -> dict[str, object]:
    return {
        "issuer": ISSUER_URL,
        "authorization_endpoint": f"{ISSUER_URL}/authorize",
        "token_endpoint": f"{ISSUER_URL}/token",
        "jwks_uri": f"{ISSUER_URL}/jwks",
        "end_session_endpoint": f"{ISSUER_URL}/logout",
        "code_challenge_methods_supported": ["S256"],
    }


def _session_hash(headers: dict[str, str]) -> str:
    raw_token = headers["Cookie"].partition("=")[2]
    return sha256(raw_token.encode()).hexdigest()


class CallbackOidcClient:
    def __init__(self, token: dict | None = None, error: OAuthError | None = None):
        self.token = token
        self.error = error

    async def authorize_access_token(self, _request):
        if self.error:
            raise self.error
        return self.token


class LogoutOidcClient:
    def __init__(self):
        self.logout_kwargs = None
        self.validated = False

    async def logout_redirect(self, _request, **kwargs):
        self.logout_kwargs = kwargs
        return RedirectResponse(f"{ISSUER_URL}/logout")

    async def validate_logout_response(self, _request):
        self.validated = True
        return {"post_logout_redirect_uri": f"{PUBLIC_URL}/api/auth/logged-out"}


class FailingLogoutOidcClient:
    async def logout_redirect(self, _request, **_kwargs):
        raise RuntimeError("provider metadata has no logout endpoint")


def test_demo_info(client):
    response = client.get("/api/auth/demo-info")
    assert response.status_code == 200
    assert response.json() == {"demoLogin": True}


def test_oidc_login_uses_authorization_code_pkce_and_nonce(client):
    with respx.mock(assert_all_called=True) as mock:
        mock.get(DISCOVERY_URL).mock(return_value=httpx.Response(200, json=_metadata()))
        response = client.get("/api/auth/login", follow_redirects=False)

    assert response.status_code == 302
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["marketdeck-test"]
    assert query["redirect_uri"] == [f"{PUBLIC_URL}/api/auth/callback"]
    assert set(query["scope"][0].split()) == {"openid", "email", "profile"}
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"][0]
    assert query["state"][0]
    assert query["nonce"][0]
    assert "code_verifier" not in query

    flow_cookie = next(
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith("marketdeck_oidc_flow=")
    ).lower()
    assert "httponly" in flow_cookie
    assert "samesite=lax" in flow_cookie
    assert "max-age=600" in flow_cookie


def test_oidc_client_is_confidential_and_never_requests_refresh_tokens():
    from app.oidc import OIDC_SCOPES, get_oidc_client

    oidc = get_oidc_client()
    assert oidc.client_secret == "test-client-secret"
    assert oidc.client_kwargs["token_endpoint_auth_method"] == "client_secret_basic"
    assert oidc.client_kwargs["code_challenge_method"] == "S256"
    assert OIDC_SCOPES == "openid email profile"
    assert "offline_access" not in OIDC_SCOPES


def test_oidc_callback_creates_admin_session_for_any_admitted_identity(client, monkeypatch):
    fake = CallbackOidcClient(
        {
            "access_token": "discarded-access-token",
            "refresh_token": "discarded-refresh-token",
            "id_token": "retained-id-token",
            "userinfo": {"sub": "new-admin-subject", "email": "second-admin@test.local"},
        }
    )
    monkeypatch.setattr("app.api.auth.get_oidc_client", lambda: fake)

    response = client.get("/api/auth/callback?code=code&state=state", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == f"{PUBLIC_URL}/"
    app_cookie = next(
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith("marketdeck_session=")
    ).lower()
    assert "httponly" in app_cookie
    assert "samesite=lax" in app_cookie
    assert "max-age=604800" in app_cookie

    assert client.get("/api/auth/me").json() == {
        "role": "admin",
        "displayName": "second-admin@test.local",
    }

    from app.db import session_factory
    from app.models import AuthSession

    with session_factory()() as session:
        rows = list(session.scalars(select(AuthSession)))
    assert len(rows) == 1
    assert rows[0].subject == "new-admin-subject"
    assert rows[0].id_token == "retained-id-token"
    assert not hasattr(rows[0], "access_token")
    assert not hasattr(rows[0], "refresh_token")


def test_oidc_callback_rejects_invalid_identity(client, monkeypatch):
    fake = CallbackOidcClient({"id_token": "token", "userinfo": {}})
    monkeypatch.setattr("app.api.auth.get_oidc_client", lambda: fake)
    response = client.get("/api/auth/callback?code=code&state=state")
    assert response.status_code == 400
    assert response.json() == {"detail": "OIDC provider returned an invalid identity"}


def test_oidc_callback_reports_protocol_error(client, monkeypatch):
    fake = CallbackOidcClient(error=OAuthError(error="access_denied"))
    monkeypatch.setattr("app.api.auth.get_oidc_client", lambda: fake)
    response = client.get("/api/auth/callback?error=access_denied&state=state")
    assert response.status_code == 400
    assert response.json() == {"detail": "OIDC authentication failed"}


def test_demo_login_requires_no_identity_and_sets_anonymous_session(client):
    response = client.post("/api/auth/demo-login", headers={"Origin": PUBLIC_URL})

    assert response.status_code == 200
    assert response.json() == {"role": "demo"}
    assert client.get("/api/auth/me").json() == {"role": "demo"}

    from app.db import session_factory
    from app.models import AuthSession

    with session_factory()() as session:
        auth_session = session.scalar(select(AuthSession))
    assert auth_session is not None
    assert auth_session.role == "demo"
    assert auth_session.subject is None
    assert auth_session.id_token is None


def test_demo_login_rejects_cross_origin_request(client):
    assert client.post("/api/auth/demo-login").status_code == 403
    assert (
        client.post("/api/auth/demo-login", headers={"Origin": "https://attacker.test"}).status_code
        == 403
    )


def test_me_admin(client, admin_headers):
    response = client.get("/api/auth/me", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == {"displayName": "admin@test.local", "role": "admin"}


def test_me_demo_hides_identity(client, demo_headers):
    response = client.get("/api/auth/me", headers=demo_headers)
    assert response.status_code == 200
    assert response.json() == {"role": "demo"}


def test_me_without_cookie(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_ignores_legacy_bearer_token(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401


def test_only_explicit_user_activity_slides_idle_timeout(client, admin_headers):
    from app.db import session_factory
    from app.models import AuthSession

    token_hash = _session_hash(admin_headers)
    earlier = datetime.now(UTC) - timedelta(hours=1)
    with session_factory()() as session:
        auth_session = session.get(AuthSession, token_hash)
        auth_session.last_seen_at = earlier
        session.commit()

    assert client.get("/api/auth/me", headers=admin_headers).status_code == 200
    with session_factory()() as session:
        assert session.get(AuthSession, token_hash).last_seen_at == earlier

    assert client.get("/api/init", headers=admin_headers).status_code == 200
    with session_factory()() as session:
        assert session.get(AuthSession, token_hash).last_seen_at == earlier

    response = client.post(
        "/api/auth/activity",
        headers=admin_headers
        | {
            "x-marketdeck-user-activity": "1",
            "sec-fetch-site": "same-origin",
        },
    )
    assert response.status_code == 204
    with session_factory()() as session:
        assert session.get(AuthSession, token_hash).last_seen_at > earlier


def test_activity_rejects_missing_header_and_cross_origin_requests(client, admin_headers):
    assert client.post("/api/auth/activity", headers=admin_headers).status_code == 403
    assert (
        client.post(
            "/api/auth/activity",
            headers=admin_headers
            | {
                "Origin": "https://attacker.test",
                "x-marketdeck-user-activity": "1",
                "sec-fetch-site": "cross-site",
            },
        ).status_code
        == 403
    )


def test_idle_timeout_requires_login_and_deletes_id_token(client, admin_headers):
    from app.config import SESSION_IDLE_SECONDS
    from app.db import session_factory
    from app.models import AuthSession

    token_hash = _session_hash(admin_headers)
    with session_factory()() as session:
        auth_session = session.get(AuthSession, token_hash)
        auth_session.last_seen_at = datetime.now(UTC) - timedelta(seconds=SESSION_IDLE_SECONDS + 1)
        session.commit()

    assert client.get("/api/init", headers=admin_headers).status_code == 401
    with session_factory()() as session:
        assert session.get(AuthSession, token_hash) is None


def test_absolute_timeout_requires_login(client, admin_headers):
    from app.db import session_factory
    from app.models import AuthSession

    token_hash = _session_hash(admin_headers)
    with session_factory()() as session:
        auth_session = session.get(AuthSession, token_hash)
        auth_session.absolute_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()

    assert client.get("/api/init", headers=admin_headers).status_code == 401
    with session_factory()() as session:
        assert session.get(AuthSession, token_hash) is None


def test_admin_logout_deletes_local_session_and_uses_rp_logout(client, admin_headers, monkeypatch):
    from app.db import session_factory
    from app.models import AuthSession

    fake = LogoutOidcClient()
    monkeypatch.setattr("app.api.auth.get_oidc_client", lambda: fake)
    token_hash = _session_hash(admin_headers)

    response = client.post("/api/auth/logout", headers=admin_headers, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == f"{ISSUER_URL}/logout"
    assert fake.logout_kwargs == {
        "post_logout_redirect_uri": f"{PUBLIC_URL}/api/auth/logged-out",
        "id_token_hint": "test-id-token",
        "client_id": "marketdeck-test",
    }
    assert "max-age=0" in response.headers["set-cookie"].lower()
    with session_factory()() as session:
        assert session.get(AuthSession, token_hash) is None


def test_demo_logout_stays_local(client, demo_headers, monkeypatch):
    fake = LogoutOidcClient()
    monkeypatch.setattr("app.api.auth.get_oidc_client", lambda: fake)

    response = client.post("/api/auth/logout", headers=demo_headers, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == f"{PUBLIC_URL}/"
    assert fake.logout_kwargs is None


def test_admin_logout_stays_local_when_provider_logout_fails(
    client, admin_headers, monkeypatch
):
    from app.db import session_factory
    from app.models import AuthSession

    monkeypatch.setattr("app.api.auth.get_oidc_client", lambda: FailingLogoutOidcClient())
    token_hash = _session_hash(admin_headers)

    response = client.post("/api/auth/logout", headers=admin_headers)

    assert response.status_code == 502
    assert "max-age=0" in response.headers["set-cookie"].lower()
    with session_factory()() as session:
        assert session.get(AuthSession, token_hash) is None


def test_logout_callback_validates_state_and_returns_home(client, monkeypatch):
    fake = LogoutOidcClient()
    monkeypatch.setattr("app.api.auth.get_oidc_client", lambda: fake)
    response = client.get("/api/auth/logged-out?state=logout-state", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"{PUBLIC_URL}/"
    assert fake.validated is True


def test_local_password_auth_routes_are_removed(client, admin_headers):
    assert (
        client.post(
            "/api/auth/login",
            headers={"Origin": PUBLIC_URL},
            json={"email": "admin@test.local", "password": "password"},
        ).status_code
        == 405
    )
    assert client.put("/api/auth/password", headers=admin_headers, json={}).status_code == 405

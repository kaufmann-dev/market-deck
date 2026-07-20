"""Opaque database sessions and authorization dependencies."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, or_
from sqlalchemy.orm import Session

from .config import (
    APP_SESSION_COOKIE,
    SESSION_ABSOLUTE_SECONDS,
    SESSION_IDLE_SECONDS,
    get_settings,
)
from .db import get_session
from .models import AuthSession
from .schemas import CurrentUser

USER_ACTIVITY_PATH = "/api/auth/activity"
USER_ACTIVITY_HEADER = "x-marketdeck-user-activity"
USER_ACTIVITY_HEADER_VALUE = "1"


def _token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _delete_expired_sessions(session: Session, now: datetime) -> None:
    idle_cutoff = now - timedelta(seconds=SESSION_IDLE_SECONDS)
    session.execute(
        delete(AuthSession).where(
            or_(
                AuthSession.absolute_expires_at <= now,
                AuthSession.last_seen_at <= idle_cutoff,
            )
        )
    )


def create_auth_session(
    session: Session,
    *,
    role: str,
    subject: str | None = None,
    display_name: str | None = None,
    id_token: str | None = None,
    replace_token: str | None = None,
    now: datetime | None = None,
) -> str:
    """Create a server-side session and return its one-time raw cookie value."""
    if role not in ("admin", "demo"):
        raise ValueError("Unsupported session role")
    if role == "admin" and (not subject or not id_token):
        raise ValueError("OIDC admin sessions require a subject and ID token")
    if role == "demo" and (subject or id_token):
        raise ValueError("Anonymous demo sessions cannot contain an identity or ID token")

    current_time = now or datetime.now(UTC)
    _delete_expired_sessions(session, current_time)
    if replace_token:
        session.execute(
            delete(AuthSession).where(AuthSession.token_hash == _token_hash(replace_token))
        )

    raw_token = token_urlsafe(32)
    session.add(
        AuthSession(
            token_hash=_token_hash(raw_token),
            role=role,
            subject=subject,
            display_name=display_name,
            id_token=id_token,
            created_at=current_time,
            last_seen_at=current_time,
            absolute_expires_at=current_time + timedelta(seconds=SESSION_ABSOLUTE_SECONDS),
        )
    )
    session.commit()
    return raw_token


def set_session_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        APP_SESSION_COOKIE,
        raw_token,
        max_age=SESSION_ABSOLUTE_SECONDS,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        APP_SESSION_COOKIE,
        httponly=True,
        secure=get_settings().secure_cookies,
        samesite="lax",
        path="/",
    )


def pop_auth_session(session: Session, raw_token: str | None) -> AuthSession | None:
    auth_session = load_auth_session(session, raw_token)
    if auth_session:
        session.delete(auth_session)
        session.commit()
    return auth_session


def load_auth_session(session: Session, raw_token: str | None) -> AuthSession | None:
    if not raw_token:
        return None
    return session.get(AuthSession, _token_hash(raw_token))


def require_same_origin(request: Request) -> None:
    if request.headers.get("origin") != get_settings().public_url:
        raise HTTPException(403, "Invalid request origin")


def require_user_activity_request(request: Request) -> None:
    if (
        request.method != "POST"
        or request.url.path != USER_ACTIVITY_PATH
        or request.headers.get(USER_ACTIVITY_HEADER) != USER_ACTIVITY_HEADER_VALUE
    ):
        raise HTTPException(403, "Invalid activity request")
    require_same_origin(request)
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site not in (None, "same-origin"):
        raise HTTPException(403, "Invalid activity request")


def _resolve_current_user(
    request: Request,
    session: Session,
    *,
    touch_idle_timeout: bool,
) -> CurrentUser:
    raw_token = request.cookies.get(APP_SESSION_COOKIE)
    if not raw_token:
        raise HTTPException(401, "Not authenticated")

    auth_session = session.get(AuthSession, _token_hash(raw_token))
    if not auth_session:
        raise HTTPException(401, "Not authenticated")

    now = datetime.now(UTC)
    idle_expires_at = auth_session.last_seen_at + timedelta(seconds=SESSION_IDLE_SECONDS)
    if now >= auth_session.absolute_expires_at or now >= idle_expires_at:
        session.delete(auth_session)
        session.commit()
        raise HTTPException(401, "Session expired")

    if request.method not in ("GET", "HEAD", "OPTIONS"):
        require_same_origin(request)

    if touch_idle_timeout and request.method not in ("HEAD", "OPTIONS"):
        auth_session.last_seen_at = now
        session.commit()

    return CurrentUser(role=auth_session.role, display_name=auth_session.display_name)


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> CurrentUser:
    return _resolve_current_user(request, session, touch_idle_timeout=False)


def touch_current_user_activity(
    request: Request,
    session: Session = Depends(get_session),
) -> CurrentUser:
    require_user_activity_request(request)
    return _resolve_current_user(request, session, touch_idle_timeout=True)


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(403, "Read-only account. Write operations require admin privileges.")
    return current_user

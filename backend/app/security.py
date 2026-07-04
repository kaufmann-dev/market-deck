"""Password hashing and JWT authentication."""
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import JWT_ALGORITHM, JWT_TTL_SECONDS, get_settings
from .db import get_session
from .models import User
from .schemas import CurrentUser


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Non-bcrypt hash (e.g. the demo user's "disabled" sentinel) can never match.
        return False


def create_access_token(subject: str, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=JWT_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=JWT_ALGORITHM)


def get_current_user(request: Request, session: Session = Depends(get_session)) -> CurrentUser:
    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Not authenticated")

    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(401, "Token expired") from None

    subject = payload.get("sub")
    role = payload.get("role")
    if not subject or role not in ("admin", "demo"):
        raise HTTPException(401, "Token expired")

    if role == "demo":
        user = session.scalars(select(User).where(User.role == "demo").order_by(User.id).limit(1)).first()
    else:
        user = session.scalars(select(User).where(User.email == subject)).first()

    if not user or user.role != role:
        raise HTTPException(401, "Token expired")
    return CurrentUser(email=user.email, role=user.role)


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(403, "Read-only account. Write operations require admin privileges.")
    return current_user

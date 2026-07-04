"""Authentication endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi.util import get_remote_address
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import User
from ..schemas import CurrentUser, LoginRequest, PasswordChangeRequest
from ..security import create_access_token, get_current_user, hash_password, require_admin, verify_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth")


@router.get("/demo-info")
def demo_info(session: Session = Depends(get_session)):
    session.execute(text("SELECT 1"))
    return {"demoLogin": True}


@router.post("/login")
def login(request: Request, body: LoginRequest, session: Session = Depends(get_session)):
    user = session.scalars(select(User).where(User.email == body.email)).first()

    if not user or user.role == "demo" or not verify_password(body.password, user.password_hash):
        logger.warning("failed login: email=%s ip=%s", body.email, get_remote_address(request))
        raise HTTPException(401, "Invalid email or password")

    token = create_access_token(user.email, user.role)
    return {"token": token, "email": user.email, "role": user.role}


@router.post("/demo-login")
def demo_login(request: Request, session: Session = Depends(get_session)):
    user = session.scalars(select(User).where(User.role == "demo").order_by(User.id).limit(1)).first()

    if not user:
        logger.warning("failed demo login: demo user missing ip=%s", get_remote_address(request))
        raise HTTPException(503, "Demo login is temporarily unavailable")

    token = create_access_token("demo", user.role)
    return {"token": token, "role": user.role}


@router.get("/me")
def me(current_user: CurrentUser = Depends(get_current_user)):
    if current_user.role == "demo":
        return {"role": current_user.role}
    return {"email": current_user.email, "role": current_user.role}


@router.put("/password")
def change_password(
    body: PasswordChangeRequest,
    current_user: CurrentUser = Depends(require_admin),
    session: Session = Depends(get_session),
):
    user = session.scalars(select(User).where(User.email == current_user.email)).first()
    if not user or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    session.execute(
        update(User)
        .where(User.email == current_user.email)
        .values(password_hash=hash_password(body.new_password))
    )
    session.commit()
    return {"ok": True}

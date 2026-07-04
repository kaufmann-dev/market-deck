"""Pydantic request/response models."""
from pydantic import BaseModel


class CurrentUser(BaseModel):
    email: str
    role: str


class LoginRequest(BaseModel):
    email: str
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class SettingUpdate(BaseModel):
    value: str


class WatchlistCreate(BaseModel):
    slug: str
    name: str
    short_name: str
    category: str = "Other"
    description: str = ""
    currency: str = "USD"
    show_tag: bool = True


class WatchlistUpdate(BaseModel):
    name: str | None = None
    short_name: str | None = None
    category: str | None = None
    description: str | None = None
    currency: str | None = None
    show_tag: bool | None = None


class TickerCreate(BaseModel):
    symbol: str
    name: str
    tag: str
    currency: str = "USD"


class TickerUpdate(BaseModel):
    symbol: str | None = None
    name: str | None = None
    tag: str | None = None
    currency: str | None = None


class TagUpdate(BaseModel):
    tag: str | None = None
    bg: str
    text: str
    border: str

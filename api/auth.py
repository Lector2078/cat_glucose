import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, HTTPException, Response, status


SESSION_COOKIE = "cat_glucose_session"
SESSION_TTL_HOURS = 24

_sessions: dict[str, datetime] = {}


def _get_credentials() -> tuple[str, str]:
    return (
        os.getenv("HOUSEHOLD_USERNAME", "household"),
        os.getenv("HOUSEHOLD_PASSWORD", "change_this_password"),
    )


def issue_session(response: Response) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    _sessions[token] = expires_at
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=SESSION_TTL_HOURS * 3600,
    )
    return token


def verify_credentials(username: str, password: str) -> bool:
    expected_username, expected_password = _get_credentials()
    return username == expected_username and password == expected_password


def require_auth(session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> None:
    if session_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    expiry = _sessions.get(session_token)
    if not expiry or expiry < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

"""Single-user password auth backed by a signed session cookie.

There is exactly one user, so there is no user table: a password in the
environment, compared in constant time, and a signed cookie afterwards.
"""

from __future__ import annotations

import hmac
import os
import secrets

from fastapi import HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE_NAME = "familia_session"
MAX_AGE = 60 * 60 * 24 * 30  # 30 days

PASSWORD = os.environ.get("FAMILIA_PASSWORD", "")
SECRET_KEY = os.environ.get("FAMILIA_SECRET_KEY", "")

if not SECRET_KEY:
    # Ephemeral key: every restart logs you out. Fine locally, wrong in prod,
    # which is why the deploy docs make you set it.
    SECRET_KEY = secrets.token_urlsafe(32)

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="familia-session")


def password_is_set() -> bool:
    return bool(PASSWORD)


def check_password(candidate: str) -> bool:
    if not PASSWORD:
        return False
    return hmac.compare_digest(candidate.encode(), PASSWORD.encode())


def issue_session(response: Response) -> None:
    token = _serializer.dumps({"v": 1})
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("FAMILIA_INSECURE_COOKIES") != "1",
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def is_authenticated(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        _serializer.loads(token, max_age=MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return True


def require_auth(request: Request) -> None:
    """FastAPI dependency guarding every /api route."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Not signed in")

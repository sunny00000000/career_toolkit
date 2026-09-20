"""
Deliberately simple single-user auth: one shared password from .env,
checked in constant time, backed by a signed session cookie.

This is NOT a multi-account system -- it's a door lock, so that a tool
sitting on a public IP:port isn't wide open to anyone scanning the internet.
"""
import hmac

from fastapi import Request
from fastapi.responses import RedirectResponse

from . import config


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("authenticated"))


def check_password(password: str) -> bool:
    if not config.APP_PASSWORD:
        # No password configured -- fail open so local dev isn't blocked,
        # but config.startup_warnings() already screams about this loudly.
        return True
    return hmac.compare_digest(password, config.APP_PASSWORD)


def require_login(request: Request):
    """Return a redirect response if not authenticated, else None."""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None

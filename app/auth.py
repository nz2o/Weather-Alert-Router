from fastapi import Header, HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED
from .db import SessionLocal
from .models import ApiKey
import os
import hmac
import hashlib
import time
import base64


def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Missing API key")
    db = SessionLocal()
    try:
        key = db.query(ApiKey).filter(ApiKey.key == x_api_key, ApiKey.active == 1).first()
        if not key:
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    finally:
        db.close()


def verify_admin(x_admin_key: str = Header(None)):
    """Verify admin access using `ADMIN_KEY` environment variable.

    The admin key should be passed in the `X-Admin-Key` header.
    """
    admin_key = os.getenv('ADMIN_KEY')
    if not admin_key:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Admin key not configured")
    if not x_admin_key or x_admin_key != admin_key:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid admin key")


def verify_admin_csrf(x_admin_key: str = Header(None), x_csrf_token: str = Header(None)):
    """Verify admin header plus a HMAC-based CSRF token.

    The CSRF token format is: base64url(hmac_sha256(ADMIN_KEY, ts))|ts
    where `ts` is the UNIX timestamp in seconds. Token is valid if HMAC matches
    and timestamp is within 5 minutes.
    """
    admin_key = os.getenv('ADMIN_KEY')
    if not admin_key:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Admin key not configured")
    if not x_admin_key or x_admin_key != admin_key:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid admin key")

    if not x_csrf_token:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Missing CSRF token")
    try:
        sig_b64, ts_s = x_csrf_token.split('|', 1)
        ts = int(ts_s)
    except Exception:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid CSRF token format")

    # timestamp freshness
    now = int(time.time())
    if abs(now - ts) > 300:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="CSRF token expired")

    # compute expected HMAC
    expected = hmac.new(admin_key.encode('utf-8'), ts_s.encode('utf-8'), hashlib.sha256).digest()
    expected_b64 = base64.urlsafe_b64encode(expected).decode('utf-8').rstrip('=')
    # normalize incoming
    sig_norm = x_csrf_token.split('|', 1)[0].rstrip('=')
    if not hmac.compare_digest(expected_b64, sig_norm):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid CSRF token")

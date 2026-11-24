"""Password hashing, JWT issuing/validation, device credentials and field encryption."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# --------------------------------------------------------------------------
# JWT
# --------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: str, claims: Optional[dict[str, Any]] = None) -> str:
    expire = _now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire, "iat": _now(), "type": "access"}
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str, claims: Optional[dict[str, Any]] = None) -> tuple[str, str, datetime]:
    """Return (token, jti, expires_at)."""
    expire = _now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    jti = secrets.token_urlsafe(24)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": _now(),
        "type": "refresh",
        "jti": jti,
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM), jti, expire


def decode_token(token: str, expected_type: str = "access") -> Optional[dict[str, Any]]:
    """Decode a token. Returns None instead of raising so callers map to 401."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Device credentials (GPS ingest)
# --------------------------------------------------------------------------
def generate_device_key() -> str:
    return "sw_" + secrets.token_urlsafe(settings.DEVICE_TOKEN_BYTES)


def hash_device_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def verify_device_key(raw_key: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_device_key(raw_key), stored_hash)


# --------------------------------------------------------------------------
# Field-level encryption for PII (licence numbers, phone numbers)
# --------------------------------------------------------------------------
_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.FIELD_ENCRYPTION_KEY
        if not key:
            # Derive a stable key from the application secret so the feature still
            # works in development. Production should set FIELD_ENCRYPTION_KEY.
            digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
            key = base64.urlsafe_b64encode(digest).decode()
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(token: Optional[str]) -> Optional[str]:
    if not token:
        return token
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Value was stored before encryption was enabled.
        return token


def mask_value(value: Optional[str], keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * (len(value) - keep) + value[-keep:]


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def utcnow() -> datetime:
    return _now()

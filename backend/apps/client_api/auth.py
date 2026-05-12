from __future__ import annotations

"""JWT + password helpers for client_api.

Password storage format (stdlib only — no bcrypt/passlib dependency):
    pbkdf2_sha256$<iter>$<salt_b64>$<hash_b64>

JWT claims:
    sub  : api_users.id (uuid string)
    cid  : api_users.client_id (uuid string or None for super_admin)
    role : 'owner' | 'agent' | 'super_admin'
    iat  : issued-at (epoch)
    exp  : expires-at (epoch)
"""

import base64
import hashlib
import hmac
import secrets
import time
from typing import Any

import jwt

from backend.shared.config import settings

JWT_ALGORITHM = "HS256"
PBKDF2_DIGEST = "sha256"
PBKDF2_ITERATIONS = 200_000
PBKDF2_SALT_BYTES = 16

ROLE_OWNER = "owner"
ROLE_AGENT = "agent"
ROLE_SUPER_ADMIN = "super_admin"
ALL_ROLES = (ROLE_OWNER, ROLE_AGENT, ROLE_SUPER_ADMIN)


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")
    salt = secrets.token_bytes(PBKDF2_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(PBKDF2_DIGEST, password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "$".join(
        [
            f"pbkdf2_{PBKDF2_DIGEST}",
            str(PBKDF2_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(dk).decode("ascii"),
        ]
    )


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not password:
        return False
    try:
        scheme, iter_str, salt_b64, hash_b64 = stored.split("$", 3)
        if not scheme.startswith("pbkdf2_"):
            return False
        digest = scheme.split("_", 1)[1]
        iters = int(iter_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    dk = hashlib.pbkdf2_hmac(digest, password.encode("utf-8"), salt, iters)
    return hmac.compare_digest(dk, expected)


def make_jwt(*, user_id: str, client_id: str | None, role: str) -> tuple[str, int]:
    if role not in ALL_ROLES:
        raise ValueError(f"invalid role: {role}")
    now = int(time.time())
    exp = now + (settings.client_api_jwt_ttl_minutes * 60)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "cid": str(client_id) if client_id else None,
        "role": role,
        "iat": now,
        "exp": exp,
    }
    token = jwt.encode(payload, settings.client_api_jwt_secret, algorithm=JWT_ALGORITHM)
    return token, exp


def decode_jwt(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.client_api_jwt_secret, algorithms=[JWT_ALGORITHM])

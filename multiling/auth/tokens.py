"""Auth tokens — see __init__.py."""
import secrets
import time
from typing import Optional

_tokens: dict = {}

def issue_token(user_id: str, ttl_seconds: int = 3600) -> str:
    token = secrets.token_urlsafe(32)
    _tokens[token] = {
        "user_id": user_id,
        "issued_at": time.time(),
        "expires_at": time.time() + ttl_seconds,
    }
    return token

def validate_token(token: str) -> Optional[dict]:
    info = _tokens.get(token)
    if not info: return None
    if time.time() > info["expires_at"]:
        del _tokens[token]
        return None
    return info

def revoke_token(token: str) -> bool:
    if token in _tokens:
        del _tokens[token]
        return True
    return False

"""auth.tokens — Self-contained bearer-token store.

Each issued token carries: subject, scope, TTL, optional reuse-count.
Tokens are opaque random strings; binding is by in-memory dict. Suitable
for single-process services; for distributed settings use a shared cache.
""""
from __future__ import annotations
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TokenInfo:
    user_id: str
    issued_at: float
    expires_at: float
    scope: str = ""
    reuse_count: int = 0
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at


class TokenStore:
    def __init__(self) -> None:
        self._tokens: Dict[str, TokenInfo] = {}

    def issue(
        self,
        user_id: str,
        ttl_seconds: int = 3600,
        scope: str = "",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        self._tokens[token] = TokenInfo(
            user_id=user_id,
            issued_at=now,
            expires_at=now + ttl_seconds,
            scope=scope,
            metadata=dict(metadata or {}),
        )
        return token

    def validate(self, token: str) -> Optional[TokenInfo]:
        info = self._tokens.get(token)
        if not info:
            return None
        if info.expired:
            self._tokens.pop(token, None)
            return None
        info.reuse_count += 1
        return info

    def revoke(self, token: str) -> bool:
        return self._tokens.pop(token, None) is not None

    def purge_expired(self) -> int:
        before = len(self._tokens)
        self._tokens = {k: v for k, v in self._tokens.items() if not v.expired}
        return before - len(self._tokens)

    def list_for_user(self, user_id: str) -> List[str]:
        return [k for k, v in self._tokens.items() if v.user_id == user_id and not v.expired]

    def __len__(self) -> int:
        return len(self._tokens)


_store = TokenStore()
issue_token = _store.issue
validate_token = _store.validate
revoke_token = _store.revoke
purge_expired = _store.purge_expired
list_user_tokens = _store.list_for_user

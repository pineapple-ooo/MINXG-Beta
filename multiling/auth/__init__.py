"""
auth.py - Authentication and Authorization Module

Provides:
  - Permission: Fine-grained permission definitions
  - Role: Role-based access control (RBAC) roles
  - AuthManager: Token-based authentication
  - Authorizer: Permission checking engine
  - SessionAuth: Session-based authentication
""""

import hashlib
import hmac
import secrets
import time
import uuid
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
from functools import wraps


@dataclass
class Permission:
    """A fine-grained permission""""
    resource: str       
    action: str         
    scope: str = "*"    

    def __hash__(self):
        return hash((self.resource, self.action, self.scope))

    def __eq__(self, other):
        return (self.resource == other.resource and
                self.action == other.action and
                self.scope == other.scope)

    def to_dict(self):
        return {"resource": self.resource, "action": self.action, "scope": self.scope}


@dataclass
class Role:
    """RBAC role definition""""
    name: str
    description: str = ""
    permissions: Set[Permission] = field(default_factory=set)
    inherits: List[str] = field(default_factory=list)  
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "name": self.name, "description": self.description,
            "permissions": [p.to_dict() for p in self.permissions],
            "inherits": self.inherits,
        }


class TokenManager:
    """Token generation and validation""""

    def __init__(self, secret_key: str = None, token_expiry: int = 3600):
        self.secret_key = secret_key or secrets.token_hex(32)
        self.token_expiry = token_expiry
        self._tokens: Dict[str, Dict] = {}
        self._revoked: Set[str] = set()

    def generate_token(self, user_id: str, roles: List[str] = None,
                       metadata: Dict = None) -> str:
        """Generate a signed JWT-like token""""
        now = time.time()
        payload = {
            "jti": uuid.uuid4().hex[:16],
            "sub": user_id,
            "roles": roles or [],
            "iat": now,
            "exp": now + self.token_expiry,
            "meta": metadata or {},
        }
        
        header_payload = self._encode_header() + "." + self._encode_payload(payload)
        signature = self._sign(header_payload)
        token = header_payload + "." + signature
        self._tokens[payload["jti"]] = {
            "user_id": user_id, "roles": roles or [],
            "created": now, "expires": now + self.token_expiry,
            "revoked": False,
        }
        return token

    def validate_token(self, token: str) -> Optional[Dict]:
        """Validate a token and return payload if valid""""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header_payload = parts[0] + "." + parts[1]
            signature = parts[2]

            
            expected_sig = self._sign(header_payload)
            if not hmac.compare_digest(signature, expected_sig):
                return None

            payload = self._decode_payload(parts[1])

            
            if time.time() > payload.get("exp", 0):
                return None

            
            jti = payload.get("jti", "")
            if jti in self._revoked:
                return None
            token_info = self._tokens.get(jti)
            if token_info and token_info.get("revoked"):
                return None

            return payload
        except Exception:
            return None

    def revoke_token(self, token: str) -> bool:
        """Revoke a token""""
        payload = self.validate_token(token)
        if payload:
            jti = payload.get("jti", "")
            self._revoked.add(jti)
            if jti in self._tokens:
                self._tokens[jti]["revoked"] = True
            return True
        return False

    def _sign(self, data: str) -> str:
        return hmac.new(
            self.secret_key.encode(), data.encode(), hashlib.sha256
        ).hexdigest()

    def _encode_header(self) -> str:
        import base64
        header = {"alg": "HS256", "typ": "JWT"}
        return base64.urlsafe_b64encode(
            str(header).encode()
        ).decode().rstrip("=")

    def _encode_payload(self, payload: Dict) -> str:
        import base64
        return base64.urlsafe_b64encode(
            str(payload).encode()
        ).decode().rstrip("=")

    def _decode_payload(self, encoded: str) -> Dict:
        import base64, json
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += "=" * padding
        return eval(base64.urlsafe_b64decode(encoded).decode())


class Authorizer:
    """Permission checking engine with role inheritance""""

    def __init__(self):
        self._roles: Dict[str, Role] = {}
        self._user_roles: Dict[str, List[str]] = defaultdict(list)

    def add_role(self, role: Role):
        """Register a role""""
        self._roles[role.name] = role

    def assign_role(self, user_id: str, role_name: str):
        """Assign a role to a user""""
        if role_name in self._roles:
            if role_name not in self._user_roles[user_id]:
                self._user_roles[user_id].append(role_name)

    def remove_role(self, user_id: str, role_name: str):
        """Remove a role from a user""""
        if role_name in self._user_roles[user_id]:
            self._user_roles[user_id].remove(role_name)

    def check_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if user has the specified permission""""
        user_roles = self._user_roles.get(user_id, [])
        checked = set()
        for role_name in user_roles:
            if self._check_role_permission(role_name, permission, checked):
                return True
        return False

    def _check_role_permission(self, role_name: str, permission: Permission,
                               checked: Set[str]) -> bool:
        """Recursively check role and inherited roles""""
        if role_name in checked:
            return False
        checked.add(role_name)

        role = self._roles.get(role_name)
        if not role:
            return False

        
        for perm in role.permissions:
            if self._permission_matches(perm, permission):
                return True

        
        for parent_name in role.inherits:
            if self._check_role_permission(parent_name, permission, checked):
                return True

        return False

    def _permission_matches(self, perm: Permission, required: Permission) -> bool:
        """Check if a permission satisfies the required permission""""
        if perm.resource != required.resource:
            if perm.resource != "*" and required.resource != perm.resource:
                return False
        if perm.action != required.action:
            if perm.action != "*" and required.action != perm.action:
                return False
        
        scope_order = {"own": 1, "team": 2, "global": 3, "*": 4}
        perm_scope = scope_order.get(perm.scope, 0)
        req_scope = scope_order.get(required.scope, 0)
        return perm_scope >= req_scope

    def get_user_permissions(self, user_id: str) -> List[Permission]:
        """Get all permissions for a user""""
        perms = set()
        for role_name in self._user_roles.get(user_id, []):
            self._collect_permissions(role_name, perms, set())
        return list(perms)

    def _collect_permissions(self, role_name: str, perms: Set[Permission],
                             visited: Set[str]):
        if role_name in visited:
            return
        visited.add(role_name)
        role = self._roles.get(role_name)
        if not role:
            return
        perms.update(role.permissions)
        for parent in role.inherits:
            self._collect_permissions(parent, perms, visited)


class SessionAuth:
    """Session-based authentication manager""""

    def __init__(self, token_manager: TokenManager = None):
        self.token_manager = token_manager or TokenManager()
        self._sessions: Dict[str, Dict] = {}
        self._user_sessions: Dict[str, List[str]] = defaultdict(list)

    def create_session(self, user_id: str, metadata: Dict = None) -> str:
        """Create a new session and return session ID""""
        session_id = secrets.token_urlsafe(32)
        token = self.token_manager.generate_token(user_id, metadata=metadata)
        now = time.time()
        self._sessions[session_id] = {
            "user_id": user_id,
            "token": token,
            "created": now,
            "last_active": now,
            "metadata": metadata or {},
            "valid": True,
        }
        self._user_sessions[user_id].append(session_id)
        return session_id

    def validate_session(self, session_id: str) -> Optional[Dict]:
        """Validate a session and return session info""""
        session = self._sessions.get(session_id)
        if not session or not session["valid"]:
            return None
        
        payload = self.token_manager.validate_token(session["token"])
        if not payload:
            session["valid"] = False
            return None
        session["last_active"] = time.time()
        return session

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session""""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session["valid"] = False
            self.token_manager.revoke_token(session["token"])
            return True
        return False

    def invalidate_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user""""
        count = 0
        for sid in self._user_sessions.get(user_id, []):
            if sid in self._sessions and self._sessions[sid]["valid"]:
                self._sessions[sid]["valid"] = False
                count += 1
        return count

    def cleanup_expired(self, max_age_seconds: float = 86400) -> int:
        """Remove expired sessions""""
        now = time.time()
        expired = [
            sid for sid, sess in self._sessions.items()
            if sess["valid"] and (now - sess["last_active"]) > max_age_seconds
        ]
        for sid in expired:
            self._sessions[sid]["valid"] = False
        return len(expired)

    def get_active_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s["valid"])




def create_default_roles() -> Dict[str, Role]:
    """Create default RBAC roles""""
    return {
        "admin": Role(
            name="admin",
            description="System administrator with full access",
            permissions={
                Permission("tool", "execute", "*"),
                Permission("session", "manage", "*"),
                Permission("config", "modify", "*"),
                Permission("user", "manage", "*"),
                Permission("data", "*", "*"),
            },
        ),
        "developer": Role(
            name="developer",
            description="Developer with tool execution and data read access",
            permissions={
                Permission("tool", "execute", "own"),
                Permission("data", "read", "team"),
                Permission("data", "write", "own"),
                Permission("session", "read", "own"),
            },
            inherits=["viewer"],
        ),
        "viewer": Role(
            name="viewer",
            description="Read-only access",
            permissions={
                Permission("data", "read", "team"),
                Permission("session", "read", "own"),
            },
        ),
    }


def auth_required(permission: str):
    """Decorator to require authentication with specific permission""""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, '_auth_manager') or not hasattr(self, '_current_user'):
                raise PermissionError("Auth system not initialized")
            resource, action = permission.split(":", 1) if ":" in permission else (permission, "execute")
            perm = Permission(resource=resource, action=action)
            if not self._auth_manager.check_permission(self._current_user, perm):
                raise PermissionError(
                    "Permission denied: {} on {}".format(action, resource)
                )
            return func(self, *args, **kwargs)
        return wrapper
    return decorator
"""
"""
from __future__ import annotations
from typing import Dict
import re
import hashlib
import hmac
import base64
import json as _json
from minxg.base import BaseWorker, tool


class SecurityToolsWorker(BaseWorker):
    worker_id = "security_tools"
    version = "1.0.0"

    @tool(description="Check password strength (0-4)", category="password")
    async def password_strength(self, password: str) -> Dict:
        score = 0
        checks = []
        if len(password) >= 8:
            score += 1
            checks.append("length>=8")
        if re.search(r'[A-Z]', password):
            score += 1
            checks.append("uppercase")
        if re.search(r'[a-z]', password):
            score += 1
            checks.append("lowercase")
        if re.search(r'[0-9]', password):
            score += 1
            checks.append("digit")
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 1
            checks.append("special")
        levels = {0: "very_weak", 1: "weak", 2: "fair", 3: "strong", 4: "very_strong", 5: "very_strong"}
        return {"score": score, "level": levels[min(score, 5)], "checks": checks, "length": len(password)}

    @tool(description="Generate secure token", category="generate")
    async def generate_token(self, length: int = 32, style: str = "hex") -> Dict:
        import secrets
        if style == "hex":
            token = secrets.token_hex(length)
        elif style == "urlsafe":
            token = secrets.token_urlsafe(length)
        elif style == "alphanumeric":
            import string
            alphabet = string.ascii_letters + string.digits
            token = ''.join(secrets.choice(alphabet) for _ in range(length))
        else:
            token = secrets.token_hex(length)
        return {"token": token, "length": len(token), "style": style, "bits": length * 8}

    @tool(description="Parse JWT (decode header/payload only)", category="jwt")
    async def jwt_decode(self, token: str) -> Dict:
        parts = token.split(".")
        if len(parts) != 3:
            return {"error": "not a valid JWT (expected 3 parts)"}
        def _decode(part):
            padded = part + "=" * (-len(part) % 4)
            try:
                return _json.loads(base64.urlsafe_b64decode(padded).decode())
            except Exception:
                return {"raw": part}
        header = _decode(parts[0])
        payload = _decode(parts[1])
        return {"header": header, "payload": payload, "signature_present": len(parts[2]) > 0,
                "algorithm": header.get("alg", "unknown") if isinstance(header, dict) else "unknown"}

    @tool(description="Sanitize input: remove XSS/SQL injection chars", category="sanitize")
    async def sanitize_input(self, text: str, mode: str = "html") -> Dict:
        import html
        if mode == "html":
            safe = html.escape(text)
        elif mode == "sql":
            safe = text.replace("'", "''").replace("\\", "\\\\")
        elif mode == "shell":
            import shlex
            safe = shlex.quote(text)
        elif mode == "alphanumeric":
            safe = re.sub(r'[^a-zA-Z0-9_\- ]', '', text)
        else:
            safe = text
        changed = safe != text
        return {"sanitized": safe, "changed": changed, "mode": mode, "original_length": len(text)}

    @tool(description="CORS header configuration advice", category="web")
    async def cors_config(self, origin: str = "*", methods: str = "GET,POST,PUT,DELETE",
                           max_age: int = 86400) -> Dict:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": methods,
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Max-Age": str(max_age),
            "nginx": f"add_header 'Access-Control-Allow-Origin' '{origin}' always;",
        }

    @tool(description="Content Security Policy header generation", category="web")
    async def csp_header(self, default_src: str = "'self'", script_src: str = "'self'",
                          style_src: str = "'self'") -> Dict:
        csp = f"default-src {default_src}; script-src {script_src}; style-src {style_src}; img-src *; font-src 'self'; connect-src 'self' https:"
        return {"content_security_policy": csp,
                "header": f"add_header Content-Security-Policy \"{csp}\" always;"}

    @tool(description="Rate limiting configuration advice", category="api")
    async def rate_limit_config(self, requests: int = 100, period_sec: int = 60) -> Dict:
        return {
            "limit": requests, "period_seconds": period_sec,
            "nginx": f"limit_req_zone $binary_remote_addr zone=mylimit:10m rate={requests}r/m; limit_req zone=mylimit burst=20 nodelay;",
            "express": f"app.use(rateLimit({{ windowMs: {period_sec*1000}, max: {requests} }}));",
        }

    @tool(description="Security headers checklist", category="audit")
    async def security_headers_checklist(self) -> Dict:
        return {
            "required_headers": [
            ],
            "check_command": "curl -I https://yoursite.com | grep -iE '(content-security|x-frame|x-content|strict-transport|referrer|permissions)'",
        }

    @tool(description="Hash verification", category="verify")
    async def checksum(self, text: str, algorithm: str = "sha256") -> Dict:
        algos = {"md5": hashlib.md5, "sha1": hashlib.sha1, "sha256": hashlib.sha256, "sha512": hashlib.sha512}
        fn = algos.get(algorithm)
        if not fn:
            return {"error": f"unknown algorithm: {algorithm}"}
        h = fn(text.encode()).hexdigest()
        return {"checksum": h, "algorithm": algorithm, "length": len(h)}

    @tool(description="Generate .gitignore template", category="config")
    async def gitignore_security(self) -> Dict:
        content = """# Secrets & Credentials
.env
*.pem
*.key
*.p12
*.pfx
credentials.json
service-account.json
secrets.yml
config/credentials.yml.enc

.env.local
.env.production
*.token

private/
sensitive/
backup/
*.bak"""
        return {"gitignore": content, "category": "security"}

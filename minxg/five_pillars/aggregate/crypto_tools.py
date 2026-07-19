"""
py_workers.crypto_tools - Encoding/Decoding & Format Conversion
Approximately 16 tools: MD5/SHA, HMAC, Base64/Hex/URL, Random, UUID
Performance-critical operations use C++ via minxg_core.
"""

from __future__ import annotations
import hashlib
import hmac
import base64
import uuid
import secrets
import string
import binascii
from typing import Dict
from minxg.base import BaseWorker, tool


try:
    from multiling.minxg_core import (
        sha256 as _cpp_sha256, sha512 as _cpp_sha512,
        hmac_sha256 as _cpp_hmac_sha256, secure_random as _cpp_secure_random,
        pbkdf2_sha256 as _cpp_pbkdf2, hex_encode as _cpp_hex_encode,
        base64_encode as _cpp_base64_encode, base64_decode as _cpp_base64_decode,
    )
    _HAS_CPP = True
except ImportError:
    _HAS_CPP = False


class CryptoToolsWorker(BaseWorker):
    facade_alias = "crypto_tools"
    worker_id = "crypto_tools"
    tier = "code"  # v0.18.0 three-tier classification
    version = "0.17.1"

    @tool(description="MD5 hash", category="hash")
    async def md5(self, text: str) -> Dict:
        return {"hash": hashlib.md5(text.encode()).hexdigest(), "algorithm": "MD5"}

    @tool(description="SHA-256 hash", category="hash")
    async def sha256(self, text: str) -> Dict:
        try:
            if _HAS_CPP:
                result = _cpp_sha256(text.encode())
                h = result.hex()
            else:
                h = hashlib.sha256(text.encode()).hexdigest()
            return {"hash": h, "algorithm": "SHA-256"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="SHA-512 hash", category="hash")
    async def sha512(self, text: str) -> Dict:
        try:
            if _HAS_CPP:
                result = _cpp_sha512(text.encode())
                h = result.hex()
            else:
                h = hashlib.sha512(text.encode()).hexdigest()
            return {"hash": h, "algorithm": "SHA-512"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="SHA-1 hash", category="hash")
    async def sha1(self, text: str) -> Dict:
        return {"hash": hashlib.sha1(text.encode()).hexdigest(), "algorithm": "SHA-1"}

    @tool(description="BLAKE2b hash", category="hash")
    async def blake2b(self, text: str) -> Dict:
        return {"hash": hashlib.blake2b(text.encode()).hexdigest(), "algorithm": "BLAKE2b"}

    @tool(description="HMAC-SHA256", category="hash")
    async def hmac_sha256(self, text: str, key: str) -> Dict:
        try:
            if _HAS_CPP:
                result = _cpp_hmac_sha256(key.encode(), text.encode())
                h = result.hex()
            else:
                h = hmac.new(key.encode(), text.encode(), hashlib.sha256).hexdigest()
            return {"hash": h, "algorithm": "HMAC-SHA256"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Base64 encode", category="encode")
    async def base64_encode(self, text: str) -> Dict:
        try:
            if _HAS_CPP:
                encoded = _cpp_base64_encode(text.encode()).decode("ascii")
            else:
                encoded = base64.b64encode(text.encode()).decode("ascii")
            return {"encoded": encoded, "algorithm": "base64"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Base64 decode", category="decode")
    async def base64_decode(self, encoded: str) -> Dict:
        try:
            if _HAS_CPP:
                decoded = _cpp_base64_decode(encoded.encode()).decode("utf-8", errors="replace")
            else:
                decoded = base64.b64decode(encoded.encode()).decode("utf-8", errors="replace")
            return {"decoded": decoded, "algorithm": "base64"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Base32 encode", category="encode")
    async def base32_encode(self, text: str) -> Dict:
        return {"encoded": base64.b32encode(text.encode()).decode(), "algorithm": "base32"}

    @tool(description="Hex encode", category="encode")
    async def hex_encode(self, text: str) -> Dict:
        try:
            if _HAS_CPP:
                encoded = _cpp_hex_encode(text.encode())
            else:
                encoded = text.encode().hex()
            return {"encoded": encoded, "algorithm": "hex"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Hex decode", category="decode")
    async def hex_decode(self, encoded: str) -> Dict:
        try:
            return {"decoded": bytes.fromhex(encoded).decode(), "algorithm": "hex"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="URL encode", category="encode")
    async def url_encode(self, text: str) -> Dict:
        import urllib.parse
        return {"encoded": urllib.parse.quote(text), "algorithm": "url"}

    @tool(description="URL decode", category="decode")
    async def url_decode(self, encoded: str) -> Dict:
        import urllib.parse
        return {"decoded": urllib.parse.unquote(encoded), "algorithm": "url"}

    @tool(description="Generate UUID v4", category="generate")
    async def uuid_v4(self) -> Dict:
        u = str(uuid.uuid4())
        return {"uuid": u, "version": 4}

    @tool(description="Generate random string", category="generate")
    async def random_string(self, length: int = 32, charset: str = "alphanumeric") -> Dict:
        if _HAS_CPP:
            try:
                raw = _cpp_secure_random(length)
                if charset == "alphanumeric":
                    chars = string.ascii_letters + string.digits
                elif charset == "alpha":
                    chars = string.ascii_letters
                elif charset == "numeric":
                    chars = string.digits
                elif charset == "hex":
                    chars = string.hexdigits.lower()
                elif charset == "password":
                    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
                else:
                    chars = string.ascii_letters + string.digits
                
                import base64 as _b64
                b64 = _b64.b64encode(raw).decode("ascii")
                result = ""
                for c in b64:
                    if c not in "+/=" and len(result) < length:
                        result += c
                result = (result * ((length // len(result)) + 1))[:length]
                return {"random": result, "length": length, "charset": charset}
            except Exception:
                pass
        sets = {
            "alphanumeric": string.ascii_letters + string.digits,
            "alpha": string.ascii_letters,
            "numeric": string.digits,
            "hex": string.hexdigits,
            "password": string.ascii_letters + string.digits + "!@#$%^&*()",
        }
        chars = sets.get(charset, sets["alphanumeric"])
        result = "".join(secrets.choice(chars) for _ in range(length))
        return {"random": result, "length": length, "charset": charset}

    @tool(description="Hash file by path + content", category="hash")
    async def hash_file(self, path: str, algorithm: str = "sha256") -> Dict:
        algos = {"md5": hashlib.md5, "sha1": hashlib.sha1, "sha256": hashlib.sha256, "sha512": hashlib.sha512}
        fn = algos.get(algorithm)
        if not fn:
            return {"error": f"unsupported algorithm: {algorithm}", "available": list(algos.keys())}
        try:
            h = fn()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return {"hash": h.hexdigest(), "algorithm": algorithm, "path": path}
        except Exception as e:
            return {"error": str(e)}

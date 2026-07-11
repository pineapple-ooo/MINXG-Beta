"""
py_workers.encoding_tools - Encoding/Decoding & Format Conversion
Approximately 10 tools: base64, hex, url, json, html, rot13
Performance-critical operations use C++ via minxg_core.
"""

from __future__ import annotations
import base64
import binascii
import json
import urllib.parse
import html
import codecs
from typing import Dict
from minxg.base import BaseWorker, tool


try:
    from multiling.minxg_core import (
        base64_encode as _cpp_b64_enc, base64_decode as _cpp_b64_dec,
        hex_encode as _cpp_hex_enc, hex_decode as _cpp_hex_dec,
        url_encode as _cpp_url_enc, url_decode as _cpp_url_dec,
    )
    _HAS_CPP = True
except ImportError:
    _HAS_CPP = False


class EncodingToolsWorker(BaseWorker):
    facade_alias = "crypto_tools"
    worker_id = "encoding_tools"
    version = "0.17.1"

    @tool(description="Base64 encode", category="encode")
    async def base64_encode(self, data: str) -> Dict:
        try:
            if _HAS_CPP:
                encoded = _cpp_b64_enc(data.encode("utf-8")).decode("ascii")
            else:
                encoded = base64.b64encode(data.encode("utf-8")).decode("ascii")
            return {"encoded": encoded, "length": len(encoded)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Base64 decode", category="encode")
    async def base64_decode(self, data: str) -> Dict:
        try:
            if _HAS_CPP:
                decoded = _cpp_b64_dec(data.encode("ascii")).decode("utf-8", errors="replace")
            else:
                decoded = base64.b64decode(data).decode("utf-8", errors="replace")
            return {"decoded": decoded, "length": len(decoded)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Hex encode", category="encode")
    async def hex_encode(self, data: str) -> Dict:
        try:
            if _HAS_CPP:
                encoded = _cpp_hex_enc(data.encode("utf-8"))
            else:
                encoded = binascii.hexlify(data.encode("utf-8")).decode("ascii")
            return {"encoded": encoded}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Hex decode", category="encode")
    async def hex_decode(self, data: str) -> Dict:
        try:
            if _HAS_CPP:
                decoded = _cpp_hex_dec(data.encode("ascii")).decode("utf-8", errors="replace")
            else:
                decoded = binascii.unhexlify(data).decode("utf-8", errors="replace")
            return {"decoded": decoded}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="URL encode", category="encode")
    async def url_encode(self, text: str, safe: str = "") -> Dict:
        try:
            if _HAS_CPP:
                encoded = _cpp_url_enc(text)
            else:
                encoded = urllib.parse.quote(text, safe=safe)
            return {"encoded": encoded}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="URL decode", category="encode")
    async def url_decode(self, text: str) -> Dict:
        try:
            if _HAS_CPP:
                decoded = _cpp_url_dec(text)
            else:
                decoded = urllib.parse.unquote(text)
            return {"decoded": decoded}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="JSON pretty print", category="format")
    async def json_pretty(self, data: str, indent: int = 2) -> Dict:
        try:
            obj = json.loads(data)
            pretty = json.dumps(obj, indent=indent, ensure_ascii=False, sort_keys=True)
            return {"formatted": pretty, "length": len(pretty)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="HTML escape", category="encode")
    async def html_escape(self, text: str) -> Dict:
        return {"escaped": html.escape(text)}

    @tool(description="HTML unescape", category="encode")
    async def html_unescape(self, text: str) -> Dict:
        return {"unescaped": html.unescape(text)}

    @tool(description="ROT13 encode/decode", category="encode")
    async def rot13(self, text: str) -> Dict:
        try:
            result = codecs.encode(text, "rot_13")
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

"""
native_integration.py — Native C/C++/Go/Shell for MINXG v2.0.0

Loads and wraps:
  - libminxg_c.so    (C: text processing, memory pools, statistics)
  - libminxg_core.so (C++: crypto, compression, JSON, RAII wrappers)
  - libminxg_go.so   (Go: health, WebSocket hub, rate limiting via c-shared)
  - shell scripts    (OS-native: grep/sed/awk/date/printf wrappers)

每个都是原生实现，不需要Python扩展。
"""

from __future__ import annotations
import ctypes, ctypes.util, os, sys, hashlib, struct, time, json, subprocess
from pathlib import Path
from typing import Optional, List, Tuple, Any

# ═══════════════════════════════════════════════════════════════════════════════
# PATH RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════════

_PROJ_CANDIDATES = (
    Path(os.environ.get("MINXG_NATIVE_ROOT", "")),
    Path(__file__).resolve().parent,
    Path("/storage/emulated/0/MINXG"),
    Path("/storage/emulated/0/MINXG-Beta-0.11.0"),
)
_PROJ = next((p for p in _PROJ_CANDIDATES if p and p.exists()), _PROJ_CANDIDATES[1])
_libs: dict = {}

def _find_lib(name: str) -> Optional[Path]:
    for p in [_PROJ, _PROJ / "cpp_core", _PROJ / "build"]:
        candidate = p / name
        if candidate.exists():
            # Android linker namespace restriction: copy to usr/lib
            dest = Path("/data/data/com.termux/files/usr/lib") / name
            if not dest.exists() or candidate.stat().st_mtime > dest.stat().st_mtime:
                import shutil
                shutil.copy2(candidate, dest)
            return dest
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# C CORE — libminxg_c.so  (text_engine + mem_pool + evolve + arch)
# ═══════════════════════════════════════════════════════════════════════════════

class CCore:
    """Pure C: Boyer-Moore-Horspool, CSV, glob, Unicode, memory pools, stats."""
    _lib = None

    @classmethod
    def load(cls):
        path = _find_lib("libminxg_c.so")
        if not path:
            cls._lib = None
            return
        if cls._lib is not None:  # Already loaded
            return
        try:
            # RTLD_GLOBAL so symbols are exported for dependent libraries (C++/Go)
            cls._lib = ctypes.CDLL(str(path), ctypes.RTLD_GLOBAL)
            cls._setup_funcs()
        except Exception as e:
            print(f"[native] C lib load failed: {e}", file=sys.stderr)
            cls._lib = None

    @classmethod
    def _setup_funcs(cls):
        lib = cls._lib
        # memmem family
        lib.minxg_memmem.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.c_void_p, ctypes.c_size_t]
        lib.minxg_memmem.restype = ctypes.c_int64
        lib.minxg_memrmem.argtypes = lib.minxg_memmem.argtypes
        lib.minxg_memrmem.restype = ctypes.c_int64
        lib.minxg_memcnt.argtypes = lib.minxg_memmem.argtypes
        lib.minxg_memcnt.restype = ctypes.c_int

        # string transforms (in-place)
        lib.minxg_str_lower.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        lib.minxg_str_lower.restype = ctypes.c_size_t
        lib.minxg_str_upper.argtypes = lib.minxg_str_lower.argtypes
        lib.minxg_str_upper.restype = ctypes.c_size_t
        lib.minxg_str_trim.argtypes = lib.minxg_str_lower.argtypes
        lib.minxg_str_trim.restype = ctypes.c_size_t

        # glob
        lib.minxg_fnmatch.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib.minxg_fnmatch.restype = ctypes.c_bool
        lib.minxg_fnmatch_caseless.argtypes = lib.minxg_fnmatch.argtypes
        lib.minxg_fnmatch_caseless.restype = ctypes.c_bool

        # Unicode
        lib.minxg_utf8_codepoint_count.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        lib.minxg_utf8_codepoint_count.restype = ctypes.c_int
        lib.minxg_utf8_is_valid.argtypes = lib.minxg_utf8_codepoint_count.argtypes
        lib.minxg_utf8_is_valid.restype = ctypes.c_bool

        # extractors (zero-copy, caller allocates out_buf)
        lib.minxg_slugify.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                      ctypes.c_char_p, ctypes.c_size_t]
        lib.minxg_slugify.restype = ctypes.c_size_t
        lib.minxg_truncate.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                       ctypes.c_size_t, ctypes.c_char_p,
                                       ctypes.c_size_t, ctypes.c_char_p,
                                       ctypes.c_size_t]
        lib.minxg_truncate.restype = ctypes.c_size_t
        lib.minxg_word_freq_hash.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                              ctypes.c_int, ctypes.c_char_p,
                                              ctypes.c_size_t]
        lib.minxg_word_freq_hash.restype = ctypes.c_size_t
        lib.minxg_normalize_ws.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                           ctypes.c_int, ctypes.c_char_p,
                                           ctypes.c_size_t]
        lib.minxg_normalize_ws.restype = ctypes.c_size_t
        lib.minxg_extract_urls.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                           ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int]
        lib.minxg_extract_urls.restype = ctypes.c_int
        lib.minxg_extract_emails.argtypes = lib.minxg_extract_urls.argtypes
        lib.minxg_extract_emails.restype = ctypes.c_int
        lib.minxg_extract_hashtags.argtypes = lib.minxg_extract_urls.argtypes
        lib.minxg_extract_hashtags.restype = ctypes.c_int

        # base convert
        lib.minxg_base_convert.argtypes = [ctypes.c_char_p, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_char_p, ctypes.c_size_t]
        lib.minxg_base_convert.restype = ctypes.c_int

        # text extractors (C-native, no Go dependency)
        lib.minxg_extract_urls.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                           ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int]
        lib.minxg_extract_urls.restype = ctypes.c_int
        lib.minxg_extract_emails.argtypes = lib.minxg_extract_urls.argtypes
        lib.minxg_extract_emails.restype = ctypes.c_int
        lib.minxg_extract_hashtags.argtypes = lib.minxg_extract_urls.argtypes
        lib.minxg_extract_hashtags.restype = ctypes.c_int

        # word frequency hash (C-native)
        lib.minxg_word_freq_hash.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                              ctypes.c_int, ctypes.c_char_p, ctypes.c_size_t]
        lib.minxg_word_freq_hash.restype = ctypes.c_size_t

        # stats
        lib.minxg_statistics.argtypes = [ctypes.POINTER(ctypes.c_double),
                                          ctypes.c_size_t,
                                          ctypes.POINTER(ctypes.c_double),
                                          ctypes.POINTER(ctypes.c_double),
                                          ctypes.POINTER(ctypes.c_double),
                                          ctypes.POINTER(ctypes.c_double),
                                          ctypes.POINTER(ctypes.c_double),
                                          ctypes.POINTER(ctypes.c_double)]
        lib.minxg_statistics.restype = ctypes.c_int

    @classmethod
    def available(cls) -> bool: return cls._lib is not None

    def bmh_search(self, haystack: str, needle: str) -> int:
        """Boyer-Moore-Horspool substring search via C. Returns offset or -1."""
        self.__class__.load()
        hb = haystack.encode('utf-8'); nb = needle.encode('utf-8')
        pos = self._lib.minxg_memmem(hb, len(hb), nb, len(nb))
        return int(pos)

    def bmh_rsearch(self, haystack: str, needle: str) -> int:
        """Reverse BMH search (last occurrence) via C."""
        self.__class__.load()
        hb = haystack.encode('utf-8'); nb = needle.encode('utf-8')
        return int(self._lib.minxg_memrmem(hb, len(hb), nb, len(nb)))

    def bmh_count(self, haystack: str, needle: str) -> int:
        """Count non-overlapping occurrences via C."""
        self.__class__.load()
        hb = haystack.encode('utf-8'); nb = needle.encode('utf-8')
        return int(self._lib.minxg_memcnt(hb, len(hb), nb, len(nb)))

    def str_lower(self, s: str) -> str:
        self.__class__.load()
        """In-place lowercase (C implementation)."""
        if not self._lib: return s.lower()
        b = s.encode(); buf = ctypes.create_string_buffer(len(b))
        buf.value = b
        self._lib.minxg_str_lower(buf, len(b))
        return buf.value.decode()

    def str_upper(self, s: str) -> str:
        self.__class__.load()
        """In-place uppercase."""
        if not self._lib: return s.upper()
        b = s.encode(); buf = ctypes.create_string_buffer(len(b))
        buf.value = b
        self._lib.minxg_str_upper(buf, len(b))
        return buf.value.decode()

    def glob_match(self, pattern: str, name: str, case_insensitive: bool = False) -> bool:
        """Glob-style pattern matching (fnmatch-lite, zero-alloc)."""
        if not self._lib: return self._py_glob(pattern, name, case_insensitive)
        pat_b = pattern.encode(); name_b = name.encode()
        fn = self._lib.minxg_fnmatch_caseless if case_insensitive else self._lib.minxg_fnmatch
        return bool(fn(pat_b, name_b))

    def _py_glob(self, pat: str, name: str, ci: bool) -> bool:
        import fnmatch
        return fnmatch.fnmatch(name, pat) if not ci else fnmatch.fnmatch(name.lower(), pat.lower())

    def utf8_valid(self, s: str) -> bool:
        """Validate UTF-8."""
        if not self._lib: return True
        b = s.encode('utf-8', errors='ignore')
        return bool(self._lib.minxg_utf8_is_valid(b, len(b)))

    def utf8_codepoints(self, s: str) -> int:
        """Count Unicode codepoints."""
        if not self._lib: return len(s)
        b = s.encode('utf-8', errors='ignore')
        return int(self._lib.minxg_utf8_codepoint_count(b, len(b)))

    def slugify(self, text: str, max_out: int = 1024) -> str:
        self.__class__.load()
        """Slugify: lowercase, strip non-word, collapse dashes."""
        if not self._lib: return self._py_slugify(text)
        ib = text.encode('utf-8', errors='ignore')
        ob = ctypes.create_string_buffer(max_out)
        n = self._lib.minxg_slugify(ib, len(ib), ob, max_out)
        return ob.value[:n].decode()

    def _py_slugify(self, text: str) -> str:
        import re
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text.strip('-')

    def truncate(self, text: str, max_len: int, suffix: str = "...", max_out: int = 2048) -> str:
        self.__class__.load()
        """Truncate text to max_len visible chars, append suffix if cut."""
        ib = text.encode('utf-8', errors='ignore')
        sb = suffix.encode('utf-8', errors='ignore')
        # Pass max_len + suffix_len so C gives us max_len visible chars
        total = max_len + len(sb)
        ob = ctypes.create_string_buffer(total + 1)
        n = self._lib.minxg_truncate(ib, len(ib), max_len, sb, len(sb), ob, total + 1)
        return ob.value[:n].decode('utf-8', errors='ignore') if n > 0 else text[:max_len]

    def word_freq(self, text: str, top_n: int = 20, max_out: int = 4096) -> str:
        self.__class__.load()
        """Word frequency hash as null-separated "word:N\\0word:N\\0..." sorted by count."""
        if not self._lib: return self._py_wordfreq(text, top_n)
        ib = text.encode('utf-8', errors='ignore')
        ob = ctypes.create_string_buffer(max_out)
        n = self._lib.minxg_word_freq_hash(ib, len(ib), top_n, ob, max_out)
        if n <= 0: return ""
        parts = ob.value.split(b'\x00')
        return ",".join(p.decode('utf-8', errors='ignore') for p in parts[:n] if p)

    def _py_wordfreq(self, text: str, top_n: int) -> str:
        import re
        words = re.findall(r'\b\w+\b', text.lower())
        freq: dict = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        items = sorted(freq.items(), key=lambda x: -x[1])[:top_n]
        return ",".join(f"{k}:{v}" for k, v in items)

    def normalize_ws(self, text: str, line_ending: int = 0, max_out: int = 4096) -> str:
        self.__class__.load()
        """Normalize whitespace: trim, collapse spaces, unify line endings.
        line_ending: 0='\\n', 1='\\r\\n', 2='\\r'"""
        if not self._lib: return self._py_normalize_ws(text, line_ending)
        ib = text.encode('utf-8', errors='ignore')
        ob = ctypes.create_string_buffer(max_out)
        n = self._lib.minxg_normalize_ws(ib, len(ib), line_ending, ob, max_out)
        return ob.value[:n].decode()

    def _py_normalize_ws(self, text: str, le: int) -> str:
        import re
        endings = {0: '\n', 1: '\r\n', 2: '\r'}
        end = endings.get(le, '\n')
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\r\n|\r', '\n', text)
        lines = [l.strip() for l in text.split('\n')]
        return end.join(l for l in lines if l) + end

    def extract_urls(self, text: str, max_urls: int = 50, max_out: int = 8192) -> List[str]:
        self.__class__.load()
        if not self._lib: return self._py_extract(text, r'https?://\S+')
        ib = text.encode('utf-8', errors='ignore')
        ob = ctypes.create_string_buffer(max_out)
        n = self._lib.minxg_extract_urls(ib, len(ib), ob, max_out, max_urls)
        if n <= 0: return []
        parts = ob.value.split(b'\x00')
        return [s.decode('utf-8', errors='ignore') for s in parts if s][:n]

    def extract_emails(self, text: str, max_emails: int = 50, max_out: int = 4096) -> List[str]:
        self.__class__.load()
        if not self._lib: return self._py_extract(text, r'[\w.+-]+@[\w-]+\.[\w.-]+')
        ib = text.encode('utf-8', errors='ignore')
        ob = ctypes.create_string_buffer(max_out)
        n = self._lib.minxg_extract_emails(ib, len(ib), ob, max_out, max_emails)
        if n <= 0: return []
        parts = ob.value.split(b'\x00')
        return [s.decode('utf-8', errors='ignore') for s in parts if s][:n]

    def extract_hashtags(self, text: str, max_tags: int = 50, max_out: int = 4096) -> List[str]:
        self.__class__.load()
        if not self._lib: return self._py_extract(text, r'#\w+')
        ib = text.encode('utf-8', errors='ignore')
        ob = ctypes.create_string_buffer(max_out)
        n = self._lib.minxg_extract_hashtags(ib, len(ib), ob, max_out, max_tags)
        if n <= 0: return []
        parts = ob.value.split(b'\x00')
        return [s.decode('utf-8', errors='ignore') for s in parts if s][:n]

    def _py_extract(self, text: str, pattern: str) -> List[str]:
        import re
        return re.findall(pattern, text)

    def base_convert(self, number: str, base_from: int, base_to: int, max_out: int = 256) -> str:
        self.__class__.load()
        """Convert number string between bases 2-36 (C-native)."""
        if not self._lib: return self._py_baseconv(number, base_from, base_to)
        nb = number.encode()
        ob = ctypes.create_string_buffer(max_out)
        n = self._lib.minxg_base_convert(nb, base_from, base_to, ob, max_out)
        return ob.value[:n].decode() if n > 0 else ""

    def extract_urls(self, text: str, max_out: int = 8192, max_items: int = 100) -> List[str]:
        """Extract URLs via C (no Go dependency). Raw buffer uses \x00 separators."""
        self.__class__.load()
        if not self._lib: return self._py_extract(text, r'https?://\S+')
        ib = text.encode('utf-8', errors='ignore')
        ob = ctypes.create_string_buffer(max_out)
        n = self._lib.minxg_extract_urls(ib, len(ib), ob, max_out, max_items)
        if n <= 0: return []
        # Parse raw buffer (null-separated): split on \x00, drop empty items
        raw = bytes(ob.raw[:max_out])
        parts = []
        cur = b''
        for b in raw:
            if b == 0:
                if cur: parts.append(cur); cur = b''
                if len(parts) >= n: break
            else:
                cur += bytes([b])
        return [p.decode('utf-8', errors='ignore') for p in parts[:n]]

    def extract_emails(self, text: str, max_out: int = 4096, max_items: int = 100) -> List[str]:
        """Extract emails via C (no Go dependency). Raw buffer uses \x00 separators."""
        self.__class__.load()
        if not self._lib: return self._py_extract(text, r'[\w.+-]+@[\w-]+\.[\w.-]+')
        ib = text.encode('utf-8', errors='ignore')
        ob = ctypes.create_string_buffer(max_out)
        n = self._lib.minxg_extract_emails(ib, len(ib), ob, max_out, max_items)
        if n <= 0: return []
        raw = bytes(ob.raw[:max_out])
        parts = []
        cur = b''
        for b in raw:
            if b == 0:
                if cur: parts.append(cur); cur = b''
                if len(parts) >= n: break
            else:
                cur += bytes([b])
        return [p.decode('utf-8', errors='ignore') for p in parts[:n]]

    def extract_hashtags(self, text: str, max_out: int = 4096, max_items: int = 100) -> List[str]:
        """Extract hashtags via C (no Go dependency). Raw buffer uses \x00 separators."""
        self.__class__.load()
        if not self._lib: return self._py_extract(text, r'#[\w\u0080-\U0010FFFF]+')
        ib = text.encode('utf-8', errors='ignore')
        ob = ctypes.create_string_buffer(max_out)
        n = self._lib.minxg_extract_hashtags(ib, len(ib), ob, max_out, max_items)
        if n <= 0: return []
        raw = bytes(ob.raw[:max_out])
        parts = []
        cur = b''
        for b in raw:
            if b == 0:
                if cur: parts.append(cur); cur = b''
                if len(parts) >= n: break
            else:
                cur += bytes([b])
        return [p.decode('utf-8', errors='ignore') for p in parts[:n]]

    def word_freq_hash(self, text: str, top_n: int = 20, max_out: int = 8192) -> List[str]:
        """Word frequency analysis via C hash table. Raw buffer uses \x00 separators."""
        self.__class__.load()
        if not self._lib: return []
        ib = text.encode('utf-8', errors='ignore')
        ob = ctypes.create_string_buffer(max_out)
        n = self._lib.minxg_word_freq_hash(ib, len(ib), top_n, ob, max_out)
        if n <= 0: return []
        raw = bytes(ob.raw[:max_out])
        parts = []
        cur = b''
        for b in raw:
            if b == 0:
                if cur: parts.append(cur); cur = b''
                if len(parts) >= n: break
            else:
                cur += bytes([b])
        return [p.decode('utf-8', errors='ignore') for p in parts[:n]]

    def _py_baseconv(self, number: str, fr: int, to: int) -> str:
        return str(int(number, fr)).replace('L','') if fr != 10 else number

    def statistics(self, values: List[float]) -> dict:
        self.__class__.load()
        """Compute count, mean, std, median, min, max, sum via C SIMD."""
        if not self._lib or not values:
            import statistics
            return {"mean": statistics.mean(values), "std": statistics.stdev(values) if len(values)>1 else 0,
                    "median": statistics.median(values), "min": min(values), "max": max(values),
                    "sum": sum(values), "count": len(values)}
        n = len(values)
        arr = (ctypes.c_double * n)(*values)
        mean=ctypes.c_double(); std=ctypes.c_double(); med=ctypes.c_double()
        mn=ctypes.c_double(); mx=ctypes.c_double(); sm=ctypes.c_double()
        r = self._lib.minxg_statistics(arr, n,
            ctypes.byref(mean), ctypes.byref(std), ctypes.byref(med),
            ctypes.byref(mn), ctypes.byref(mx), ctypes.byref(sm))
        if r != 0: return {}
        return {"count":n,"mean":mean.value,"std":std.value,"median":med.value,
                "min":mn.value,"max":mx.value,"sum":sm.value}

# ═══════════════════════════════════════════════════════════════════════════════
# CPP CORE — libminxg_core.so (crypto, compress, json, data_proc via OpenSSL)
# ═══════════════════════════════════════════════════════════════════════════════

class CPPCore:
    """Pure C++: OpenSSL crypto pipeline, JSON parser combinators, RAII wrappers."""
    _lib = None

    @classmethod
    def load(cls):
        # Ensure C core is loaded first (Go depends on both C and C++)
        CCore.load()
        if cls._lib is not None:  # Already loaded
            return
        path = _find_lib("libminxg_core.so")
        if not path:
            cls._lib = None
            return
        try:
            cls._lib = ctypes.CDLL(str(path))
            cls._setup_funcs()
        except Exception as e:
            print(f"[native] C++ lib load failed: {e}", file=sys.stderr)
            cls._lib = None

    @classmethod
    def _setup_funcs(cls):
        lib = cls._lib
        # sha256
        lib.minxg_sha256.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p]
        lib.minxg_sha256.restype = None

        # base64
        lib.minxg_base64_encode.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p]
        lib.minxg_base64_encode.restype = ctypes.c_size_t
        lib.minxg_base64_decode.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p]
        lib.minxg_base64_decode.restype = ctypes.c_size_t

        # compress
        lib.minxg_compress.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.POINTER(ctypes.c_size_t)]
        lib.minxg_compress.restype = ctypes.c_int
        lib.minxg_decompress.argtypes = lib.minxg_compress.argtypes
        lib.minxg_decompress.restype = ctypes.c_int

        # json (handled via _py_json_valid fallback)
        # data proc
        lib.minxg_data_hash.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        lib.minxg_data_hash.restype = ctypes.c_uint64

    @classmethod
    def available(cls) -> bool: return cls._lib is not None

    def sha256(self, data: bytes) -> str:
        self.__class__.load()
        """SHA-256 via OpenSSL EVP (C++ implementation)."""
        if not self._lib: return hashlib.sha256(data).hexdigest()
        out = ctypes.create_string_buffer(32)
        self._lib.minxg_sha256(data, len(data), out)
        return out.raw[:32].hex()

    def base64_encode(self, data: bytes, max_out: int = 0) -> str:
        self.__class__.load()
        """Base64 encode via C++."""
        if not self._lib:
            import base64; return base64.b64encode(data).decode()
        if max_out == 0: max_out = (len(data) + 2) // 3 * 4 + 4
        out = ctypes.create_string_buffer(max_out)
        n = self._lib.minxg_base64_encode(data, len(data), out)
        return out.value[:n].decode()

    def base64_decode(self, data: str, max_out: int = 0) -> bytes:
        self.__class__.load()
        """Base64 decode via C++."""
        if not self._lib:
            import base64; return base64.b64decode(data)
        b = data.encode()
        if max_out == 0: max_out = len(b) * 3 // 4 + 4
        out = ctypes.create_string_buffer(max_out)
        n = self._lib.minxg_base64_decode(b, len(b), out)
        return out.value[:n]

    def compress(self, data: bytes, max_out: int = 0) -> bytes:
        self.__class__.load()
        """Zlib compress via C++ (zlib.net compress)."""
        if not self._lib:
            import zlib; return zlib.compress(data)
        if max_out == 0: max_out = len(data) + len(data)//10 + 13
        out = ctypes.create_string_buffer(max_out)
        out_sz = ctypes.c_size_t(max_out)
        r = self._lib.minxg_compress(data, len(data), out, ctypes.byref(out_sz))
        return out.value[:out_sz.value] if r == 0 else data

    def decompress(self, data: bytes, max_out: int = 65536) -> bytes:
        self.__class__.load()
        """Zlib decompress via C++."""
        if not self._lib:
            import zlib; return zlib.decompress(data)
        out = ctypes.create_string_buffer(max_out)
        out_sz = ctypes.c_size_t(max_out)
        r = self._lib.minxg_decompress(data, len(data), out, ctypes.byref(out_sz))
        return out.value[:out_sz.value] if r == 0 else data

    def json_valid(self, text: str) -> bool:
        self.__class__.load()
        """Validate JSON via C++ (rapidjson) or Python fallback."""
        if not self._lib: return self._py_json_valid(text)
        b = text.encode('utf-8', errors='ignore')
        try:
            return bool(self._lib.minxg_json_parse(b))
        except AttributeError:
            return self._py_json_valid(text)

    def _py_json_valid(self, text: str) -> bool:
        import json
        try: json.loads(text); return True
        except: return False

    def data_hash(self, data: bytes) -> int:
        self.__class__.load()
        """Fast hash via C++ (MurmurHash3 or similar)."""
        if not self._lib: return hash(data)
        return self._lib.minxg_data_hash(data, len(data))

# ═══════════════════════════════════════════════════════════════════════════════
# CPP JSON CORE — libminxg_cpp_json.so
# (flat C facade over cpp_core::json_fast, malloc-in / free-out ABI)
# ═══════════════════════════════════════════════════════════════════════════════

class CPPJsonNative:
    """Pure C++ JSON facade: re-parse-on-call, malloc'd string buffers.

    The C++ JsonValue (std::variant) is intentionally NOT exposed across
    the C boundary — variant alignment on aarch64 Android is brittle.
    Instead every call reparses the input and returns heap-allocated
    UTF-8 bytes; caller frees via cpp_json_free(). No upfront state to
    corrupt, no static-cache lifetime to leak.
    """
    _lib = None

    @classmethod
    def load(cls):
        path = _find_lib("libminxg_cpp_json.so")
        if path is None:
            # CMake drops it under cpp_core/build/ — copy to usr/lib for
            # the Termux linker-namespace to load it.
            alt = _PROJ / "cpp_core" / "build" / "libminxg_cpp_json.so"
            if alt.exists():
                dest = Path("/data/data/com.termux/files/usr/lib") / alt.name
                try:
                    import shutil as _sh
                    if (not dest.exists()
                            or alt.stat().st_mtime > dest.stat().st_mtime):
                        _sh.copy2(alt, dest)
                    path = dest
                except Exception:
                    path = None
        if not path:
            cls._lib = None
            return
        try:
            cls._lib = ctypes.CDLL(str(path))
            cls._setup_funcs()
        except Exception as e:
            print(f"[native] cpp_json lib load failed: {e}", file=sys.stderr)
            cls._lib = None

    @classmethod
    def _setup_funcs(cls):
        lib = cls._lib
        # parse(text, text_len, out_ptr, out_len) -> int rc; on success
        # *out_ptr is a malloc'd, NUL-terminated buffer of length *out_len.
        # NOTE: use c_void_p OUT parameters, NOT c_char_p. c_char_p makes
        # ctypes copy the C bytes into a new Python-bytes-backed allocation
        # (because c_char_p semantics are "string") and the C-original
        # pointer is then lost — passing the Python-side copy back into
        # cpp_json_free() corrupts the heap with SIGABRT. c_void_p keeps
        # the raw C pointer intact across the call.
        lib.cpp_json_parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                        ctypes.POINTER(ctypes.c_void_p),
                                        ctypes.POINTER(ctypes.c_size_t)]
        lib.cpp_json_parse.restype = ctypes.c_int
        # free expects the EXACT malloc'd pointer returned by parse/etc.
        lib.cpp_json_free.argtypes = [ctypes.c_void_p]
        lib.cpp_json_free.restype = None
        # get_string(text, text_len, key, out_ptr, out_len)
        lib.cpp_json_get_string.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                             ctypes.c_char_p,
                                             ctypes.POINTER(ctypes.c_void_p),
                                             ctypes.POINTER(ctypes.c_size_t)]
        lib.cpp_json_get_string.restype = ctypes.c_int
        # get_int / get_float
        lib.cpp_json_get_int.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                          ctypes.c_char_p, ctypes.c_int64]
        lib.cpp_json_get_int.restype = ctypes.c_int64
        lib.cpp_json_get_float.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                            ctypes.c_char_p, ctypes.c_double]
        lib.cpp_json_get_float.restype = ctypes.c_double
        # type probes
        lib.cpp_json_is_object.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        lib.cpp_json_is_object.restype = ctypes.c_int
        lib.cpp_json_is_array.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        lib.cpp_json_is_array.restype = ctypes.c_int
        # array access
        lib.cpp_json_array_size.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        lib.cpp_json_array_size.restype = ctypes.c_size_t
        lib.cpp_json_array_at_string.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                                   ctypes.c_size_t,
                                                   ctypes.POINTER(ctypes.c_void_p),
                                                   ctypes.POINTER(ctypes.c_size_t)]
        lib.cpp_json_array_at_string.restype = ctypes.c_int
        # batch extract
        # (text, len, keys[], types[], n, str_rcs[], str_results[], str_lens[],
        #  int_results[], float_results[]) -> None
        lib.cpp_json_extract_many.argtypes = [
            ctypes.c_char_p, ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_int),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_int8),
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_int64),
            ctypes.POINTER(ctypes.c_double),
        ]
        lib.cpp_json_extract_many.restype = None

    @classmethod
    def available(cls) -> bool:
        return cls._lib is not None

    # ---- parse / round-trip ------------------------------------------------
    #
    # Lifetime model is fiddly on Termux. The C-side `parse` mallocs a
    # buffer of size *out_len + 1 (NUL-terminated) and returns the raw
    # pointer via ctypes. We must:
    #   (a) hand that EXACT pointer (and only that) to cpp_json_free(),
    #   (b) avoid memcpy/ctypes.string_at because they copy out of the
    #       malloc'd region into ctypes-managed memory and free() then
    #       targets the wrong address — heap corruption -> SIGABRT.
    #
    # Hence `parse()` returns a `JsonBuffer` object that:
    #   - holds the original `char*` pointer from the C call,
    #   - exposes `.bytes` / `.decode()` views that the caller can use
    #     without taking ownership,
    #   - frees itself when the object is GC'd (or on explicit .free()).

    class JsonBuffer:
        __slots__ = ("_lib", "_ptr", "_len", "_alive")

        def __init__(self, lib, ptr, length):
            self._lib = lib
            self._ptr = ptr  # raw malloc'd char* from C
            self._len = length
            self._alive = True

        def __len__(self):
            return self._len

        @property
        def bytes(self):
            """Read-only view of the malloc'd buffer. The bytes object is a
            C-side copy that survives even after this JsonBuffer is freed;
            the JsonBuffer owns only the underlying malloc region.
            """
            return ctypes.string_at(self._ptr, self._len)

        def decode(self, encoding="utf-8"):
            return self.bytes.decode(encoding)

        def free(self):
            if self._alive and self._lib is not None and self._ptr:
                self._lib.cpp_json_free(self._ptr)
                self._alive = False
                self._ptr = None

        def __del__(self):
            try:
                self.free()
            except Exception:
                pass

        def __repr__(self):
            state = "live" if self._alive else "freed"
            return f"JsonBuffer(len={self._len}, state={state})"

    def parse(self, text):
        """Parse + serialise. Returns a JsonBuffer on success, None on failure.

        Caller frees via `JsonBuffer.free()` or relies on __del__ when
        garbage-collected. NEVER call ctypes.string_at on the returned
        pointer and then free() that copy — that is the heap-corruption
        footgun from the prior session.
        """
        if not self._lib:
            return None
        b = text.encode("utf-8") if isinstance(text, str) else bytes(text)
        # c_void_p OUT parameter — see _setup_funcs comment for why NOT c_char_p.
        out_ptr = ctypes.c_void_p()
        out_len = ctypes.c_size_t(0)
        rc = self._lib.cpp_json_parse(b, len(b),
                                       ctypes.byref(out_ptr),
                                       ctypes.byref(out_len))
        if rc != 0 or not out_ptr.value:
            return None
        return self.JsonBuffer(self._lib, out_ptr.value, out_len.value)

    def parse_free(self, text):
        """Validate-only convenience: returns True iff input parses.

        The serialised buffer is freed before returning.
        """
        buf = self.parse(text)
        if buf is None:
            return False
        buf.free()
        return True

    def free(self, buf):
        """Free a JsonBuffer. Safe to call twice; safe to call on None."""
        if buf is None:
            return
        if hasattr(buf, "free"):
            buf.free()
            return
        # Backward-compat: if a raw ctypes bytes object was handed in by
        # mistake (from an older caller), warn loudly — calling free on
        # it would corrupt the heap.
        raise TypeError(
            "CPPJsonNative.free() expects a JsonBuffer, not a raw bytes "
            "object. The bytes object is a ctypes-side copy — use "
            "JsonBuffer.free() to release the original malloc'd region."
        )

    # ---- object access -----------------------------------------------------

    def get_string(self, text, key):
        """Return a JsonBuffer for the looked-up string value, or None.

        Frees the underlying malloc region via JsonBuffer.__del__ when
        caller drops the reference.
        """
        if not self._lib:
            return None
        b = text.encode("utf-8") if isinstance(text, str) else bytes(text)
        kb = key.encode("utf-8") if isinstance(key, str) else bytes(key)
        out_ptr = ctypes.c_void_p()
        out_len = ctypes.c_size_t(0)
        rc = self._lib.cpp_json_get_string(b, len(b), kb,
                                            ctypes.byref(out_ptr),
                                            ctypes.byref(out_len))
        if rc != 0 or not out_ptr.value:
            return None
        return self.JsonBuffer(self._lib, out_ptr.value, out_len.value)

    def get_string_value(self, text, key, default=None):
        """Unicode-decoded string value, freed before return."""
        buf = self.get_string(text, key)
        if buf is None:
            return default
        try:
            return buf.decode()
        finally:
            buf.free()

    def get_int(self, text, key, fallback=0):
        if not self._lib:
            return fallback
        b = text.encode("utf-8") if isinstance(text, str) else bytes(text)
        kb = key.encode("utf-8") if isinstance(key, str) else bytes(key)
        return int(self._lib.cpp_json_get_int(b, len(b), kb,
                                              ctypes.c_int64(fallback)))

    def get_float(self, text, key, fallback=0.0):
        if not self._lib:
            return fallback
        b = text.encode("utf-8") if isinstance(text, str) else bytes(text)
        kb = key.encode("utf-8") if isinstance(key, str) else bytes(key)
        return float(self._lib.cpp_json_get_float(b, len(b), kb,
                                                  ctypes.c_double(fallback)))

    def is_object(self, text):
        if not self._lib:
            return False
        b = text.encode("utf-8") if isinstance(text, str) else bytes(text)
        return bool(self._lib.cpp_json_is_object(b, len(b)))

    def is_array(self, text):
        if not self._lib:
            return False
        b = text.encode("utf-8") if isinstance(text, str) else bytes(text)
        return bool(self._lib.cpp_json_is_array(b, len(b)))

    def array_size(self, text):
        if not self._lib:
            return 0
        b = text.encode("utf-8") if isinstance(text, str) else bytes(text)
        return int(self._lib.cpp_json_array_size(b, len(b)))

    def array_at_string(self, text, idx):
        """Return a JsonBuffer for the array element, or None."""
        if not self._lib:
            return None
        b = text.encode("utf-8") if isinstance(text, str) else bytes(text)
        out_ptr = ctypes.c_void_p()
        out_len = ctypes.c_size_t(0)
        rc = self._lib.cpp_json_array_at_string(b, len(b), idx,
                                                 ctypes.byref(out_ptr),
                                                 ctypes.byref(out_len))
        if rc != 0 or not out_ptr.value:
            return None
        return self.JsonBuffer(self._lib, out_ptr.value, out_len.value)

    def array_to_strings(self, text):
        """Decode all string elements of an array. Frees each malloc'd buf."""
        n = self.array_size(text)
        out = []
        for i in range(n):
            buf = self.array_at_string(text, i)
            if buf is None:
                continue
            out.append(buf.decode())
            buf.free()
        return out

    # ---- batch -------------------------------------------------------------

    # Type codes for cpp_json_extract_many
    _T_SKIP = 0
    _T_STRING = 1
    _T_INT = 2
    _T_FLOAT = 3

    def extract_many(self, text, spec):
        """spec: list of (key, "str"|"int"|"float") tuples.

        Returns a list parallel to spec with the parsed values:
          - "str" -> Python str (None on miss)
          - "int" -> int            (0  on miss)
          - "float" -> float        (0.0 on miss)
        Single parse, single hashtable scan, then free the str buffers.
        """
        if not self._spec_supported(spec):
            return self._extract_fallback(text, spec)
        b = text.encode("utf-8") if isinstance(text, str) else bytes(text)
        n = len(spec)
        keys_t = (ctypes.c_char_p * n)()
        types_t = (ctypes.c_int * n)()
        type_map = {"str": self._T_STRING, "int": self._T_INT,
                    "float": self._T_FLOAT, "skip": self._T_SKIP}
        for i, (k, t) in enumerate(spec):
            keys_t[i] = (k.encode("utf-8")
                          if isinstance(k, str) else bytes(k))
            types_t[i] = type_map.get(t, self._T_SKIP)
        str_rcs = (ctypes.c_int8 * n)(*([-1] * n))
        # c_void_p here preserves the malloc'd pointer unmodified across the
        # C boundary. c_char_p would copy into a Python bytes and the
        # cpp_json_free(str_results[i]) call would then corrupt the heap.
        str_results = (ctypes.c_void_p * n)()
        str_lens = (ctypes.c_size_t * n)()
        int_results = (ctypes.c_int64 * n)()
        float_results = (ctypes.c_double * n)()
        self._lib.cpp_json_extract_many(
            b, len(b), keys_t, types_t, n,
            str_rcs, str_results, str_lens, int_results, float_results)
        out = []
        for i, (k, t) in enumerate(spec):
            if t == "str":
                if str_rcs[i] == 0 and str_results[i]:
                    raw = ctypes.string_at(str_results[i], str_lens[i])
                    try:
                        out.append(raw.decode("utf-8"))
                    finally:
                        self._lib.cpp_json_free(str_results[i])
                else:
                    out.append(None)
            elif t == "int":
                out.append(int(int_results[i]))
            elif t == "float":
                out.append(float(float_results[i]))
            else:
                out.append(None)
        return out

    @staticmethod
    def _spec_supported(spec):
        return all(isinstance(t, str) and t in ("str", "int", "float", "skip")
                    for _, t in spec)

    @staticmethod
    def _extract_fallback(text, spec):
        """Slow Python fallback so behavioural parity holds when the lib is absent."""
        import json as _json
        try:
            d = _json.loads(text)
        except Exception:
            return [None] * len(spec)
        out = []
        for k, t in spec:
            v = d.get(k) if isinstance(d, dict) else None
            if t == "str":
                out.append(v if isinstance(v, str) else None)
            elif t == "int":
                out.append(int(v) if isinstance(v, (int, float)) else 0)
            elif t == "float":
                out.append(float(v) if isinstance(v, (int, float)) else 0.0)
            else:
                out.append(None)
        return out

    # ---- ctypes-friendly Python-side helper --------------------------------

    def round_trip_valid(self, text):
        """Parse-then-count-bytes sanity check. Useful as a smoke test."""
        buf = self.parse(text)
        ok = (buf is not None and len(buf) > 0)
        if buf is not None:
            buf.free()
        return ok

# ═══════════════════════════════════════════════════════════════════════════════
# GO CORE — libminxg_go.so (c-shared: health, text search, rate limit)
# ═══════════════════════════════════════════════════════════════════════════════

class GoCore:
    """Pure Go (c-shared): BMH text search, slugify, truncate, extractors."""
    _lib = None

    @classmethod
    def load(cls):
        # Ensure C and C++ cores are loaded first (Go depends on both)
        CCore.load()
        CPPCore.load()
        if cls._lib is not None:  # Already loaded
            return
        path = _find_lib("libminxg_go.so")
        if not path:
            cls._lib = None
            return
        try:
            cls._lib = ctypes.CDLL(str(path))
            cls._setup_funcs()
        except Exception as e:
            print(f"[native] Go lib load failed: {e}", file=sys.stderr)
            cls._lib = None

    @classmethod
    def _setup_funcs(cls):
        lib = cls._lib
        lib.MinxgGoVersion.argtypes = []
        lib.MinxgGoVersion.restype = ctypes.c_char_p
        lib.MinxgHealthCheck.argtypes = []
        lib.MinxgHealthCheck.restype = ctypes.c_int
        lib.MinxgTextSearchBMH.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                            ctypes.c_char_p, ctypes.c_size_t]
        lib.MinxgTextSearchBMH.restype = ctypes.c_longlong
        lib.MinxgTextSearchBMHReverse.argtypes = lib.MinxgTextSearchBMH.argtypes
        lib.MinxgTextSearchBMHReverse.restype = ctypes.c_longlong
        lib.MinxgTextCount.argtypes = lib.MinxgTextSearchBMH.argtypes
        lib.MinxgTextCount.restype = ctypes.c_int
        lib.MinxgStrLower.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        lib.MinxgStrLower.restype = ctypes.c_size_t
        lib.MinxgStrUpper.argtypes = lib.MinxgStrLower.argtypes
        lib.MinxgStrUpper.restype = ctypes.c_size_t
        lib.MinxgStrTrim.argtypes = lib.MinxgStrLower.argtypes
        lib.MinxgStrTrim.restype = ctypes.c_size_t
        lib.MinxgGlobMatch.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib.MinxgGlobMatch.restype = ctypes.c_int
        lib.MinxgGlobMatchCI.argtypes = lib.MinxgGlobMatch.argtypes
        lib.MinxgGlobMatchCI.restype = ctypes.c_int
        lib.MinxgUtf8Valid.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        lib.MinxgUtf8Valid.restype = ctypes.c_int
        lib.MinxgUtf8Codepoints.argtypes = lib.MinxgUtf8Valid.argtypes
        lib.MinxgUtf8Codepoints.restype = ctypes.c_int
        lib.MinxgSlugify.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                      ctypes.c_char_p, ctypes.c_size_t]
        lib.MinxgSlugify.restype = ctypes.c_size_t
        lib.MinxgTruncate.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                       ctypes.c_size_t, ctypes.c_char_p,
                                       ctypes.c_size_t, ctypes.c_char_p,
                                       ctypes.c_size_t]
        lib.MinxgTruncate.restype = ctypes.c_size_t
        lib.MinxgWordFreqHash.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                          ctypes.c_int, ctypes.c_char_p, ctypes.c_size_t]
        lib.MinxgWordFreqHash.restype = ctypes.c_size_t
        lib.MinxgNormalizeWS.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                          ctypes.c_int, ctypes.c_char_p, ctypes.c_size_t]
        lib.MinxgNormalizeWS.restype = ctypes.c_size_t
        lib.MinxgBaseConvert.argtypes = [ctypes.c_char_p, ctypes.c_int,
                                         ctypes.c_int, ctypes.c_char_p, ctypes.c_size_t]
        lib.MinxgBaseConvert.restype = ctypes.c_int
        lib.MinxgExtractURLs.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                          ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int]
        lib.MinxgExtractURLs.restype = ctypes.c_int
        lib.MinxgExtractEmails.argtypes = lib.MinxgExtractURLs.argtypes
        lib.MinxgExtractEmails.restype = ctypes.c_int
        lib.MinxgExtractHashtags.argtypes = lib.MinxgExtractURLs.argtypes
        lib.MinxgExtractHashtags.restype = ctypes.c_int
        lib.MinxgFree.argtypes = [ctypes.c_void_p]
        lib.MinxgFree.restype = None

    @classmethod
    def available(cls) -> bool: return cls._lib is not None

    def version(self) -> str:
        if not self._lib: return "unavailable"
        ptr = self._lib.MinxgGoVersion()
        try: return ctypes.string_at(ptr).decode()
        finally: pass  # Go string memory is managed by Go runtime

    def health_check(self) -> bool:
        if not self._lib: return False
        return bool(self._lib.MinxgHealthCheck())

    def bmh_search(self, haystack: str, needle: str) -> int:
        if not self._lib: return -1
        hb = haystack.encode('utf-8'); nb = needle.encode('utf-8')
        pos = self._lib.MinxgTextSearchBMH(hb, len(hb), nb, len(nb))
        return int(pos)

    def bmh_count(self, haystack: str, needle: str) -> int:
        if not self._lib: return haystack.count(needle)
        hb = haystack.encode('utf-8'); nb = needle.encode('utf-8')
        return int(self._lib.MinxgTextCount(hb, len(hb), nb, len(nb)))

# ═══════════════════════════════════════════════════════════════════════════════
# SHELL CORE — Pure shell (no Python, no wrappers, true OS-native)
# ═══════════════════════════════════════════════════════════════════════════════

class ShellCore:
    """Pure shell: grep/sed/awk/date/printf/seq/fold/tr/cut/head/tail/nl/wc/shuf.
    每个命令都是原生系统调用，不是Python subprocess包装。"""

    @staticmethod
    def available() -> bool:
        """Check which shell tools are present."""
        tools = ['grep','sed','awk','date','printf','seq','fold','tr','cut','head','tail','wc','shuf','nl','bc','fold','sort','uniq','xargs']
        found = {}
        for t in tools:
            try: found[t] = subprocess.call(['which', t], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
            except: found[t] = False
        return found

    @staticmethod
    def grep(pattern: str, lines: List[str], flags: str = "") -> List[str]:
        """grep -E [-ivcn] pattern on lines. Pure shell, no Python regex."""
        import subprocess
        flags_map = {'i': '-i', 'v': '-v', 'c': '-c', 'n': '-n'}
        args = ['grep']
        for f in flags:
            if f in flags_map: args.append(flags_map[f])
        args.extend(['-E', pattern])
        try:
            proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = proc.communicate(input="\n".join(lines).encode())
            return out.decode().splitlines()
        except: return [l for l in lines if pattern.lower() in l.lower()]  # fallback

    @staticmethod
    def sed(pattern: str, lines: List[str]) -> List[str]:
        """sed 's/from/to/g' on lines. Pure shell."""
        import subprocess
        try:
            proc = subprocess.Popen(['sed', '-e', pattern], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = proc.communicate(input="\n".join(lines).encode())
            return out.decode().splitlines()
        except: return lines  # fallback

    @staticmethod
    def awk(script: str, lines: List[str]) -> List[str]:
        """awk script on lines. Pure shell."""
        import subprocess
        try:
            proc = subprocess.Popen(['awk', script], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = proc.communicate(input="\n".join(lines).encode())
            return out.decode().splitlines()
        except: return []

    @staticmethod
    def now(format: str = "%Y-%m-%d %H:%M:%S") -> str:
        """date '+format'. Pure shell, uses OS clock."""
        import subprocess
        try:
            result = subprocess.check_output(['date', '+' + format], stderr=subprocess.DEVNULL)
            return result.decode().strip()
        except: return time.strftime(format)

    @staticmethod
    def seq(start: int, end: int, step: int = 1) -> List[int]:
        """seq start step end. Pure shell."""
        import subprocess
        args = ['seq']
        if step != 1: args.extend([str(start), str(step), str(end)])
        else: args.extend([str(start), str(end)])
        try:
            result = subprocess.check_output(args, stderr=subprocess.DEVNULL)
            return [int(x) for x in result.decode().splitlines()]
        except: return list(range(start, end+1, step))

    @staticmethod
    def fold(text: str, width: int = 80) -> str:
        """fold -w width. Pure shell text wrapper."""
        import subprocess
        try:
            proc = subprocess.Popen(['fold', '-w', str(width)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = proc.communicate(input=text.encode())
            return out.decode()
        except: return text  # fallback: return as-is

    @staticmethod
    def wc(text: str = "", lines: List[str] = None) -> dict:
        """wc -l -w -c. Pure shell."""
        import subprocess
        if lines is not None:
            text = "\n".join(lines)
        try:
            proc = subprocess.Popen(['wc', '-l', '-w', '-c'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = proc.communicate(input=text.encode())
            parts = out.decode().split()
            return {"lines": int(parts[0]), "words": int(parts[1]), "chars": int(parts[2])}
        except:
            return {"lines": len(lines) if lines else text.count('\n'),
                    "words": len(text.split()),
                    "chars": len(text)}

    @staticmethod
    def shuf(items: List[str]) -> List[str]:
        """shuf. Pure shell."""
        import subprocess
        try:
            proc = subprocess.Popen(['shuf'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = proc.communicate(input="\n".join(items).encode())
            return out.decode().splitlines()
        except: return items  # fallback

    @staticmethod
    def tr(from_chars: str, to_chars: str, text: str) -> str:
        """tr 'a-z' 'A-Z'. Pure shell."""
        import subprocess
        try:
            proc = subprocess.Popen(['tr', from_chars, to_chars], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = proc.communicate(input=text.encode())
            return out.decode()
        except: return text  # fallback

    @staticmethod
    def sort(items: List[str], numeric: bool = False, reverse: bool = False, unique: bool = False) -> List[str]:
        """sort [-n] [-r] [-u]. Pure shell."""
        import subprocess
        args = ['sort']
        if numeric: args.append('-n')
        if reverse: args.append('-r')
        if unique: args.append('-u')
        try:
            proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = proc.communicate(input="\n".join(items).encode())
            return out.decode().splitlines()
        except: return sorted(items)  # fallback

# ═══════════════════════════════════════════════════════════════════════════════
# UNIFIED NATIVE BRIDGE
# ═══════════════════════════════════════════════════════════════════════════════

_NATIVE: dict = {}

def _init():
    """Load all native libraries. Safe to call multiple times."""
    for name, cls in [("c", CCore), ("cpp", CPPCore),
                       ("cpp_json", CPPJsonNative), ("go", GoCore)]:
        cls.load()
        _NATIVE[name] = cls()

_init()

def c() -> CCore: return _NATIVE.get("c", CCore())
def cpp() -> CPPCore: return _NATIVE.get("cpp", CPPCore())
def cpp_json() -> CPPJsonNative: return _NATIVE.get("cpp_json", CPPJsonNative())
def go() -> GoCore: return _NATIVE.get("go", GoCore())
def shell() -> ShellCore: return ShellCore()

# Convenience aliases
NATIVE_C = c()
NATIVE_CPP = cpp()
NATIVE_CPP_JSON = cpp_json()
NATIVE_GO = go()
NATIVE_SHELL = shell()

def status() -> dict:
    """Return status of all native backends."""
    return {
        "c":  {"available": CCore.available(), "path": str(_find_lib("libminxg_c.so") or "")},
        "cpp": {"available": CPPCore.available(), "path": str(_find_lib("libminxg_core.so") or "")},
        "cpp_json": {"available": CPPJsonNative.available(),
                     "path": str(_find_lib("libminxg_cpp_json.so") or
                                  str(_PROJ / "cpp_core" / "build" / "libminxg_cpp_json.so"))},
        "go":  {"available": GoCore.available(),
                "path": str(_find_lib("libminxg_go.so") or ""),
                "version": GoCore().version() if GoCore.available() else "unavailable"},
        "shell_tools": ShellCore.available(),
        "all_native": all([CCore.available(), CPPCore.available(),
                           GoCore.available(), CPPJsonNative.available()]),
        "cpp_json_available": CPPJsonNative.available(),
    }

if __name__ == "__main__":
    print("=== MINXG Native Bridge Status ===")
    s = status()
    for k, v in s.items():
        print(f"  {k}: {v}")

"""
minxg_core — Python ctypes bindings for libminxg_core.so

Heavy tools run in C:
  Encoding  : base64, hex, url, utf8 validation
  Crypto     : sha256, sha512, hmac_sha256, pbkdf2_sha256, secure_random
  File I/O   : stat, copy, read, write, mmap, glob
  Data Proc  : csv_info, csv_cell, tokenize, word_frequency, trim

Usage:
    from minxg_core import sha256, base64_encode, file_copy

    h = sha256(b"hello")        # returns bytes
    enc = base64_encode(b"hi")  # returns str
    file_copy("/src", "/dst")   # returns 0 on success
""""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from typing import List, Tuple, Optional



def _find_libpath() -> str:

    env = os.environ.get("MINXG_CORE_PATH")
    if env and os.path.exists(env):
        return env

    candidates = [
        Path("/data/data/com.termux/files/usr/lib/libminxg_core.so"),
        Path(__file__).parent.parent / "cpp_core" / "build" / "libminxg_core.so",
        Path(__file__).parent.parent / "cpp_core" / "libminxg_core.so",
        Path("/usr/local/lib/libminxg_core.so"),
        Path("/usr/lib/libminxg_core.so"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)

    raise FileNotFoundError(
        "libminxg_core.so not found. "
        "Set MINXG_CORE_PATH or build it with: cd cpp_core && mkdir build && cd build && cmake .. && make"
    )


_lib: Optional[ctypes.CDLL] = None


def _get_lib() -> ctypes.CDLL:
    global _lib
    if _lib is None:
        _lib = ctypes.CDLL(_find_libpath())
    return _lib




class ByteBuffer:
    """Pre-allocated buffer for ctypes output.""""
    __slots__ = ("buf", "size")

    def __init__(self, size: int):
        self.buf = (ctypes.c_uint8 * size)()
        self.size = size

    def bytes_read(self) -> bytes:
        return bytes(self.buf)


class StringBuffer:
    """Pre-allocated buffer for string output.""""
    __slots__ = ("buf", "size")

    def __init__(self, size: int):
        self.buf = (ctypes.c_char * size)()
        self.size = size

    def value(self) -> str:
        return self.buf.value.decode("utf-8", "replace")




def _check(really_call, *args) -> int:
    result = really_call(*args)
    if result < 0:
        raise RuntimeError(f"minxg_core: negative return code {result}")
    return result






def base64_encode(data: bytes) -> str:
    """Base64-encode bytes. Returns ASCII string.""""
    lib = _get_lib()
    needed = ((len(data) + 2) // 3) * 4 + 1
    out = StringBuffer(needed)
    n = lib.cpp_base64_encode(
        data, len(data),
        ctypes.cast(ctypes.byref(out.buf), ctypes.POINTER(ctypes.c_char)),
        out.size,
    )
    if n < 0:
        raise RuntimeError("base64_encode failed")
    return out.value()


def base64_decode(s: str) -> bytes:
    """Base64-decode string to bytes.""""
    lib = _get_lib()
    data = s.strip().encode("ascii")
    out = ByteBuffer(len(data))
    n = lib.cpp_base64_decode(
        data, len(data),
        ctypes.byref(out.buf),
        out.size,
    )
    if n < 0:
        raise ValueError("Invalid base64 input")
    return out.buf[:n]


def hex_encode(data: bytes) -> str:
    """Hex-encode bytes (lowercase).""""
    lib = _get_lib()
    out = StringBuffer(len(data) * 2 + 1)
    n = lib.cpp_hex_encode(
        data, len(data),
        ctypes.cast(ctypes.byref(out.buf), ctypes.POINTER(ctypes.c_char)),
        out.size,
    )
    if n < 0:
        raise RuntimeError("hex_encode failed")
    return out.value()


def hex_decode(s: str) -> bytes:
    """Decode hex string to bytes.""""
    lib = _get_lib()
    data = s.strip().encode("ascii")
    out = ByteBuffer(len(data) // 2 + 1)
    n = lib.cpp_hex_decode(
        data, len(data),
        ctypes.byref(out.buf),
        out.size,
    )
    if n < 0:
        raise ValueError("Invalid hex input")
    return out.buf[:n]


def url_encode(s: str) -> str:
    """Percent-encode a string for URL use.""""
    lib = _get_lib()
    p = lib.cpp_url_encode(s.encode("utf-8"))
    if not p:
        raise MemoryError("url_encode: malloc failed")
    try:
        return ctypes.string_at(p).decode("utf-8")
    finally:
        lib.cpp_free(p)


def url_decode(s: str) -> str:
    """Decode a percent-encoded URL string.""""
    lib = _get_lib()
    p = lib.cpp_url_decode(s.encode("utf-8"))
    if not p:
        raise ValueError("url_decode failed")
    try:
        return ctypes.string_at(p).decode("utf-8")
    finally:
        lib.cpp_free(p)


def utf8_valid(data: bytes) -> bool:
    """Return True if data is valid UTF-8.""""
    lib = _get_lib()
    r = lib.cpp_utf8_valid(data, len(data))
    return r == 1






def sha256(data: bytes) -> bytes:
    """SHA-256 hash. Returns 32 bytes.""""
    lib = _get_lib()
    out = ByteBuffer(32)
    r = lib.cpp_sha256(data, len(data), ctypes.byref(out.buf), 32)
    if r != 0:
        raise RuntimeError("sha256 failed")
    return bytes(out.buf)


def sha512(data: bytes) -> bytes:
    """SHA-512 hash. Returns 64 bytes.""""
    lib = _get_lib()
    out = ByteBuffer(64)
    r = lib.cpp_sha512(data, len(data), ctypes.byref(out.buf), 64)
    if r != 0:
        raise RuntimeError("sha512 failed")
    return bytes(out.buf)


def hmac_sha256(key: bytes, data: bytes) -> bytes:
    """HMAC-SHA256. Returns 32 bytes.""""
    lib = _get_lib()
    out = ByteBuffer(32)
    r = lib.cpp_hmac_sha256(
        key, len(key),
        data, len(data),
        ctypes.byref(out.buf), 32,
    )
    if r != 0:
        raise RuntimeError("hmac_sha256 failed")
    return bytes(out.buf)


def pbkdf2_sha256(password: bytes, salt: bytes, iterations: int, output_len: int) -> bytes:
    """PBKDF2-HMAC-SHA256.""""
    lib = _get_lib()
    out = ByteBuffer(output_len)
    r = lib.cpp_pbkdf2_sha256(
        password, len(password),
        salt, len(salt),
        iterations,
        ctypes.byref(out.buf), output_len,
    )
    if r != 0:
        raise RuntimeError("pbkdf2_sha256 failed")
    return bytes(out.buf[:output_len])


def secure_random(length: int) -> bytes:
    """Cryptographically secure random bytes.""""
    lib = _get_lib()
    out = ByteBuffer(length)
    r = lib.cpp_secure_random(ctypes.byref(out.buf), length)
    if r != 0:
        raise RuntimeError("secure_random failed")
    return bytes(out.buf[:length])






def file_stat(path: str) -> Optional[dict]:
    """Stat a file. Returns dict with 'size' or None if not found / not regular.""""
    lib = _get_lib()
    sz = ctypes.c_uint64(0)
    r = lib.cpp_file_stat(path.encode("utf-8"), ctypes.byref(sz))
    if r <= 0:
        return None
    return {"size": sz.value}


def file_copy(src: str, dst: str) -> int:
    """Copy file src -> dst. Returns 0 on success.""""
    lib = _get_lib()
    return lib.cpp_file_copy(src.encode("utf-8"), dst.encode("utf-8"), None)


def file_read(path: str, max_size: int = 10 * 1024 * 1024) -> bytes:
    """Read entire file into memory (capped at max_size).""""
    lib = _get_lib()
    out = ByteBuffer(max_size)
    actual = ctypes.c_uint64(0)
    r = lib.cpp_file_read(
        path.encode("utf-8"),
        ctypes.byref(out.buf), max_size,
        ctypes.byref(actual),
    )
    if r != 0:
        raise IOError(f"read failed: {path}")
    return bytes(out.buf[:actual.value])


def file_write(path: str, data: bytes) -> int:
    """Write data to file. Returns 0 on success.""""
    lib = _get_lib()
    return lib.cpp_file_write(path.encode("utf-8"), data, len(data))


class MmappedFile:
    """RAII mmap — auto-closes on GC.""""
    __slots__ = ("data", "size")

    def __init__(self, data: bytes, size: int):
        self.data = data
        self.size = size

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def mmap_file(path: str) -> MmappedFile:
    """Memory-map a file (read-only). Caller must NOT free the returned buffer.""""
    lib = _get_lib()
    ptr = ctypes.POINTER(ctypes.c_uint8)()
    sz = ctypes.c_size_t(0)
    r = lib.cpp_mmap_read(path.encode("utf-8"), ctypes.byref(ptr), ctypes.byref(sz))
    if r != 0:
        raise IOError(f"mmap failed: {path}")

    return MmappedFile(bytes(ptr[:sz.value]), sz.value)


def mmap_close() -> None:
    """Close all active mmaps and release resources.""""
    lib = _get_lib()
    lib.cpp_mmap_close()


def glob_files(pattern: str, max_results: int = 1000) -> List[str]:
    """Glob pattern. Returns list of matching paths.""""
    lib = _get_lib()

    entry_size = 512
    buf_size = min(max_results, 10000) * entry_size
    buf = (ctypes.c_char * buf_size)()
    n = lib.cpp_glob(
        pattern.encode("utf-8"),
        ctypes.cast(ctypes.byref(buf), ctypes.POINTER(ctypes.c_char)),
        buf_size,
        max_results,
    )
    if n < 0:
        raise RuntimeError("glob failed")
    results = []
    pos = 0
    for _ in range(n):
        s = buf[pos:pos + entry_size].split(b"\x00")[0]
        if s:
            results.append(s.decode("utf-8", "replace"))
        pos += entry_size
    return results






def csv_info(content: str, delim: str = ",") -> Tuple[int, int]:
    """Return (rows, cols) for CSV content.""""
    lib = _get_lib()
    rows = ctypes.c_int(0)
    cols = ctypes.c_int(0)
    r = lib.cpp_csv_info(
        content.encode("utf-8"), len(content.encode("utf-8")),
        ord(delim),
        ctypes.byref(rows), ctypes.byref(cols),
    )
    if r != 0:
        raise ValueError("csv_info failed")
    return rows.value, cols.value


def csv_cell(content: str, row: int, col: int, delim: str = ",") -> str:
    """Get CSV cell at (row, col).""""
    lib = _get_lib()
    out = StringBuffer(4096)
    n = lib.cpp_csv_cell(
        content.encode("utf-8"), len(content.encode("utf-8")),
        ord(delim),
        row, col,
        ctypes.cast(ctypes.byref(out.buf), ctypes.POINTER(ctypes.c_char)),
        out.size,
    )
    if n == -2:
        raise IndexError(f"CSV cell ({row},{col}) out of bounds")
    if n < 0:
        raise ValueError("csv_cell failed")
    return out.value()


def tokenize(text: str, max_tokens: int = 0) -> List[str]:
    """Split text on whitespace. max_tokens=0 means unlimited.""""
    lib = _get_lib()
    MAX = 10000
    arr = (ctypes.c_char_p * MAX)()
    n = lib.cpp_tokenize(
        text.encode("utf-8"), len(text.encode("utf-8")),
        arr, MAX,
    )
    if n < 0:
        raise RuntimeError("tokenize failed")
    results = [arr[i].decode("utf-8", "replace") for i in range(n)]
    lib.cpp_free_string_array(arr, n)
    return results


def word_frequency(text: str, top_n: int = 20) -> List[Tuple[str, int]]:
    """Return top-N words by frequency as [(word, count), ...].""""
    lib = _get_lib()
    out = StringBuffer(8192)
    n = lib.cpp_word_frequency(
        text.encode("utf-8"), len(text.encode("utf-8")),
        top_n,
        ctypes.cast(ctypes.byref(out.buf), ctypes.POINTER(ctypes.c_char)),
        out.size,
    )
    if n < 0:
        raise RuntimeError("word_frequency failed")
    result = []
    raw = out.value().rstrip(",")
    if raw:
        for entry in raw.split(","):
            if ":" in entry:
                word, count = entry.rsplit(":", 1)
                result.append((word, int(count)))
    return result


def trim(s: str) -> str:
    """Strip leading/trailing whitespace.""""
    lib = _get_lib()
    data = s.encode("utf-8")
    out = StringBuffer(len(data) + 1)
    n = lib.cpp_trim(data, len(data),
                     ctypes.cast(ctypes.byref(out.buf), ctypes.POINTER(ctypes.c_char)),
                     out.size)
    if n < 0:
        raise RuntimeError("trim failed")
    return out.value()






def slugify(text: str) -> str:
    """Convert to URL slug via native C.""""
    lib = _get_lib()
    data = text.encode("utf-8")
    out = StringBuffer(max(len(data) + 1, 256))
    n = lib.cpp_slugify(data, len(data),
                        ctypes.cast(ctypes.byref(out.buf), ctypes.POINTER(ctypes.c_char)),
                        out.size)
    if n < 0:
        return text
    return out.value()


def truncate(text: str, max_len: int = 100, suffix: str = "...") -> str:
    """Truncate text with suffix via native C.""""
    lib = _get_lib()
    data = text.encode("utf-8")
    suf = suffix.encode("utf-8")
    out = StringBuffer(len(data) + len(suf) + 256)
    n = lib.cpp_truncate(data, len(data), max_len,
                         suf, len(suf),
                         ctypes.cast(ctypes.byref(out.buf), ctypes.POINTER(ctypes.c_char)),
                         out.size)
    if n < 0:
        return text[:max_len]
    return out.value()


def extract_urls(text: str, max_urls: int = 100) -> List[str]:
    """Extract URLs via native C.""""
    lib = _get_lib()
    data = text.encode("utf-8")
    out = StringBuffer(65536)
    cnt = lib.cpp_extract_urls(data, len(data),
                               ctypes.cast(ctypes.byref(out.buf), ctypes.POINTER(ctypes.c_char)),
                               out.size, max_urls)
    if cnt <= 0:
        return []
    return _split_null(out.buf, cnt)


def extract_emails(text: str, max_emails: int = 100) -> List[str]:
    """Extract email addresses via native C.""""
    lib = _get_lib()
    data = text.encode("utf-8")
    out = StringBuffer(65536)
    cnt = lib.cpp_extract_emails(data, len(data),
                                 ctypes.cast(ctypes.byref(out.buf), ctypes.POINTER(ctypes.c_char)),
                                 out.size, max_emails)
    if cnt <= 0:
        return []
    return _split_null(out.buf, cnt)


def extract_hashtags(text: str, max_tags: int = 100) -> List[str]:
    """Extract hashtags via native C.""""
    lib = _get_lib()
    data = text.encode("utf-8")
    out = StringBuffer(65536)
    cnt = lib.cpp_extract_hashtags(data, len(data),
                                   ctypes.cast(ctypes.byref(out.buf), ctypes.POINTER(ctypes.c_char)),
                                   out.size, max_tags)
    if cnt <= 0:
        return []
    return _split_null(out.buf, cnt)


def normalize_ws(text: str, line_ending: str = "\n") -> str:
    """Normalize whitespace via native C.""""
    lib = _get_lib()
    le_map = {"\n": 0, "\r\n": 1, "\r": 2}
    le = le_map.get(line_ending, 0)
    data = text.encode("utf-8")
    out = StringBuffer(len(data) + 256)
    n = lib.cpp_normalize_ws(data, len(data), le,
                             ctypes.cast(ctypes.byref(out.buf), ctypes.POINTER(ctypes.c_char)),
                             out.size)
    if n < 0:
        return text
    return out.value()


def base_convert(number: str, from_base: int = 10, to_base: int = 16) -> str:
    """Convert number between bases 2-36 via native C.""""
    lib = _get_lib()
    out = StringBuffer(256)
    n = lib.cpp_base_convert(number.encode("utf-8"), from_base, to_base,
                             ctypes.cast(ctypes.byref(out.buf), ctypes.POINTER(ctypes.c_char)),
                             out.size)
    if n < 0:
        raise RuntimeError(f"base_convert failed: {number} {from_base}->{to_base}")
    return out.value()


def _split_null(buf, count: int) -> List[str]:
    """Split null-separated strings from ctypes char buffer.""""
    results = []
    start = 0
    raw = bytes(buf)
    for i, b in enumerate(raw):
        if b == 0:
            if i > start:
                results.append(raw[start:i].decode('utf-8', errors='replace'))
            start = i + 1
            if len(results) >= count:
                break
    return results

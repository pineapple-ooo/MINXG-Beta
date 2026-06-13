"""
core_native.py — Python ctypes bridge to C/C++ shared libraries.

This module is the single delegation point from Python to native code.
All performance-critical paths in the MINXG system route through here.

Language dispatch rules:
  - SHA-256/512, HMAC, PBKDF2 → C wrapper (OpenSSL native)
  - string search (memmem/memrmem/memcnt) → C Boyer-Moore
  - CSV parsing → C streaming parser
  - JSON parse/serialize → C++ json_fast (via C wrapper)
  - compression → C++ compress (zlib native)
  - file mmap/copy → C POSIX wrappers
  - Go services → Unix socket (protobuf or JSON)
  - Python-only: CLI/TUI shell, AI orchestration, extension loading

Memory ownership:
  - Functions returning allocated strings: caller must free with cpp_free()
  - Functions with pre-allocated output buffers: caller owns the buffer
  - Arena/slab allocations: freed at arena destroy
""""

import ctypes
import os
import sys
import platform
from ctypes import (
    c_uint8, c_size_t, c_int, c_int64, c_uint64,
    c_bool, c_char_p, POINTER, byref, create_string_buffer,
    cast, c_void_p
)
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path



def _find_lib(name: str) -> str:
    """Find a shared library by name, searching build dirs first.
    On Android, copies the library to Termux lib dir to bypass linker namespace restrictions.""""
    base = Path(__file__).resolve().parent.parent
    candidates = [
        base / "build" / name,
        base / "cpp_core" / "build" / name,
        base / "cpp_core" / "build" / f"{name}.so",
        base / "build" / name,
        base / "build" / f"{name}.so",
    ]
    for p in candidates:
        if p.exists():
            src = str(p)
            if platform.system() == "Android" and "/storage/" in src:
                import shutil
                dst = f"/data/data/com.termux/files/usr/lib/{name}"
                try:
                    shutil.copy2(src, dst)
                    return dst
                except Exception:
                    pass
            return src
    return name



_lib = None
_lib_path = None


def _load_lib():
    global _lib, _lib_path
    if _lib is not None:
        return _lib

    system = platform.system()
    if system == "Linux":
        lib_name = "libminxg_core.so"
    elif system == "Android":
        lib_name = "libminxg_core.so"
    elif system == "Darwin":
        lib_name = "libminxg_core.dylib"
    elif system == "Windows":
        lib_name = "minxg_core.dll"
    else:
        raise OSError(f"Unsupported platform: {system}")

    _lib_path = _find_lib(lib_name)
    try:
        _lib = ctypes.CDLL(_lib_path)
    except OSError:
        _lib_path = _find_lib("minxg_core.so")
        _lib = ctypes.CDLL(_lib_path)


    _lib.cpp_free.argtypes = [c_void_p]
    _lib.cpp_free.restype = None

    _lib.cpp_sha256.argtypes = [POINTER(c_uint8), c_size_t,
                                POINTER(c_uint8), c_size_t]
    _lib.cpp_sha256.restype = c_int

    _lib.cpp_sha512.argtypes = [POINTER(c_uint8), c_size_t,
                                POINTER(c_uint8), c_size_t]
    _lib.cpp_sha512.restype = c_int

    _lib.cpp_hmac_sha256.argtypes = [POINTER(c_uint8), c_size_t,
                                     POINTER(c_uint8), c_size_t,
                                     POINTER(c_uint8), c_size_t]
    _lib.cpp_hmac_sha256.restype = c_int

    _lib.cpp_pbkdf2_sha256.argtypes = [POINTER(c_uint8), c_size_t,
                                       POINTER(c_uint8), c_size_t,
                                       c_int,
                                       POINTER(c_uint8), c_size_t]
    _lib.cpp_pbkdf2_sha256.restype = c_int

    _lib.cpp_secure_random.argtypes = [POINTER(c_uint8), c_size_t]
    _lib.cpp_secure_random.restype = c_int

    _lib.cpp_base64_encode.argtypes = [POINTER(c_uint8), c_size_t,
                                       POINTER(ctypes.c_char), c_size_t]
    _lib.cpp_base64_encode.restype = c_int

    _lib.cpp_base64_decode.argtypes = [c_char_p, c_size_t,
                                       POINTER(c_uint8), c_size_t]
    _lib.cpp_base64_decode.restype = c_int

    _lib.cpp_hex_encode.argtypes = [POINTER(c_uint8), c_size_t,
                                    POINTER(ctypes.c_char), c_size_t]
    _lib.cpp_hex_encode.restype = c_int

    _lib.cpp_hex_decode.argtypes = [c_char_p, c_size_t,
                                    POINTER(c_uint8), c_size_t]
    _lib.cpp_hex_decode.restype = c_int

    _lib.cpp_url_encode.argtypes = [c_char_p]
    _lib.cpp_url_encode.restype = c_void_p

    _lib.cpp_url_decode.argtypes = [c_char_p]
    _lib.cpp_url_decode.restype = c_void_p

    _lib.cpp_utf8_valid.argtypes = [c_char_p, c_size_t]
    _lib.cpp_utf8_valid.restype = c_int

    _lib.cpp_file_stat.argtypes = [c_char_p, POINTER(c_uint64)]
    _lib.cpp_file_stat.restype = c_int

    _lib.cpp_file_copy.argtypes = [c_char_p, c_char_p, POINTER(c_uint64)]
    _lib.cpp_file_copy.restype = c_int

    _lib.cpp_file_read.argtypes = [c_char_p, POINTER(c_uint8), c_size_t,
                                   POINTER(c_uint64)]
    _lib.cpp_file_read.restype = c_int

    _lib.cpp_file_write.argtypes = [c_char_p, POINTER(c_uint8), c_size_t]
    _lib.cpp_file_write.restype = c_int

    _lib.cpp_mmap_read.argtypes = [c_char_p,
                                   POINTER(POINTER(c_uint8)),
                                   POINTER(c_size_t)]
    _lib.cpp_mmap_read.restype = c_int

    _lib.cpp_mmap_close.argtypes = []
    _lib.cpp_mmap_close.restype = None

    _lib.cpp_csv_info.argtypes = [c_char_p, c_size_t, c_uint8,
                                  POINTER(c_int), POINTER(c_int)]
    _lib.cpp_csv_info.restype = c_int

    _lib.cpp_csv_cell.argtypes = [c_char_p, c_size_t, c_uint8,
                                  c_int, c_int,
                                  c_char_p, c_size_t]
    _lib.cpp_csv_cell.restype = c_int

    _lib.cpp_tokenize.argtypes = [c_char_p, c_size_t,
                                  POINTER(c_void_p), c_size_t]
    _lib.cpp_tokenize.restype = c_int

    _lib.cpp_free_string_array.argtypes = [POINTER(c_void_p), c_int]
    _lib.cpp_free_string_array.restype = None

    _lib.cpp_word_frequency.argtypes = [c_char_p, c_size_t, c_int,
                                        c_char_p, c_size_t]
    _lib.cpp_word_frequency.restype = c_int

    _lib.cpp_trim.argtypes = [c_char_p, c_size_t, c_char_p, c_size_t]
    _lib.cpp_trim.restype = c_int

    _lib.cpp_slugify.argtypes = [c_char_p, c_size_t, c_char_p, c_size_t]
    _lib.cpp_slugify.restype = c_int

    _lib.cpp_truncate.argtypes = [c_char_p, c_size_t, c_size_t,
                                   c_char_p, c_size_t,
                                   c_char_p, c_size_t]
    _lib.cpp_truncate.restype = c_int

    _lib.cpp_extract_urls.argtypes = [c_char_p, c_size_t,
                                       c_char_p, c_size_t, c_int]
    _lib.cpp_extract_urls.restype = c_int

    _lib.cpp_extract_emails.argtypes = [c_char_p, c_size_t,
                                         c_char_p, c_size_t, c_int]
    _lib.cpp_extract_emails.restype = c_int

    _lib.cpp_extract_hashtags.argtypes = [c_char_p, c_size_t,
                                           c_char_p, c_size_t, c_int]
    _lib.cpp_extract_hashtags.restype = c_int

    _lib.cpp_normalize_ws.argtypes = [c_char_p, c_size_t, c_int,
                                       c_char_p, c_size_t]
    _lib.cpp_normalize_ws.restype = c_int

    _lib.cpp_base_convert.argtypes = [c_char_p, c_int, c_int,
                                       c_char_p, c_size_t]
    _lib.cpp_base_convert.restype = c_int

    _lib.cpp_word_freq_hash.argtypes = [c_char_p, c_size_t, c_int,
                                         c_char_p, c_size_t]
    _lib.cpp_word_freq_hash.restype = c_int

    _lib.cpp_glob.argtypes = [c_char_p, c_char_p, c_size_t, c_int]
    _lib.cpp_glob.restype = c_int

    return _lib


def _ensure_loaded():
    global _lib
    if _lib is None:
        _load_lib()
    return _lib




class NativeError(RuntimeError):
    """Raised when a native call fails.""""



def sha256(data: bytes) -> bytes:
    """Compute SHA-256 via native OpenSSL.""""
    lib = _ensure_loaded()
    out = (c_uint8 * 32)()
    rc = lib.cpp_sha256(
        cast(data, POINTER(c_uint8)), len(data),
        out, 32,
    )
    if rc != 0:
        raise NativeError("sha256 failed")
    return bytes(out)


def sha512(data: bytes) -> bytes:
    """Compute SHA-512 via native OpenSSL.""""
    lib = _ensure_loaded()
    out = (c_uint8 * 64)()
    rc = lib.cpp_sha512(
        cast(data, POINTER(c_uint8)), len(data),
        out, 64,
    )
    if rc != 0:
        raise NativeError("sha512 failed")
    return bytes(out)


def hmac_sha256(key: bytes, data: bytes) -> bytes:
    """Compute HMAC-SHA256 via native OpenSSL.""""
    lib = _ensure_loaded()
    out = (c_uint8 * 32)()
    rc = lib.cpp_hmac_sha256(
        cast(key, POINTER(c_uint8)), len(key),
        cast(data, POINTER(c_uint8)), len(data),
        out, 32,
    )
    if rc != 0:
        raise NativeError("hmac_sha256 failed")
    return bytes(out)


def pbkdf2_sha256(password: bytes, salt: bytes, iterations: int = 100000,
                  key_len: int = 32) -> bytes:
    """Derive key via PBKDF2-HMAC-SHA256.""""
    lib = _ensure_loaded()
    out = (c_uint8 * key_len)()
    rc = lib.cpp_pbkdf2_sha256(
        cast(password, POINTER(c_uint8)), len(password),
        cast(salt, POINTER(c_uint8)), len(salt),
        iterations,
        out, key_len,
    )
    if rc != 0:
        raise NativeError("pbkdf2_sha256 failed")
    return bytes(out)


def secure_random(n_bytes: int) -> bytes:
    """Generate cryptographically secure random bytes.""""
    lib = _ensure_loaded()
    out = (c_uint8 * n_bytes)()
    rc = lib.cpp_secure_random(out, n_bytes)
    if rc != 0:
        raise NativeError("secure_random failed")
    return bytes(out)



def base64_encode(data: bytes) -> str:
    """Base64 encode via native OpenSSL BIO.""""
    lib = _ensure_loaded()
    enc_len = len(data) * 2 + 10
    out = create_string_buffer(enc_len)
    rc = lib.cpp_base64_encode(
        cast(data, POINTER(c_uint8)), len(data),
        out, enc_len,
    )
    if rc < 0:
        raise NativeError("base64_encode failed")
    return out.value.decode() if isinstance(out.value, bytes) else out.value


def base64_decode(encoded: str) -> bytes:
    """Base64 decode via native OpenSSL BIO.""""
    lib = _ensure_loaded()
    enc = encoded.encode() if isinstance(encoded, str) else encoded
    out = (c_uint8 * (len(enc) * 3 // 4 + 4))()
    rc = lib.cpp_base64_decode(
        enc, len(enc),
        out, len(out),
    )
    if rc < 0:
        raise NativeError("base64_decode failed")
    return bytes(out[:rc])


def hex_encode(data: bytes) -> str:
    """Hex encode bytes.""""
    lib = _ensure_loaded()
    out = create_string_buffer(len(data) * 2 + 1)
    rc = lib.cpp_hex_encode(
        cast(data, POINTER(c_uint8)), len(data),
        out, len(out),
    )
    if rc < 0:
        raise NativeError("hex_encode failed")
    return out.value.decode() if isinstance(out.value, bytes) else out.value


def hex_decode(hex_str: str) -> bytes:
    """Hex decode string to bytes.""""
    lib = _ensure_loaded()
    out_len = len(hex_str) // 2
    out = (c_uint8 * out_len)()
    rc = lib.cpp_hex_decode(
        hex_str.encode(), len(hex_str),
        out, out_len,
    )
    if rc < 0:
        raise NativeError("hex_decode failed")
    return bytes(out)


def url_encode(value: str) -> str:
    """URL-encode a string via native C.""""
    lib = _ensure_loaded()
    ptr = lib.cpp_url_encode(value.encode())
    if not ptr:
        raise NativeError("url_encode failed")
    try:
        result = ctypes.string_at(ptr).decode()
        return result
    finally:
        lib.cpp_free(ptr)


def url_decode(encoded: str) -> str:
    """URL-decode a string via native C.""""
    lib = _ensure_loaded()
    ptr = lib.cpp_url_decode(encoded.encode())
    if not ptr:
        raise NativeError("url_decode failed")
    try:
        result = ctypes.string_at(ptr).decode()
        return result
    finally:
        lib.cpp_free(ptr)



def is_valid_utf8(data: bytes) -> bool:
    """Validate UTF-8 via native C.""""
    lib = _ensure_loaded()
    return lib.cpp_utf8_valid(data, len(data)) == 1



def file_stat(path: str) -> Tuple[bool, int]:
    """Check if path is a regular file and get size. Returns (is_file, size).""""
    lib = _ensure_loaded()
    size = c_uint64(0)
    rc = lib.cpp_file_stat(path.encode(), byref(size))
    if rc == 0:
        return (False, 0)
    if rc < 0:
        raise NativeError(f"file_stat failed: {path}")
    return (rc == 1, size.value)


def file_copy(src: str, dst: str) -> int:
    """Copy file src→dst via native C (64KB buffer, POSIX). Returns bytes copied.""""
    lib = _ensure_loaded()
    out_bytes = c_uint64(0)
    rc = lib.cpp_file_copy(src.encode(), dst.encode(), byref(out_bytes))
    if rc != 0:
        raise NativeError(f"file_copy failed: {src} -> {dst}")
    return out_bytes.value


def file_read(path: str, max_size: int = 16 * 1024 * 1024) -> bytes:
    """Read file via native C (POSIX read).""""
    lib = _ensure_loaded()
    out = (c_uint8 * max_size)()
    bytes_read = c_uint64(0)
    rc = lib.cpp_file_read(path.encode(), out, max_size, byref(bytes_read))
    if rc != 0:
        raise NativeError(f"file_read failed: {path}")
    return bytes(out[:bytes_read.value])


def file_write(path: str, data: bytes) -> None:
    """Write file via native C (POSIX write, O_TRUNC).""""
    lib = _ensure_loaded()
    rc = lib.cpp_file_write(path.encode(),
                            cast(data, POINTER(c_uint8)), len(data))
    if rc != 0:
        raise NativeError(f"file_write failed: {path}")


def mmap_read(path: str) -> Tuple[bytes, int]:
    """Memory-map a file read-only. Returns (data_view, size). Caller must call mmap_close().""""
    lib = _ensure_loaded()
    out_ptr = POINTER(c_uint8)()
    out_size = c_size_t(0)
    rc = lib.cpp_mmap_read(path.encode(), byref(out_ptr), byref(out_size))
    if rc != 0:
        raise NativeError(f"mmap_read failed: {path}")
    buf = ctypes.string_at(out_ptr, out_size.value)
    return (buf, out_size.value)


def mmap_close() -> None:
    """Release all mmap mappings.""""
    lib = _ensure_loaded()
    lib.cpp_mmap_close()



def csv_info(data: str, delim: str = ",") -> Tuple[int, int]:
    """Count rows and columns of CSV data.""""
    lib = _ensure_loaded()
    rows = c_int(0)
    cols = c_int(0)
    rc = lib.cpp_csv_info(data.encode(), len(data.encode()),
                          ord(delim).to_bytes(1, 'little')[0],
                          byref(rows), byref(cols))
    if rc != 0:
        raise NativeError("csv_info failed")
    return (rows.value, cols.value)


def csv_cell(data: str, row: int, col: int, delim: str = ",") -> str:
    """Extract a single cell from CSV data.""""
    lib = _ensure_loaded()
    out = create_string_buffer(65536)
    rc = lib.cpp_csv_cell(data.encode(), len(data.encode()),
                          ord(delim).to_bytes(1, 'little')[0],
                          row, col, out, 65536)
    if rc < 0:
        raise NativeError(f"csv_cell failed: row={row} col={col}")
    return out.value.decode() if isinstance(out.value, bytes) else out.value[:rc]



def tokenize(text: str, max_tokens: int = 100000) -> List[str]:
    """Tokenize text by whitespace via native C.""""
    lib = _ensure_loaded()
    arr = (c_void_p * max_tokens)()
    data = text.encode()
    rc = lib.cpp_tokenize(data, len(data), arr, max_tokens)
    if rc < 0:
        raise NativeError("tokenize failed")
    count = rc
    tokens = []
    for i in range(count):
        tokens.append(ctypes.string_at(arr[i]).decode())
    lib.cpp_free_string_array(arr, count)
    return tokens


def word_frequency(text: str, top_n: int = 20) -> List[Tuple[str, int]]:
    """Count word frequencies via native C hash table.""""
    lib = _ensure_loaded()
    out = create_string_buffer(65536)
    data = text.encode()
    rc = lib.cpp_word_frequency(data, len(data), top_n, out, 65536)
    if rc < 0:
        raise NativeError("word_frequency failed")
    result_str = out.value.decode() if isinstance(out.value, bytes) else out.value
    pairs = []
    for entry in result_str.split(","):
        if ":" in entry:
            word, count = entry.rsplit(":", 1)
            pairs.append((word, int(count)))
    return pairs


def trim(text: str) -> str:
    """Trim whitespace from both ends via native C.""""
    lib = _ensure_loaded()
    out = create_string_buffer(len(text.encode()) + 1)
    data = text.encode()
    rc = lib.cpp_trim(data, len(data), out, len(out))
    if rc < 0:
        return text
    return out.value.decode() if isinstance(out.value, bytes) else out.value[:rc]




def slugify(text: str) -> str:
    """Convert to URL slug via native C.""""
    lib = _ensure_loaded()
    data = text.encode()
    out = create_string_buffer(len(data) + 1)
    rc = lib.cpp_slugify(data, len(data), out, len(out))
    if rc < 0:
        return text
    return out.value.decode() if isinstance(out.value, bytes) else out.value[:rc]


def truncate(text: str, max_len: int = 100, suffix: str = "...") -> str:
    """Truncate text with suffix via native C.""""
    lib = _ensure_loaded()
    data = text.encode()
    suf = suffix.encode()
    out = create_string_buffer(len(data) + len(suf) + 1)
    rc = lib.cpp_truncate(data, len(data), max_len, suf, len(suf), out, len(out))
    if rc < 0:
        return text[:max_len]
    return out.value.decode() if isinstance(out.value, bytes) else out.value[:rc]


def extract_urls(text: str, max_urls: int = 100) -> List[str]:
    """Extract URLs via native C. Returns null-separated string.""""
    lib = _ensure_loaded()
    data = text.encode()
    out = create_string_buffer(65536)
    cnt = lib.cpp_extract_urls(data, len(data), out, 65536, max_urls)
    if cnt <= 0:
        return []
    return _split_null_separated(out, cnt)


def extract_emails(text: str, max_emails: int = 100) -> List[str]:
    """Extract email addresses via native C.""""
    lib = _ensure_loaded()
    data = text.encode()
    out = create_string_buffer(65536)
    cnt = lib.cpp_extract_emails(data, len(data), out, 65536, max_emails)
    if cnt <= 0:
        return []
    return _split_null_separated(out, cnt)


def extract_hashtags(text: str, max_tags: int = 100) -> List[str]:
    """Extract hashtags via native C.""""
    lib = _ensure_loaded()
    data = text.encode()
    out = create_string_buffer(65536)
    cnt = lib.cpp_extract_hashtags(data, len(data), out, 65536, max_tags)
    if cnt <= 0:
        return []
    return _split_null_separated(out, cnt)


def normalize_whitespace(text: str, line_ending: str = "\n") -> str:
    """Normalize whitespace via native C. line_ending: 0='\\n', 1='\\r\\n', 2='\\r'""""
    lib = _ensure_loaded()
    le_map = {"\n": 0, "\r\n": 1, "\r": 2}
    le = le_map.get(line_ending, 0)
    data = text.encode()
    out = create_string_buffer(len(data) + 1)
    rc = lib.cpp_normalize_ws(data, len(data), le, out, len(out))
    if rc < 0:
        return text
    raw = out.raw
    strlen = raw.find(b'\0')
    return raw[:strlen].decode() if strlen >= 0 else out.value.decode() if isinstance(out.value, bytes) else out.value[:rc]


def base_convert(number: str, from_base: int = 10, to_base: int = 16) -> str:
    """Convert number between bases 2-36 via native C.""""
    lib = _ensure_loaded()
    out = create_string_buffer(256)
    rc = lib.cpp_base_convert(number.encode(), from_base, to_base, out, 256)
    if rc < 0:
        raise NativeError(f"base_convert failed: {number} {from_base}->{to_base}")
    return out.value.decode() if isinstance(out.value, bytes) else out.value[:rc]


def word_freq_hash(text: str, top_n: int = 20) -> List[Tuple[str, int]]:
    """Count word frequencies via native C hash table (v2, larger table).""""
    lib = _ensure_loaded()
    out = create_string_buffer(65536)
    data = text.encode()
    rc = lib.cpp_word_freq_hash(data, len(data), top_n, out, 65536)
    if rc <= 0:
        return []
    raw = out.value.decode() if isinstance(out.value, bytes) else out.value
    pairs = []
    for entry in raw.split(","):
        if ":" in entry:
            word, count = entry.rsplit(":", 1)
            try:
                pairs.append((word, int(count)))
            except ValueError:
                pass
    return pairs


def _split_null_separated(buf, count: int) -> List[str]:
    """Split a ctypes buffer of null-separated strings.""""
    results = []
    start = 0
    raw = buf.raw if hasattr(buf, 'raw') else buf.value
    if isinstance(raw, bytes):
        for i, b in enumerate(raw):
            if b == 0:
                if i > start:
                    results.append(raw[start:i].decode('utf-8', errors='replace'))
                start = i + 1
                if len(results) >= count:
                    break
    return results


def glob(pattern: str, max_results: int = 1000) -> List[str]:
    """Glob via native POSIX glob().""""
    lib = _ensure_loaded()
    out = create_string_buffer(65536)
    rc = lib.cpp_glob(pattern.encode(), out, 65536, max_results)
    if rc < 0:
        raise NativeError(f"glob failed: {pattern}")
    if rc == 0:
        return []
    raw = out.raw
    results = []
    start = 0
    for i in range(len(raw)):
        if raw[i] == 0:
            if i > start:
                results.append(raw[start:i].decode())
            start = i + 1
    return results



def benchmark(fn, *args, iterations: int = 10000, **kwargs) -> float:
    """Micro-benchmark a function. Returns microseconds per call.""""
    import time
    for _ in range(min(100, iterations // 10)):
        fn(*args, **kwargs)

    t0 = time.perf_counter()
    for _ in range(iterations):
        fn(*args, **kwargs)
    elapsed = time.perf_counter() - t0
    return (elapsed / iterations) * 1_000_000



__all__ = [
    'sha256', 'sha512', 'hmac_sha256', 'pbkdf2_sha256', 'secure_random',
    'base64_encode', 'base64_decode', 'hex_encode', 'hex_decode',
    'url_encode', 'url_decode', 'is_valid_utf8',
    'file_stat', 'file_copy', 'file_read', 'file_write',
    'mmap_read', 'mmap_close',
    'csv_info', 'csv_cell',
    'tokenize', 'word_frequency', 'trim', 'word_freq_hash', 'glob',
    'slugify', 'truncate', 'extract_urls', 'extract_emails', 'extract_hashtags',
    'normalize_whitespace', 'base_convert',
    'benchmark', 'NativeError',
]
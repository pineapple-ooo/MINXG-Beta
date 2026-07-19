"""test_native.py — verify the Python ctypes bridge to C core."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_import():
    from minxg.five_pillars.scalar.core_native import (
        sha256, sha512, hmac_sha256, hex_encode, hex_decode,
        base64_encode, base64_decode, is_valid_utf8, trim,
        tokenize, word_frequency, file_stat
    )
    print("[PASS] core_native import")

def test_crypto():
    from minxg.five_pillars.scalar.core_native import sha256, sha512, hmac_sha256, hex_encode, hex_decode

    h = sha256(b"hello world")
    assert len(h) == 32, f"sha256 length: {len(h)}"
    assert hex_encode(h) == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    print("[PASS] sha256")

    h = sha512(b"hello world")
    assert len(h) == 64, f"sha512 length: {len(h)}"
    print("[PASS] sha512")

    h = hmac_sha256(b"key", b"data")
    assert len(h) == 32
    print("[PASS] hmac_sha256")

    decoded = hex_decode("deadbeef")
    assert decoded == b'\xde\xad\xbe\xef', f"hex_decode: {decoded.hex()}"
    print("[PASS] hex encode/decode")

def test_encoding():
    from minxg.five_pillars.scalar.core_native import base64_encode, base64_decode

    enc = base64_encode(b"hello world")
    assert enc == "aGVsbG8gd29ybGQ=", f"base64_encode: {enc}"
    dec = base64_decode(enc)
    assert dec == b"hello world", f"base64_decode: {dec}"
    print("[PASS] base64 encode/decode")

def test_text():
    from minxg.five_pillars.scalar.core_native import is_valid_utf8, trim, tokenize

    assert is_valid_utf8(b"hello world")
    assert is_valid_utf8("你好世界".encode())
    assert not is_valid_utf8(b"\xc0\xc1")
    print("[PASS] utf8 validation")

    assert trim("  hello  ") == "hello"
    assert trim("\t\n  spaced \r\n") == "spaced"
    print("[PASS] trim")

    toks = tokenize("the quick brown fox")
    assert len(toks) == 4
    assert toks[0] == "the"
    print("[PASS] tokenize")

def test_word_freq():
    from minxg.five_pillars.scalar.core_native import word_frequency

    freq = word_frequency("the cat and the dog the cat", top_n=3)
    assert freq[0][0] == "the"
    assert freq[0][1] == 3
    print("[PASS] word_frequency")

if __name__ == "__main__":
    print("=== MINXG Python Bridge Tests ===\n")
    try:
        test_import()
        test_crypto()
        test_encoding()
        test_text()
        test_word_freq()
        print("\nAll tests PASSED")
    except ImportError as e:
        print(f"[SKIP] Native library not available: {e}")
        print("Run 'make c-build' first to compile the C library.")
    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
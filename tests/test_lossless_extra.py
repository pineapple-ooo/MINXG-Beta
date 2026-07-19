"""Extra coverage for minxg.lossless — codec, skeleton, and BIE primitives."""
import struct
import zlib
import pytest
from minxg.lossless import (
    sphere_embed,
    blade_between,
    BIEBlade,
    SkeletonEncoder,
    LosslessCodec,
    CompressionResult,
)


def test_lossless_module_imports_cleanly():
    import importlib
    import minxg.lossless
    importlib.reload(minxg.lossless)


def test_codec_round_trip_empty_bytes():
    codec = LosslessCodec()
    result = codec.compress(b"")
    assert result.original_size == 0
    assert result.payload == codec.compress(b"").payload  # deterministic
    out = codec.decompress(result.payload)
    assert out == b""


def test_codec_round_trip_single_byte():
    codec = LosslessCodec()
    for b in (0x00, 0x7F, 0xFF):
        result = codec.compress(bytes([b]))
        out = codec.decompress(result.payload)
        assert out == bytes([b])


def test_codec_rejects_bad_magic_bytes():
    codec = LosslessCodec()
    bad = b"BADMGC" + b"\x01" + b"\x00\x00\x00\x05" + b"\x00" * 5
    with pytest.raises(ValueError):
        codec.decompress(bad)


def test_codec_rejects_truncated_payload():
    codec = LosslessCodec()
    payload = codec.compress(b"hello world")
    truncated = payload.payload[:-5]
    with pytest.raises(ValueError):
        codec.decompress(truncated)


def test_skeleton_round_trip_simple_record():
    data = b"ABCDEFGHIJ"
    enc = SkeletonEncoder(curvature_threshold=0.05)
    skel = enc.encode(data)
    assert skel.length == len(data)
    decoded = enc.decode(skel)
    assert decoded == data


def test_bie_sphere_embed_returns_point_with_byte():
    p = sphere_embed(42)
    assert p.byte == 42
    assert len(p.coords) == 3
    # verify unit-sphere property
    x, y, z = p.coords
    assert abs(x * x + y * y + z * z - 1.0) < 1e-9


def test_bie_blade_serialize_deserialize_round_trip():
    a = sphere_embed(10)
    b = sphere_embed(200)
    blade = blade_between(a, b)
    raw = blade.serialize()
    restored = BIEBlade.deserialize(raw)
    assert restored.src_byte == 10
    assert restored.dst_byte == 200
    assert restored.grade == blade.grade
    for c1, c2 in zip(restored.components, blade.components):
        assert abs(c1 - c2) < 1e-6


def test_bie_deserialize_rejects_too_short_payload():
    with pytest.raises(ValueError):
        BIEBlade.deserialize(b"\x00" * 5)


def test_codec_rejects_wrong_version():
    codec = LosslessCodec()
    payload = codec.compress(b"test")
    raw = bytearray(payload.payload)
    raw[6] = 0xFF  # corrupt version byte
    with pytest.raises(ValueError):
        codec.decompress(bytes(raw))

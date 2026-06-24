"""Tests for minxg.lossless BIE compression."""
import os
import pytest
from minxg.lossless import (
    sphere_embed, blade_between,
    BIEBlade, SkeletonEncoder,
    LosslessCodec, CompressionResult,
)


def test_sphere_embed_byte_invertible():
    for b in (0, 1, 42, 127, 200, 255):
        p = sphere_embed(b)
        assert p.byte == b
        assert abs((p.coords[0] ** 2 + p.coords[1] ** 2 + p.coords[2] ** 2) - 1.0) < 1e-9


def test_blade_between_records_byte_pair():
    a = sphere_embed(0)
    b = sphere_embed(255)
    blade = blade_between(a, b)
    assert blade.src_byte == 0
    assert blade.dst_byte == 255
    reloaded = BIEBlade.deserialize(blade.serialize())
    assert reloaded.src_byte == 0
    assert reloaded.dst_byte == 255
    for a, b in zip(reloaded.components, blade.components):
        assert abs(a - b) < 1e-5


def test_skeleton_round_trip_random():
    data = os.urandom(1024)
    skel = SkeletonEncoder(curvature_threshold=0.05)
    encoded = skel.encode(data)
    decoded = skel.decode(encoded)
    assert decoded == data


def test_skeleton_round_trip_skewed_distribution():
    data = (b"\x00" * 1000) + b"hello" + (b"\x01" * 1000)
    skel = SkeletonEncoder(curvature_threshold=0.05)
    encoded = skel.encode(data)
    decoded = skel.decode(encoded)
    assert decoded == data


def test_codec_v1_round_trip_text():
    payload = b"the quick brown fox jumps over the lazy dog " * 16
    codec = LosslessCodec(curvature_threshold=0.05)
    result = codec.compress(payload)
    assert isinstance(result, CompressionResult)
    assert result.original_size == len(payload)
    out = codec.decompress(result.payload)
    assert out == payload


def test_codec_rejects_bad_magic():
    codec = LosslessCodec()
    with pytest.raises(ValueError):
        codec.decompress(b"XXXXXX" + b"\x00" * 20)


def test_codec_rejects_bad_crc():
    codec = LosslessCodec()
    payload = b"hello world"
    result = codec.compress(payload)
    tampered = bytearray(result.payload)
    tampered[-5] ^= 0x01
    with pytest.raises(ValueError):
        codec.decompress(bytes(tampered))

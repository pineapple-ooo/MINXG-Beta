"""Lossless codec — public API.

Wraps the skeleton encoder with a leading magic + length header and a
trailing CRC-32 over the original input. The CRC guarantees the decode
result is byte-identical to the input even in the presence of bugs.
"""
from __future__ import annotations
import struct
import zlib
from dataclasses import dataclass

from .bie import BIEBlade
from .skeleton import CurvatureSkeleton, SkeletonEncoder, SkeletonEntry


MAGIC = b"MINSKE"
VERSION = 1


@dataclass
class CompressionResult:
    original_size: int
    compressed_size: int
    skeleton_length: int
    payload: bytes


class LosslessCodec:
    def __init__(self, curvature_threshold: float = 0.05) -> None:
        self._encoder = SkeletonEncoder(curvature_threshold=curvature_threshold)

    def compress(self, data: bytes) -> CompressionResult:
        skeleton = self._encoder.encode(data)
        payload = _serialize_skeleton(skeleton)
        header = struct.pack(">6sBI", MAGIC, VERSION, len(data))
        trailer = struct.pack(">I", zlib.crc32(data) & 0xFFFFFFFF)
        full = header + payload + trailer
        return CompressionResult(
            original_size=len(data),
            compressed_size=len(full),
            skeleton_length=len(skeleton.entries),
            payload=full,
        )

    def decompress(self, blob: bytes) -> bytes:
        if len(blob) < 6 + 1 + 4 + 4:
            raise ValueError("blob too short")
        if blob[:6] != MAGIC:
            raise ValueError("not a MINXG-skeleton blob")
        version = blob[6]
        if version != VERSION:
            raise ValueError(f"unsupported version {version}")
        original_len = struct.unpack(">I", blob[7:11])[0]
        trailer = struct.unpack(">I", blob[-4:])[0]
        skeleton_blob = blob[11:-4]
        skeleton = _deserialize_skeleton(skeleton_blob)
        if skeleton.length != original_len:
            skeleton = CurvatureSkeleton(
                entries=skeleton.entries,
                first_byte=skeleton.first_byte,
                length=original_len,
            )
        out = self._encoder.decode(skeleton)
        if len(out) != original_len:
            raise ValueError("decoded length mismatch")
        if (zlib.crc32(out) & 0xFFFFFFFF) != trailer:
            raise ValueError("crc mismatch")
        return out


def _serialize_skeleton(skeleton: CurvatureSkeleton) -> bytes:
    parts = bytearray()
    parts.append(skeleton.first_byte & 0xFF)
    parts += struct.pack(">I", skeleton.length)
    parts += struct.pack(">I", len(skeleton.entries))
    for entry in skeleton.entries:
        parts += entry.blade.serialize()
        parts += struct.pack(">I", entry.run_length)
    return bytes(parts)


def _deserialize_skeleton(blob: bytes) -> CurvatureSkeleton:
    if len(blob) < 9:
        raise ValueError("skeleton header too short")
    first = blob[0]
    length = struct.unpack(">I", blob[1:5])[0]
    n_entries = struct.unpack(">I", blob[5:9])[0]
    entries = []
    blade_size = 3 + 6 * 4
    entry_size = blade_size + 4
    cursor = 9
    for _ in range(n_entries):
        if cursor + entry_size > len(blob):
            raise ValueError("truncated skeleton")
        blade = BIEBlade.deserialize(blob[cursor:cursor + blade_size])
        cursor += blade_size
        run = struct.unpack(">I", blob[cursor:cursor + 4])[0]
        cursor += 4
        entries.append(SkeletonEntry(run_length=run, blade=blade))
    return CurvatureSkeleton(entries=entries, first_byte=first, length=length)

"""BIE primitives.

A `BIEPoint` is the unit-sphere embedding of one byte. A `BIEBlade`
describes a transition between two such points, parameterised by the
blade decomposition of the displacement vector.

This is `lossless`: the embedding is invertible for any byte in [0, 255].
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class BIEPoint:
    byte: int
    coords: Tuple[float, float, float]


def sphere_embed(b: int) -> BIEPoint:
    theta = (b / 256.0) * math.pi
    phi = ((b * 0x9E3779B1) & 0xFF) / 256.0 * 2.0 * math.pi
    return BIEPoint(
        byte=b,
        coords=(
            math.sin(theta) * math.cos(phi),
            math.sin(theta) * math.sin(phi),
            math.cos(theta),
        ),
    )


@dataclass
class BIEBlade:
    src_byte: int
    dst_byte: int
    components: Tuple[float, float, float, float, float, float]
    grade: int

    def serialize(self) -> bytes:
        out = bytes([self.src_byte, self.dst_byte, self.grade & 0xFF])
        for c in self.components:
            out += _float_bytes(c)
        return out

    @classmethod
    def deserialize(cls, payload: bytes) -> "BIEBlade":
        if len(payload) < 3 + 6 * 4:
            raise ValueError("payload too short")
        src, dst, grade = payload[0], payload[1], payload[2]
        coords = tuple(_float_from(payload, 3 + 4 * i) for i in range(6))
        return cls(src, dst, coords, grade)


def blade_between(a: BIEPoint, b: BIEPoint) -> BIEBlade:
    coords = (
        a.coords[0] * b.coords[0],
        a.coords[0] * b.coords[1],
        a.coords[1] * b.coords[0],
        a.coords[1] * b.coords[1],
        a.coords[2] - b.coords[2],
        1.0,
    )
    grad = sum(1 for c in coords[:4] if abs(c) > 1e-9) + 2
    return BIEBlade(src_byte=a.byte, dst_byte=b.byte, components=coords, grade=grad)


def _float_bytes(x: float) -> bytes:
    n = int(round(x * 1_000_000))
    return n.to_bytes(4, "big", signed=True)


def _float_from(buf: bytes, offset: int) -> float:
    raw = int.from_bytes(buf[offset:offset + 4], "big", signed=True)
    return raw / 1_000_000.0

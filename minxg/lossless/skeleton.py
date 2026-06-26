"""Curvature skeleton over a sequence of BIE points."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

from .bie import BIEPoint, BIEBlade, sphere_embed, blade_between


@dataclass
class SkeletonEntry:
    run_length: int
    blade: BIEBlade


@dataclass
class CurvatureSkeleton:
    entries: List[SkeletonEntry] = field(default_factory=list)
    first_byte: int = 0
    length: int = 0


class SkeletonEncoder:
    def __init__(self, curvature_threshold: float = 0.05) -> None:
        self.threshold = float(curvature_threshold)

    def encode(self, data: bytes) -> CurvatureSkeleton:
        if not data:
            return CurvatureSkeleton()
        points = [sphere_embed(b) for b in data]
        skeleton = CurvatureSkeleton(first_byte=data[0], length=len(data))
        prev = points[0]
        run = 0
        i = 1
        while i < len(points):
            cur = points[i]
            blade = blade_between(prev, cur)
            significant = self._is_significant(blade, prev, cur)
            if significant:
                skeleton.entries.append(SkeletonEntry(run_length=run, blade=blade))
                prev = cur
                run = 0
            else:
                run += 1
            i += 1
        if run > 0:
            last_blade = blade_between(prev, points[-1])
            skeleton.entries.append(SkeletonEntry(run_length=run, blade=last_blade))
        elif not skeleton.entries:
            last_blade = blade_between(points[0], points[-1])
            skeleton.entries.append(SkeletonEntry(run_length=0, blade=last_blade))
        return skeleton

    def decode(self, skeleton: CurvatureSkeleton) -> bytes:
        if skeleton.length == 0:
            return b""
        out = bytearray(skeleton.length)
        out[0] = skeleton.first_byte & 0xFF
        cursor = 1
        prev_byte = out[0]
        for entry in skeleton.entries:
            for _ in range(entry.run_length):
                if cursor < skeleton.length:
                    out[cursor] = prev_byte
                    cursor += 1
            if cursor < skeleton.length:
                out[cursor] = entry.blade.dst_byte & 0xFF
                prev_byte = out[cursor]
                cursor += 1
        return bytes(out)

    def _is_significant(self, blade: BIEBlade, prev: BIEPoint, cur: BIEPoint) -> bool:
        if prev.byte == cur.byte:
            return False
        return any(abs(c) > self.threshold for c in blade.components)

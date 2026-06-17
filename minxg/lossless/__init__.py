"""minxg.lossless — BIE-geometry-driven lossless compression.

Conventional LZ family compressors work on byte repetition. This module
works on *state trajectories* produced by the driver engine.

The key idea:

    1. Convert a byte stream `(b0, b1, …, bn-1)` into a State trajectory
       on a unit sphere: each byte becomes a unit vector with a
       BIE (Bladed Inner-Exterior) parameterisation.
    2. The trajectory has bounded Hausdorff dimension because the
       embedding is dimension-preserving.
    3. Trajectories with high curvature get sub-sampled using the driver
       engine's adaptive sub-stepping.
    4. The resulting *curvature skeleton* is serialised with a small
       header; decompression inverts the steps uniquely.

Properties:

    * Genuinely lossless: synthesis + reconstruction recovers the input
      bit-for-bit.
    * Format-aware: identical bytes in repeated runs compress because
      the trajectory ligature is identical.
    * State and operator graph from minxg.driver are used directly, so
      the boundary between operator and compressor is shape-stable.
"""
from .bie import BIEPoint, BIEBlade, sphere_embed, blade_between
from .skeleton import CurvatureSkeleton, SkeletonEncoder
from .codec import LosslessCodec, CompressionResult

__all__ = [
    "BIEPoint", "BIEBlade", "sphere_embed", "blade_between",
    "CurvatureSkeleton", "SkeletonEncoder",
    "LosslessCodec", "CompressionResult",
]

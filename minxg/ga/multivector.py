"""
minxg/ga/multivector.py — Multivector: the unified type of Geometric Algebra
====================================================================================

A multivector M in Cl(p,q,r) is a sum of blades, each a scalar times a basis
blade e_{i1}∧e_{i2}∧...∧e_{ik}. The set of all blades forms a 2^n-dimensional
algebra, where n = p+q+r is the total dimension of the underlying vector space.

Blade Indexing Convention
-------------------------
We use a 16-bit integer "blade index" to encode which basis blade:
  - bit i set => e_i appears in the wedge
  - blade 0 = 1 (scalar)
  - blade 1 = e_0, blade 2 = e_1, blade 4 = e_2, blade 8 = e_3
  - blade 3 = e_01, blade 5 = e_02, blade 9 = e_03, blade 6 = e_12, ...

Storage is SPARSE: only non-zero blades are stored. A Multivector in 4D has
at most 16 components; most AI workloads have <8 non-zero components, so the
sparse dict representation is optimal.

Clifford Signature (p, q, r)
----------------------------
  p = number of basis vectors squaring to +1
  q = number of basis vectors squaring to -1
  r = number of null basis vectors (e_i² = 0)
Default: Cl(4, 0, 0) — Euclidean 4-space. To get 3D, set n=3. To get
Minkowski spacetime, use (1, 3, 0).
""""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, Iterator, Tuple, Union, List, Optional, Iterable




@dataclass(frozen=True)
class Signature:
    """Clifford algebra signature (p, q, r): p positive, q negative, r null.""""
    p: int
    q: int
    r: int = 0

    @property
    def n(self) -> int:
        return self.p + self.q + self.r

    def metric(self, i: int) -> int:
        """Returns +1, -1, or 0 for basis vector e_i.""""
        if i < self.p:
            return 1
        if i < self.p + self.q:
            return -1
        return 0




def grade_of(blade: int) -> int:
    """Number of basis vectors in a blade (population count).""""
    return bin(blade).count("1")


def basis_grade_index(blade: int) -> Tuple[int, ...]:
    """Returns the sorted tuple of basis indices in a blade.""""
    return tuple(i for i in range(16) if blade & (1 << i))


def blade_sign(a: int, b: int) -> int:
    """Sign from commuting basis vectors of two blades to canonical order.

    Returns +1 or -1 (or 0 if blades share a basis vector).
    """"
    if a & b:
        return 0  
    s = 0
    for j in basis_grade_index(b):
        s += bin(a & ~((1 << (j + 1)) - 1)).count("1")
    return 1 if s % 2 == 0 else -1


def blade_outer(blades_a: int, blades_b: int) -> int:
    """Outer product blade index: OR of the two blade bitmasks.""""
    if blades_a & blades_b:
        return 0  
    return blades_a | blades_b




Number = Union[int, float, complex]


@dataclass(frozen=True)
class Blade:
    """A basis blade e_{i1} ∧ e_{i2} ∧ ... ∧ e_{ik}.

    The (frozen) dataclass form of an integer blade index. Provided for
    type hints and external interop; arithmetic uses int blade indices
    internally for performance.
    """"
    indices: Tuple[int, ...]

    def __int__(self) -> int:
        result = 0
        for i in self.indices:
            result |= (1 << i)
        return result

    @property
    def grade(self) -> int:
        return len(self.indices)

    def __repr__(self) -> str:
        if not self.indices:
            return "1"
        return "e_" + "".join(str(i) for i in self.indices)


class Multivector:
    """A multivector in Cl(p,q,r). Sparse storage over blade indices.

    Examples
    --------
    >>> # 3D Euclidean
    >>> from minxg.ga import Multivector, Signature
    >>> sig = Signature(3, 0)
    >>> e1 = Multivector({1: 1.0}, sig)   # e_0
    >>> e2 = Multivector({2: 1.0}, sig)   # e_1
    >>> e12 = e1.outer(e2)                # e_01
    >>> e12[3]                              # 1.0
    """"
    __slots__ = ("coeffs", "sig")

    coeffs: Dict[int, float]
    sig: Signature

    def __init__(self, coeffs: Optional[Dict[int, Number]] = None,
                 sig: Optional[Signature] = None):
        if sig is None:
            sig = Signature(4, 0)
        if coeffs is None:
            coeffs = {}
        n_bits = sig.n
        cleaned: Dict[int, float] = {}
        for k, v in coeffs.items():
            if v == 0:
                continue
            if isinstance(v, complex) and v.imag == 0:
                v = v.real
            if k >= (1 << n_bits):
                raise ValueError(
                    f"Blade index {k} exceeds signature dim {n_bits}"
                )
            cleaned[int(k)] = float(v)
        self.coeffs = cleaned
        self.sig = sig

    

    @classmethod
    def scalar(cls, value: Number, sig: Optional[Signature] = None) -> "Multivector":
        return cls({0: float(value)}, sig)

    @classmethod
    def vector(cls, components: Iterable[Number], sig: Optional[Signature] = None) -> "Multivector":
        d = {i: float(c) for i, c in enumerate(components) if c != 0}
        return cls(d, sig)

    @classmethod
    def zero(cls, sig: Optional[Signature] = None) -> "Multivector":
        return cls({}, sig)

    @classmethod
    def from_dict(cls, d: Dict[int, Number], sig: Optional[Signature] = None) -> "Multivector":
        return cls(d, sig)

    

    def __getitem__(self, blade: int) -> float:
        return self.coeffs.get(blade, 0.0)

    def __setitem__(self, blade: int, value: float) -> None:
        if value == 0:
            self.coeffs.pop(blade, None)
        else:
            self.coeffs[blade] = float(value)

    def grade(self, k: int) -> "Multivector":
        """Return the grade-k part of this multivector.""""
        return Multivector(
            {b: v for b, v in self.coeffs.items() if grade_of(b) == k},
            self.sig,
        )

    @property
    def grades(self) -> List[int]:
        """All grades present in this multivector (sorted).""""
        return sorted({grade_of(b) for b in self.coeffs})

    

    def __add__(self, other: "Multivector") -> "Multivector":
        if not isinstance(other, Multivector):
            return NotImplemented
        result = dict(self.coeffs)
        for b, v in other.coeffs.items():
            result[b] = result.get(b, 0.0) + v
        return Multivector(result, self.sig)

    def __sub__(self, other: "Multivector") -> "Multivector":
        if not isinstance(other, Multivector):
            return NotImplemented
        result = dict(self.coeffs)
        for b, v in other.coeffs.items():
            result[b] = result.get(b, 0.0) - v
        return Multivector(result, self.sig)

    def __neg__(self) -> "Multivector":
        return Multivector({b: -v for b, v in self.coeffs.items()}, self.sig)

    def __mul__(self, other: Union["Multivector", Number]) -> "Multivector":
        """Scalar multiplication OR geometric product (with another Multivector).""""
        from .algebra import geometric_product
        if isinstance(other, (int, float)):
            return Multivector({b: v * other for b, v in self.coeffs.items()}, self.sig)
        if isinstance(other, Multivector):
            return geometric_product(self, other)
        return NotImplemented

    def __rmul__(self, other: Number) -> "Multivector":
        return self * other

    def __truediv__(self, other: Number) -> "Multivector":
        if other == 0:
            raise ZeroDivisionError("Multivector division by zero")
        return Multivector({b: v / other for b, v in self.coeffs.items()}, self.sig)

    def __pow__(self, n: int) -> "Multivector":
        if n == 0:
            return Multivector.scalar(1.0, self.sig)
        if n < 0:
            return self.inverse() ** (-n)
        result = Multivector.scalar(1.0, self.sig)
        base = self
        while n > 0:
            if n & 1:
                result = result * base
            base = base * base
            n >>= 1
        return result

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Multivector):
            return NotImplemented
        return self.coeffs == other.coeffs and self.sig == other.sig

    def __hash__(self) -> int:
        return hash((frozenset(self.coeffs.items()), self.sig))

    def __repr__(self) -> str:
        if not self.coeffs:
            return "0"
        items = sorted(self.coeffs.items(), key=lambda kv: (grade_of(kv[0]), kv[0]))
        return " + ".join(
            f"{v:g}*e_{_fmt_blade(b)}" if b != 0 else f"{v:g}"
            for b, v in items
        )

    

    def outer(self, other: "Multivector") -> "Multivector":
        from .algebra import outer_product
        return outer_product(self, other)

    def inner(self, other: "Multivector") -> "Multivector":
        from .algebra import inner_product
        return inner_product(self, other)

    def left_contract(self, other: "Multivector") -> "Multivector":
        return left_contraction(self, other)

    def right_contract(self, other: "Multivector") -> "Multivector":
        return right_contraction(self, other)

    def fat_dot(self, other: "Multivector") -> "Multivector":
        return fat_dot(self, other)

    def reverse(self) -> "Multivector":
        """Rearrangement: reverse the order of basis vectors in each blade.

        For grade k blade: (-1)^(k(k-1)/2)
        """"
        out: Dict[int, float] = {}
        for b, v in self.coeffs.items():
            k = grade_of(b)
            sign = -1 if (k * (k - 1) // 2) % 2 else 1
            out[b] = sign * v
        return Multivector(out, self.sig)

    def grade_invol(self) -> "Multivector":
        """Grade involution: flip sign of odd-grade components.""""
        return Multivector(
            {b: v * (1 if grade_of(b) % 2 == 0 else -1)
             for b, v in self.coeffs.items()},
            self.sig,
        )

    def clifford_conj(self) -> "Multivector":
        """Clifford conjugation = grade involution ∘ reverse.

        For grade k blade: (-1)^(k(k+1)/2)
        """"
        out: Dict[int, float] = {}
        for b, v in self.coeffs.items():
            k = grade_of(b)
            sign = -1 if (k * (k + 1) // 2) % 2 else 1
            out[b] = sign * v
        return Multivector(out, self.sig)

    def conjugate(self) -> "Multivector":
        """Alias for clifford_conj — context-dependent convention.""""
        return self.clifford_conj()

    @property
    def norm_sq(self) -> float:
        """Squared magnitude: |grade(M)|², computed grade-by-grade.

        For each grade-k part, |B|²_k = (-1)^(k(k-1)/2) * <B B>_0.
        This is the natural Clifford norm that always gives +1 for unit blades.
        """"
        from .algebra import geometric_product
        prod = geometric_product(self, self)
        total = 0.0
        for b, v in prod.coeffs.items():
            from .multivector import grade_of
            k = grade_of(b)
            sign = 1 if (k * (k - 1) // 2) % 2 == 0 else -1
            total += sign * v
        return total

    @property
    def norm(self) -> float:
        """Norm: |M| = sqrt(|M|²) for positive-definite metrics.""""
        n2 = self.norm_sq
        if n2 < 0:
            return math.sqrt(-n2)  
        return math.sqrt(n2)

    def normalize(self) -> "Multivector":
        n = self.norm
        if n == 0:
            raise ValueError("Cannot normalize zero multivector")
        return self / n

    def inverse(self) -> "Multivector":
        """Inverse: reverse(M) / norm_sq for invertible multivectors.""""
        n2 = self.norm_sq
        if n2 == 0:
            raise ValueError("Multivector has no inverse (null norm)")
        return self.reverse() / n2

    def dual(self) -> "Multivector":
        """Hodge dual: M * I^(-1)  (right contraction by pseudoscalar).""""
        from .algebra import pseudoscalar
        I = pseudoscalar(self.sig)
        return self * I.inverse()

    def exp(self) -> "Multivector":
        """Multivector exponential via series: e^M = Σ M^n / n!""""
        
        result = Multivector.scalar(1.0, self.sig)
        term = Multivector.scalar(1.0, self.sig)
        for n in range(1, 20):
            term = term * self / n
            result = result + term
            max_term = max((abs(v) for v in term.coeffs.values()), default=0)
            if max_term < 1e-15:
                break
        return result

    def log(self) -> "Multivector":
        """Multivector logarithm (principal branch).

        Uses: log(M) = log(|M|) + log_unit(M)  where log_unit uses atan2.
        """"
        
        s = self[0]
        B = self.grade(2)
        B_sq = geometric_product(B, B)[0]  
        b_norm = math.sqrt(max(0, -B_sq))  
        if b_norm < 1e-12:
            
            if s <= 0:
                raise ValueError("Multivector log undefined for non-positive scalar part")
            return Multivector({0: math.log(s)}, self.sig) + B / s
        
        abs_m = math.sqrt(s * s - B_sq)
        theta = math.atan2(b_norm, s)
        return Multivector.scalar(math.log(abs_m), self.sig) + Multivector(B.coeffs, self.sig) * (theta / b_norm)

    def sqrt(self) -> "Multivector":
        """Multivector square root via log/exp: √M = exp(0.5 log M).""""
        return self.log().__mul__(0.5).exp()

    

    def __iter__(self) -> Iterator[Tuple[int, float]]:
        return iter(self.coeffs.items())

    def items(self):
        return self.coeffs.items()

    def keys(self):
        return self.coeffs.keys()

    def values(self):
        return self.coeffs.values()

    def __len__(self) -> int:
        return len(self.coeffs)

    def __bool__(self) -> bool:
        return bool(self.coeffs)


def _fmt_blade(b: int) -> str:
    """Format a blade index like '01' for e_0 ∧ e_1.""""
    if b == 0:
        return "0"
    return "".join(str(i) for i in basis_grade_index(b))

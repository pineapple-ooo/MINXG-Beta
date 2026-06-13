"""
minxg/cat/morphism.py — Morphisms, Types, Composition
============================================================

Core categorical constructs. Every operator in MINXG is a Morphism.

A MORPHISM f: A → B is an operator that:
  - has a DOMAIN type A (input types)
  - has a CODOMAIN type B (output type)
  - can be COMPOSED with g: B → C to give f∘g: A → C

A TYPE is just a symbolic name (or a structural type). We don't have full
dependent types — we have nominal types with simple structural matching.

The CATEGORY of MINXG operators:
  - OBJECTS = Python types (str, int, list, dict, custom dataclasses)
  - MORPHISMS = registered operators
  - COMPOSITION = f∘g via the chain operator
  - IDENTITY = identity morphism for each type
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, Generic, TypeVar
import hashlib


# ── Type ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Type:
    """A type in the operator category.

    Structural type: identified by its string signature. Two types are equal
    iff their signatures are equal. For AI workloads, we use coarse types:
    'number', 'string', 'list', 'dict', 'bool', 'multivector', 'tensor',
    'function', 'any'.
    """
    name: str
    params: Tuple[str, ...] = ()

    def __str__(self) -> str:
        if not self.params:
            return self.name
        return f"{self.name}<{','.join(self.params)}>"

    def matches(self, other: "Type") -> bool:
        """Structural matching. 'any' matches everything."""
        if self.name == "any" or other.name == "any":
            return True
        if self.name != other.name:
            return False
        if len(self.params) != len(other.params):
            return False
        return all(p == "any" or q == "any" or p == q
                   for p, q in zip(self.params, other.params))

    @classmethod
    def any(cls) -> "Type":
        return cls("any")

    @classmethod
    def list_of(cls, element: "Type") -> "Type":
        return cls("list", (str(element),))

    @classmethod
    def dict_of(cls, key: "Type", value: "Type") -> "Type":
        return cls("dict", (str(key), str(value)))


# ── Identity morphism ────────────────────────────────────────────────────────

class Morphism:
    """A morphism in the operator category: an operator with type signature.

    Unlike Python callables, Morphisms carry:
      - explicit domain/codomain types
      - composition rules
      - purity flag
      - monadic context (optional)
    """
    __slots__ = ("name", "domain", "codomain", "fn", "is_pure", "monadic_context",
                 "metadata")

    name: str
    domain: Tuple[Type, ...]
    codomain: Type
    fn: Callable
    is_pure: bool
    monadic_context: Optional[str]
    metadata: Dict[str, Any]

    def __init__(self, name: str, domain: Tuple[Type, ...], codomain: Type,
                 fn: Callable, is_pure: bool = True,
                 monadic_context: Optional[str] = None,
                 metadata: Optional[Dict] = None):
        self.name = name
        self.domain = domain
        self.codomain = codomain
        self.fn = fn
        self.is_pure = is_pure
        self.monadic_context = monadic_context
        self.metadata = metadata or {}

    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)

    @property
    def signature(self) -> str:
        """A string signature like '(number, number) -> number'."""
        args = ", ".join(str(t) for t in self.domain)
        return f"({args}) -> {self.codomain}"

    def can_compose_with(self, other: "Morphism") -> bool:
        """Can self∘other be formed? Yes iff self.domain matches other.codomain.

        Note: this is REVERSED from function composition intuition. We use
        pipeline order: f >> g means "do f, then g", equivalent to g(f(x)).
        """
        return self.domain[0].matches(other.codomain) if self.domain else False

    def __rshift__(self, other: "Morphism") -> "Composite":
        """Pipeline composition: self >> other means self, then other.

        For x: self(x) = y, other(y) = z, so (self >> other)(x) = z.
        """
        if not self.can_compose_with(other):
            raise TypeError(
                f"Cannot compose {self.name}: {self.signature} >> {other.name}: {other.signature}. "
                f"Expected self.domain[0] to match other.codomain."
            )
        return Composite([self, other])

    def __repr__(self) -> str:
        return f"{self.name}: {self.signature}"


# ── Identity ─────────────────────────────────────────────────────────────────

def identity(t: Union[Type, str]) -> Morphism:
    """The identity morphism for type t: id_t : t → t.

    The identity is the unique morphism such that f∘id = f = id∘f.
    """
    if isinstance(t, str):
        t = Type(t)
    return Morphism(
        name=f"id_{t}",
        domain=(t,),
        codomain=t,
        fn=lambda x: x,
        is_pure=True,
        monadic_context=None,
        metadata={"is_identity": True},
    )


# ── Composite ────────────────────────────────────────────────────────────────

class Composite(Morphism):
    """A composition of multiple morphisms: f₁ >> f₂ >> f₃ ...

    Composition is ASSOCIATIVE: (f >> g) >> h == f >> (g >> h).
    The associativity is verified at construction time via type checking.
    """
    def __init__(self, morphisms: List[Morphism]):
        if not morphisms:
            raise ValueError("Composite requires at least one morphism")
        # Verify type compatibility
        for i in range(len(morphisms) - 1):
            f_next = morphisms[i + 1]
            f_curr = morphisms[i]
            if not f_next.can_compose_with(f_curr):
                raise TypeError(
                    f"Composition broken at step {i}: "
                    f"{f_next.name}: {f_next.signature} cannot follow "
                    f"{f_curr.name}: {f_curr.signature}"
                )
        # Domain = first morphism's domain, codomain = last morphism's codomain
        super().__init__(
            name=" >> ".join(m.name for m in morphisms),
            domain=morphisms[0].domain,
            codomain=morphisms[-1].codomain,
            fn=_compose_fns(morphisms),
            is_pure=all(m.is_pure for m in morphisms),
            monadic_context=_detect_monad(morphisms),
            metadata={"is_composite": True, "length": len(morphisms)},
        )
        self.morphisms = morphisms

    def __rshift__(self, other: Morphism) -> "Composite":
        return Composite(self.morphisms + [other])


def compose(*morphisms: Morphism) -> "Composite":
    """Compose a sequence of morphisms left-to-right.

    compose(f, g, h) = f >> g >> h  (do f, then g, then h)
    """
    if not morphisms:
        raise ValueError("compose requires at least one morphism")
    return Composite(list(morphisms))


def _compose_fns(morphisms: List[Morphism]) -> Callable:
    """Build a single callable from a chain of morphisms."""
    def composed(*args, **kwargs):
        result = morphisms[0](*args, **kwargs)
        for m in morphisms[1:]:
            # Unwrap single-element lists / dicts for monadic threading
            if isinstance(result, dict) and "value" in result and len(result) == 1:
                result = result["value"]
            result = m(result)
        return result
    return composed


def _detect_monad(morphisms: List[Morphism]) -> Optional[str]:
    """If all morphisms share a monadic context, propagate it."""
    contexts = [m.monadic_context for m in morphisms if m.monadic_context]
    if not contexts:
        return None
    if all(c == contexts[0] for c in contexts):
        return contexts[0]
    return "mixed"


# ── Type derivation ──────────────────────────────────────────────────────────

def derive_type(py_type: type) -> Type:
    """Map a Python type to our coarse Type system."""
    if py_type in (int, float, complex):
        return Type("number")
    if py_type is str:
        return Type("string")
    if py_type is bool:
        return Type("bool")
    if py_type is list:
        return Type("list")
    if py_type is dict:
        return Type("dict")
    if py_type is type(None):
        return Type("none")
    if py_type is bytes:
        return Type("bytes")
    return Type("any")


def derive_morphism_signature(fn: Callable) -> Tuple[Tuple[Type, ...], Type]:
    """Best-effort type derivation from Python type hints."""
    import inspect
    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        return (Type.any(),), Type.any()

    domain: List[Type] = []
    for name, param in sig.parameters.items():
        if param.annotation is inspect.Parameter.empty:
            domain.append(Type.any())
        else:
            domain.append(derive_type(param.annotation))
    ret = sig.return_annotation
    if ret is inspect.Signature.empty:
        codomain = Type.any()
    else:
        codomain = derive_type(ret)
    return tuple(domain), codomain

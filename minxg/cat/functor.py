"""
minxg/cat/functor.py — Functors and Common Instances
============================================================

A FUNCTOR F: C → D is a structure-preserving map between categories.
For our purposes, F is a TYPE CONSTRUCTOR (e.g., Maybe, List, Either) that
comes with a MAP operation:

  map: (A → B) → F<A> → F<B>

LAWS
----
  1. Identity:    map(id_A) = id_{F<A>}
  2. Composition: map(g ∘ f) = map(g) ∘ map(f)

These are FUNCTOR LAWS — every proper functor must satisfy them. We
implementations are designed to be law-compliant (verified by tests).

COMMON FUNCTORS
---------------
  - Identity<A>      = A                  (the trivial functor)
  - Maybe<A> = Some(a) | Nothing           (optional values)
  - Either<L, R> = Left(l) | Right(r)     (success/failure with error)
  - ListF<A> = [a1, ..., an]              (collections, covariant)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Generic, List, Optional, TypeVar, Union, Tuple
from abc import ABC, abstractmethod


A = TypeVar("A")
B = TypeVar("B")


class Functor(ABC):
    """Abstract base class: every functor must implement fmap."""

    @abstractmethod
    def fmap(self, f: Callable[[A], B]) -> "Functor":
        """Apply f to the contents, preserving structure."""
        raise NotImplementedError


# ── Identity functor ─────────────────────────────────────────────────────────

@dataclass
class Identity(Functor, Generic[A]):
    """The identity functor: Identity<A> = A. Trivial but useful as a base case."""
    value: A

    def fmap(self, f: Callable[[A], B]) -> "Identity[B]":
        return Identity(f(self.value))

    def __eq__(self, other):
        return isinstance(other, Identity) and self.value == other.value

    def __repr__(self):
        return f"Identity({self.value!r})"


# ── Maybe functor ────────────────────────────────────────────────────────────

@dataclass
class Maybe(Functor, Generic[A]):
    """The Maybe functor: represents optional values.

    - Just(a)   = present value
    - Nothing() = absent value

    Functor laws: fmap(_)(Nothing()) = Nothing(), fmap(f)(Just(a)) = Just(f(a))
    """
    value: Optional[A]
    is_just: bool = True

    @classmethod
    def just(cls, v: A) -> "Maybe[A]":
        return cls(v, True)

    @classmethod
    def nothing(cls) -> "Maybe[A]":
        return cls(None, False)

    def fmap(self, f: Callable[[A], B]) -> "Maybe[B]":
        if not self.is_just:
            return Maybe.nothing()
        try:
            return Maybe.just(f(self.value))
        except Exception:
            return Maybe.nothing()

    def __eq__(self, other):
        return isinstance(other, Maybe) and self.is_just == other.is_just and self.value == other.value

    def __repr__(self):
        if self.is_just:
            return f"Just({self.value!r})"
        return "Nothing"

    def __bool__(self):
        return self.is_just


# ── Either functor ───────────────────────────────────────────────────────────

@dataclass
class Either(Functor, Generic[A, B]):
    """The Either functor: success or failure with error type.

    - Right(b) = success with value b
    - Left(a)  = failure with error a

    fmap only operates on Right values; Left is preserved.
    """
    is_right: bool
    value: Union[A, B]

    @classmethod
    def right(cls, v: B) -> "Either[A, B]":
        return cls(True, v)

    @classmethod
    def left(cls, e: A) -> "Either[A, B]":
        return cls(False, e)

    def fmap(self, f: Callable[[B], Any]) -> "Either[A, Any]":
        if self.is_right:
            try:
                return Either.right(f(self.value))
            except Exception as e:
                return Either.left(e)
        return self

    def __repr__(self):
        side = "Right" if self.is_right else "Left"
        return f"{side}({self.value!r})"


# ── List functor ─────────────────────────────────────────────────────────────

@dataclass
class ListF(Functor, Generic[A]):
    """The List functor: covariant container.

    Wraps Python lists with a fmap that applies f to every element.
    """
    items: List[A]

    def fmap(self, f: Callable[[A], B]) -> "ListF[B]":
        return ListF([f(x) for x in self.items])

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        return self.items[i]

    def __repr__(self):
        return f"ListF({self.items!r})"


# ── Const functor ────────────────────────────────────────────────────────────

@dataclass
class Const(Functor, Generic[A, B]):
    """The Const functor: ignores the type parameter, holds a constant.

    Used for things like "length of a list" — type changes don't matter.
    """
    value: A

    def fmap(self, f: Callable[[B], Any]) -> "Const[A, Any]":
        return Const(self.value)

    def __repr__(self):
        return f"Const({self.value!r})"


# ── Reader functor ───────────────────────────────────────────────────────────

@dataclass
class Reader(Functor, Generic[A, B]):
    """The Reader functor: function from environment A to result B.

    Reader<A, B> = A -> B

    fmap(f)(g)(a) = f(g(a))
    """
    run: Callable[[A], B]

    def fmap(self, f: Callable[[B], Any]) -> "Reader[A, Any]":
        return Reader(lambda a: f(self.run(a)))

    def __call__(self, a: A) -> B:
        return self.run(a)


# ── Writer functor ───────────────────────────────────────────────────────────

@dataclass
class Writer(Functor, Generic[A, B]):
    """The Writer functor: value with accumulated log.

    Writer<W, A> = (W, A)  where W is a Monoid (logs compose by ⊕)
    """
    log: Any
    value: B

    def fmap(self, f: Callable[[B], Any]) -> "Writer":
        return Writer(self.log, f(self.value))

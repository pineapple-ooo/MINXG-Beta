"""
minxg/cat/monad.py — Monads and Common Instances
========================================================

A MONAD is a functor M with two additional operations:
  - unit (a.k.a. return, pure):  A → M<A>
  - bind (a.k.a. >>=, flatMap): M<A> → (A → M<B>) → M<B>

MONAD LAWS
----------
  1. Left identity:   unit(a) >>= f   =  f(a)
  2. Right identity:  m >>= unit      =  m
  3. Associativity:   (m >>= f) >>= g =  m >>= (λx. f(x) >>= g)

These laws ensure that monadic code behaves predictably under refactoring.

WHY MONADS FOR AI OPERATORS?
----------------------------
Operators have SIDE EFFECTS (state, exceptions, IO, async). Monads make
side effects FIRST-CLASS and COMPOSABLE:
  - Maybe monad:  handles optional values without nested ifs
  - Either monad: handles errors without try/except in every operator
  - State monad:  threads implicit state through operator chains
  - IO monad:     sequences impure operations in a pure wrapper
  - Reader monad: dependency injection via implicit environment
  - List monad:   nondeterministic computation (backtracking search)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, List, Optional, TypeVar, Union
from abc import ABC, abstractmethod
from .functor import Identity, Maybe, Either, ListF


A = TypeVar("A")
B = TypeVar("B")
S = TypeVar("S")  # state
R = TypeVar("R")  # reader environment


class Monad(ABC):
    """Abstract base for monads."""

    @classmethod
    @abstractmethod
    def unit(cls, value: A) -> "Monad":
        raise NotImplementedError

    @abstractmethod
    def bind(self, f: Callable[[A], "Monad"]) -> "Monad":
        """Sequential composition: ma >>= f = f(a) if ma is unit(a)."""
        raise NotImplementedError

    def __rshift__(self, f):  # Haskell's >>=
        return self.bind(f)

    def __ge__(self, f):  # >>=
        return self.bind(f)

    def map(self, f: Callable[[A], B]) -> "Monad":
        """Functor map in terms of monad operations: fmap f = (>>=) . return . f"""
        return self.bind(lambda a: self.unit(f(a)))


# ── Identity monad ───────────────────────────────────────────────────────────

@dataclass
class IdentityM(Monad, Generic[A]):
    value: A

    @classmethod
    def unit(cls, v: A) -> "IdentityM[A]":
        return cls(v)

    def bind(self, f: Callable[[A], "IdentityM[B]"]) -> "IdentityM[B]":
        return f(self.value)

    def __eq__(self, other):
        return isinstance(other, IdentityM) and self.value == other.value

    def __repr__(self):
        return f"IdentityM({self.value!r})"


# ── Maybe monad ──────────────────────────────────────────────────────────────

@dataclass
class MaybeM(Monad, Generic[A]):
    """The Maybe monad: Just(a) or Nothing.

    bind propagates Nothing: Nothing >>= f = Nothing.
    """
    is_just: bool
    value: Any = None

    @classmethod
    def unit(cls, v: A) -> "MaybeM[A]":
        return cls(True, v)

    @classmethod
    def just(cls, v: A) -> "MaybeM[A]":
        return cls(True, v)

    @classmethod
    def nothing(cls) -> "MaybeM[A]":
        return cls(False)

    def bind(self, f: Callable[[A], "MaybeM[B]"]) -> "MaybeM[B]":
        if not self.is_just:
            return MaybeM.nothing()
        return f(self.value)

    @classmethod
    def of_maybe(cls, m: "Maybe[A]") -> "MaybeM[A]":
        return cls(m.is_just, m.value)

    def to_maybe(self) -> "Maybe[A]":
        from .functor import Maybe
        return Maybe(self.value, self.is_just)

    def __repr__(self):
        return f"Just({self.value!r})" if self.is_just else "Nothing"


# ── Either monad ────────────────────────────────────────────────────────────

@dataclass
class EitherM(Monad, Generic[A, B]):
    """The Either monad: Right(b) success or Left(a) failure.

    bind propagates Left: Left(e) >>= f = Left(e).
    """
    is_right: bool
    value: Any = None

    @classmethod
    def unit(cls, v: B) -> "EitherM[A, B]":
        return cls(True, v)

    @classmethod
    def right(cls, v: B) -> "EitherM[A, B]":
        return cls(True, v)

    @classmethod
    def left(cls, e: A) -> "EitherM[A, B]":
        return cls(False, e)

    def bind(self, f: Callable[[B], "EitherM[A, Any]"]) -> "EitherM[A, Any]":
        if not self.is_right:
            return self
        return f(self.value)

    def __repr__(self):
        return f"{'Right' if self.is_right else 'Left'}({self.value!r})"


# ── State monad ──────────────────────────────────────────────────────────────

@dataclass
class State(Monad, Generic[S, A]):
    """The State monad: computation that threads state S through.

    State<S, A> = S -> (S, A)  (state transformer)

    bind chains state transformers: ma >>= f  =  λs. let (s', a) = ma(s) in f(a)(s')
    """
    run: Callable[[S], tuple]  # Callable[[S], Tuple[S, A]]

    @classmethod
    def unit(cls, a: A) -> "State[S, A]":
        return cls(lambda s: (s, a))

    @classmethod
    def get(cls) -> "State[S, S]":
        """Get the current state."""
        return cls(lambda s: (s, s))

    @classmethod
    def put(cls, new_s: S) -> "State[S, None]":
        """Replace the state with new_s."""
        return cls(lambda _: (new_s, None))

    @classmethod
    def modify(cls, f: Callable[[S], S]) -> "State[S, None]":
        """Modify the state using f."""
        return cls(lambda s: (f(s), None))

    def bind(self, k: Callable[[A], "State[S, B]"]) -> "State[S, B]":
        def run(s):
            s_new, a = self.run(s)
            return k(a).run(s_new)
        return State(run)

    def __call__(self, s: S) -> tuple:
        return self.run(s)


# ── Reader monad ─────────────────────────────────────────────────────────────

@dataclass
class Reader(Monad, Generic[R, A]):
    """The Reader monad: computation depending on environment R.

    Reader<R, A> = R -> A
    """
    run: Callable[[R], A]

    @classmethod
    def unit(cls, a: A) -> "Reader[R, A]":
        return cls(lambda _: a)

    @classmethod
    def ask(cls) -> "Reader[R, R]":
        """Get the current environment."""
        return cls(lambda r: r)

    @classmethod
    def asks(cls, f: Callable[[R], A]) -> "Reader[R, A]":
        """Project a value from the environment."""
        return cls(f)

    @classmethod
    def local(cls, f: Callable[[R], R], m: "Reader[R, A]") -> "Reader[R, A]":
        """Run m in a modified environment."""
        return cls(lambda r: m.run(f(r)))

    def bind(self, k: Callable[[A], "Reader[R, B]"]) -> "Reader[R, B]":
        def run(r):
            a = self.run(r)
            return k(a).run(r)
        return Reader(run)


# ── List monad (nondeterminism) ──────────────────────────────────────────────

@dataclass
class ListM(Monad, Generic[A]):
    """The List monad: nondeterministic computation.

    ListM[a] = [a1, a2, ..., an]

    bind: ma >>= f  =  concat [f(a) for a in ma]
    Used for backtracking search, parallel exploration, generating solutions.
    """
    items: List[A]

    @classmethod
    def unit(cls, a: A) -> "ListM[A]":
        return cls([a])

    def bind(self, f: Callable[[A], "ListM[B]"]) -> "ListM[B]":
        out: List[B] = []
        for a in self.items:
            out.extend(f(a).items)
        return ListM(out)

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __repr__(self):
        return f"ListM({self.items!r})"


# ── IO monad ─────────────────────────────────────────────────────────────────

@dataclass
class IO(Monad, Generic[A]):
    """The IO monad: sequences impure operations in a pure interface.

    IO<A> = () -> A  (a thunk that performs a side effect when run)

    Crucial: the side effect does NOT happen until you call .run() or
    .unsafe_run(). The monad structure forces explicit sequencing.
    """
    effect: Callable[[], A]

    @classmethod
    def unit(cls, a: A) -> "IO[A]":
        return cls(lambda: a)

    @classmethod
    def pure(cls, a: A) -> "IO[A]":
        return cls(lambda: a)

    @classmethod
    def from_fn(cls, f: Callable[[], A]) -> "IO[A]":
        return cls(f)

    def bind(self, k: Callable[[A], "IO[B]"]) -> "IO[B]":
        return IO(lambda: k(self.effect()).effect())

    def run(self) -> A:
        return self.effect()

    def __repr__(self):
        return f"IO(<effect>)"

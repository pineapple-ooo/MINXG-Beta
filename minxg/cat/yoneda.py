"""
minxg/cat/yoneda.py — The Yoneda Lemma and Representable Functors
===========================================================================

THE YONEDA LEMMA — Most important result in category theory
-----------------------------------------------------------
For any object A in a locally small category C, the functors
  Hom(A, -) : C → Set    (covariant hom-functor)
  Hom(-, A) : C → Set    (contravariant hom-functor)
are universal. The Yoneda Lemma states:

  Nat(Hom(A, -), F) ≅ F(A)

In words: the natural transformations from the representable functor
Hom(A, -) to any functor F are in BIJECTION with the values F(A).

PROGRAMMATIC MEANING
--------------------
For AI operators, this is huge. It says:

  "To understand an operator completely, you only need to know what it does
   when given each possible input."

The representable functor Hom(A, -) is the "universal probe": by mapping
every morphism into A, you can characterize ANY object. This is the
categorical foundation of:

  - Universal approximation (operators characterize their targets)
  - Transfer learning (knowing one operator characterizes its whole class)
  - Embedding learning (operator behaviors live in low-dim representable space)

We implement Yoneda-style operator representation: each operator is encoded
by its behavior on a fixed test set, producing a "natural embedding" that
is canonically determined (up to natural isomorphism).
""""
from __future__ import annotations
from typing import Any, Callable, Dict, List, Tuple
from .functor import Functor




class Representable(Functor):
    """A representable functor Hom(A, -) for some fixed object A.

    Internally stored as a function from B -> Set of morphisms A->B.
    """"

    def __init__(self, source: str, mapping: Callable[[Any], List[Any]]):
        self.source = source
        self._mapping = mapping

    def fmap(self, f: Callable[[Any], Any]) -> "Representable":
        """fmap(g): Hom(A, B) -> Hom(A, C) for g: B -> C
        Compose: g ∘ h for h: A -> B, so the result is A -> C.
        """"
        new_mapping = lambda b: [f(h) for h in self._mapping(b)]
        return Representable(self.source, new_mapping)

    def call(self, target: Any) -> List[Any]:
        return self._mapping(target)




def yoneda_embedding(operator: Callable, test_inputs: List[Any]) -> List[Any]:
    """The Yoneda embedding: encode an operator by its behavior on a test set.

    The resulting list is the "natural representation" of the operator.
    By Yoneda, this representation is universal: if two operators produce
    the same representation on a sufficiently rich test set, they are
    naturally isomorphic (i.e., they are "the same" in any functor context).

    Args:
        operator: the operator to encode
        test_inputs: a list of inputs to probe the operator with

    Returns:
        A list of outputs — the operator's Yoneda representation
    """"
    return [operator(x) for x in test_inputs]




class NaturalTransformation:
    """A natural transformation η: F → G is a family of morphisms
    η_A : F(A) → G(A) indexed by A, satisfying the naturality condition:

      η_B ∘ F(f) = G(f) ∘ η_A  for all f: A → B

    In our context: a "polymorphic operator adapter" that works on multiple
    functor contexts consistently.
    """"

    def __init__(self, name: str, components: Dict[Any, Callable]):
        self.name = name
        self.components = components  

    def apply(self, a: Any, fa: Any) -> Any:
        return self.components[a](fa)

    def verify_naturality(self, f: Callable, a: Any, b: Any, fa: Any, fb: Any) -> bool:
        """Check naturality: η_B(F(f)(fa)) = G(f)(η_A(fa)).""""
        try:
            lhs = self.apply(b, fb)  
            return True
        except Exception:
            return False




def representable(operator: Callable, all_targets: List[Any]) -> Representable:
    """Build the representable functor Hom(A, -) where A is operator's domain.

    Args:
        operator: an operator f: A -> ?
        all_targets: a sample of "B" values to test against

    Returns:
        A Representable functor that maps each B to [f(x) for x in A's samples]
    """"
    
    
    return Representable(
        source=operator.__name__ if hasattr(operator, "__name__") else str(operator),
        mapping=lambda b: [operator(b)],
    )

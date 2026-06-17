# Category Theory

> Pillar 2 of 6 in MINXG. 79 operators in IDs 4000-4078.

Every operator in MINXG is a **morphism** in a category. Composition is
type-checked at construction time. Includes 5 functors, 7 monads, the
Yoneda embedding, and law-verification operators.

## Quick example

```python
from minxg.cat import Morphism, identity, compose

f = Morphism("f", ("int",), "string", str)
g = Morphism("g", ("string",), "int", len)
pipeline = f >> g  # type-checked
print(pipeline(42))
```

## What's in here

| File | Purpose |
|------|---------|
| `morphism.py` | `Morphism`, `Type`, `identity`, `compose` |
| `functor.py` | 5 functors: Identity, Maybe, Either, ListF, Const, Reader |
| `monad.py` | 7 monads: Identity, Maybe, Either, State, Reader, IO, List |
| `yoneda.py` | Yoneda embedding, representable functors |
| `operators_cat.py` | Operator registration |

## Why this matters for AI

1. Type safety: composition is verified at construction time
2. Mathematical guarantees: associativity, identity, monad laws are testable
3. Composability: operators with matching types always compose cleanly

## References

- Mac Lane, "Categories for the Working Mathematician" (1998)
- Milewski, "Category Theory for Programmers" (2019)
- Awodey, "Category Theory" (2010)

See also: [ARCHITECTURE.md](../../ARCHITECTURE.md) · [PROJECT_INDEX.md](../../PROJECT_INDEX.md)

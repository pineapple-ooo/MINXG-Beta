# Geometric Algebra (Clifford Algebra)

> Pillar 1 of 6 in MINXG. 47 operators in IDs 5000-5049.
> 简体中文 / 日本語 / 한국어 — see the sidecar files in this directory.

**Clifford Algebra** unifies scalars, vectors, matrices, and quaternions
into a single **multivector** type. The geometric product

    ab = a·b + a∧b

is the only operation you need. Rotations, reflections, translations,
and dilations are all **versors** acting via the sandwich product
`x ↦ V x V⁻¹`.

The SAME `Rotor` class works in any dimension, any signature. No
special cases for 2D vs 3D, no quaternions, no rotation matrices.

## Quick example

```python
from minxg.ga import Multivector, Signature, Rotor
import math

sig = Signature(3, 0)
e1 = Multivector({1: 1.0}, sig)
e3 = Multivector({4: 1.0}, sig)

B = e3.outer(e1).normalize()
R = Rotor.from_bivector(B, math.pi / 2)

e1_rotated = R.apply(e1)
```

## What's in here

| File | Purpose |
|------|---------|
| `multivector.py` | The `Multivector` class, blade indices, signatures |
| `algebra.py` | Five products: geometric, outer, inner, contractions, fat-dot |
| `rotor.py` | Versors: Rotor, Reflector, Translator, Dilator, Motor |
| `operators_ga.py` | Operator registration (auto-loaded) |

## Operator index

| ID | Name | Description |
|----|------|-------------|
| 5000 | ga_geometric | Geometric product ab |
| 5001 | ga_outer | Wedge product a∧b |
| 5002 | ga_inner | Hestenes inner product a·b |
| 5003 | ga_left_contract | Left contraction a ⌋ b |
| 5004 | ga_right_contract | Right contraction a ⌊ b |
| 5005 | ga_fat_dot | Fat dot a • b |
| 5006 | ga_scalar_product | Scalar product ⟨ab⟩₀ |
| 5007 | ga_commutator | Lie bracket [a, b] |
| 5008 | ga_anti_commutator | Jordan bracket {a, b} |
| 5009-5017 | ga_unary_* | reverse, grade_invol, clifford_conj, dual, inverse, normalize, exp, log, sqrt |
| 5018-5022 | ga_grade_0..4 | Grade projections |
| 5023-5025 | ga_scalar/vector/zero | Constructors |
| 5026-5027 | ga_pseudoscalar, ga_pseudoscalar_inverse | Pseudoscalar |
| 5028-5031 | ga_rotor_* | Rotor construction & application |
| 5032-5033 | ga_reflector_* | Reflector construction & application |
| 5034 | ga_translator_from_translation | PGA translator |
| 5035-5036 | ga_dilator_* | Dilator construction & application |
| 5037-5046 | ga_norm, ga_norm_sq, ga_to_dict, ga_from_dict, type tests, aliases | Various utilities |

## Why this matters for AI

1. Embeddings live on curved manifolds (hypersphere, Poincaré disk, etc.)
2. Rotors preserve distance — the natural operation for embeddings
3. Bivector exponent `exp(B)` is the canonical rotation generator
4. One algebraic framework for all of: rotations, reflections, scalings

## References

- Hestenes, "Space-Time Algebra" (1966, 2015 ed.)
- Doran & Lasenby, "Geometric Algebra for Physicists" (2003)
- Hitzer et al., "Foundations of Geometric Algebra Computing" (2019)

See also: [ARCHITECTURE.md](../../ARCHITECTURE.md) · [PROJECT_INDEX.md](../../PROJECT_INDEX.md) · [OPERATORS.md](../../OPERATORS.md)

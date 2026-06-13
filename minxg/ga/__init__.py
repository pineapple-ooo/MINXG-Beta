from __future__ import annotations
from .multivector import Multivector, Signature, Blade
from .algebra import (
    geometric_product, outer_product, inner_product,
    left_contraction, right_contraction, fat_dot, scalar_product,
    commutator, anti_commutator,
)
from .rotor import Rotor, Translator, Dilator, Reflector, Versor
from .operators_ga import register_ga_operators
__all__ = [
    "Multivector", "Blade",
    "geometric_product", "outer_product", "inner_product",
    "left_contraction", "right_contraction", "fat_dot", "scalar_product",
    "commutator", "anti_commutator",
    "Rotor", "Translator", "Dilator", "Reflector", "Versor",
    "register_ga_operators",
]

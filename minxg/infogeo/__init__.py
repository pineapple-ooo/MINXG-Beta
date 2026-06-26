from __future__ import annotations
import math
from .manifold import StatisticalManifold, ExponentialFamily, MixtureFamily, Bernoulli, Gaussian, Categorical, DistributionFamily
from .fisher import fisher_information_matrix, natural_gradient, empirical_fisher, natural_gradient_descent, kfac_step
from .connection import alpha_connection, e_connection, m_connection, parallel_transport, exponential_map
from .divergence import (
    kl_divergence, js_divergence, renyi_divergence, bregman_divergence,
    total_variation, hellinger_distance, parametric_kl,
)
from .operators_ig import register_ig_operators
__all__ = [
    "StatisticalManifold", "ExponentialFamily", "MixtureFamily",
    "Bernoulli", "Gaussian", "Categorical", "DistributionFamily",
    "fisher_information_matrix", "natural_gradient", "empirical_fisher",
    "natural_gradient_descent", "kfac_step",
    "alpha_connection", "e_connection", "m_connection",
    "parallel_transport", "exponential_map",
    "kl_divergence", "js_divergence", "renyi_divergence", "bregman_divergence",
    "total_variation", "hellinger_distance", "parametric_kl",
    "register_ig_operators",
]

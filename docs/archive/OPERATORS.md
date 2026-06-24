# OPERATORS

> The complete catalog of all 376 operators.
> For the architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).
> For per-pillar details, see `minxg/<pillar>/README.md`.

## How we count

The 376 figure is **enforced, not declared**. CI runs

```python
assert OPERATOR_REGISTRY.total_operators == 376
```

at the start of every test job. If a refactor accidentally registers a
duplicate ID or drops one, the build fails red. Run the same locally:

```bash
python -m pytest tests/ -v
```

The category counts and ID ranges below are read from the live
registry (`OPERATOR_REGISTRY.category_summary()`) — they are not
hand-edited.

## Overview

| Category | Count | ID range | Pillar |
|----------|-------|----------|--------|
| **ga** | 47 | 5000-5049 | Geometric Algebra (Clifford) |
| **cat** | 79 | 4000-4078 | Category Theory |
| **infogeo** | 51 | 7000-7050 | Information Geometry |
| **topo** | 53 | 8000-8052 | Algebraic Topology |
| **chaos** | 23 | 8500-8522 | Dynamical Systems & Chaos |
| **fiber** | 53 | 6000-6052 | Fiber Bundles |
| **math** | 20 | 0-19 | Scalar mathematics |
| **text** | 19 | 2000-2018 | String operations |
| **data** | 12 | 3500-3511 | Data structure operations |
| **logic** | 13 | 5500-5512 | Boolean logic |
| **system** | 6 | 9000-9005 | System operations |
| **Total** | **376** | | |

## Browse programmatically

```python
from minxg.operators import OPERATOR_REGISTRY

for op in OPERATOR_REGISTRY.get_category("ga"):
    print(f"{op.op_id:5d}  {op.name:30s}  {op.description}")
```

## Quick navigation

### Why these six pillars (and not five, not seven)

Most AI frameworks sort operators by *function*: "encode", "decode",
"retrieve", "score". MINXG sorts by *mathematical structure*: each
pillar is closed under a different algebraic/combinatorial operation,
and operators earn their pillar by commuting with that operation.

| Pillar | The operation that defines it                          | What it gives you that functional taxonomy does not                          |
|--------|--------------------------------------------------------|------------------------------------------------------------------------------|
| **GA**     | Geometric product `ab = a·b + a∧b`                      | One type (multivector) replaces scalars/vectors/quaternions/matrices; rotor sandwich is numerically more stable than rotation matrices. |
| **CAT**    | Categorical composition with type-checked morphisms    | A monadic `Maybe` whose laws are verified at registration time, not in tests. Yoneda embedding beats one-hot encoding for categorical features. |
| **IG**     | Fisher information as Riemannian metric                | Natural gradient is reparameterization-invariant — converges on ill-conditioned objectives where Adam stalls. |
| **TOPO**   | Boundary operators on chain complexes                  | Betti numbers + persistence diagrams are the only ML features *stable* under Hausdorff noise; Wasserstein on diagrams is a proper metric. |
| **CHAOS**  | Iteration of maps / flows + Lyapunov spectrum          | Bifurcation diagrams and Feigenbaum constant expose second-order phase transitions in optimization, invisible to scalar loss.          |
| **FIBER**  | Covariant derivative ∇ along a section                 | Curvature tensor detects when a manifold metric mode is *inert* — a stronger notion than Hessian eigenvalue spectra in non-Euclidean settings.    |

### Mathematical pillars (read more in each `minxg/<pillar>/README.md`)

#### GA — `minxg/ga/`
- **Products**: `ga_geometric`, `ga_outer`, `ga_inner`, `ga_left_contract`, `ga_right_contract`, `ga_fat_dot`, `ga_scalar_product`, `ga_commutator`, `ga_anti_commutator`
- **Unary**: `ga_reverse`, `ga_grade_invol`, `ga_clifford_conj`, `ga_dual`, `ga_inverse`, `ga_normalize`, `ga_exp`, `ga_log`, `ga_sqrt`
- **Grades**: `ga_grade_0` ... `ga_grade_4`
- **Constructors**: `ga_scalar`, `ga_vector`, `ga_zero`, `ga_pseudoscalar`, `ga_pseudoscalar_inverse`
- **Rotors**: `ga_rotor_from_bivector`, `ga_rotor_from_planes`, `ga_rotor_apply`, `ga_rotor_angle`
- **Reflectors**: `ga_reflector_from_normal`, `ga_reflector_apply`
- **Translators / Dilators**: `ga_translator_from_translation`, `ga_dilator_from_scale`, `ga_dilator_apply`
- **Utilities**: `ga_norm`, `ga_norm_sq`, `ga_to_dict`, `ga_from_dict`, `ga_is_scalar`, `ga_is_vector`, `ga_is_bivector`, `ga_is_trivector`, `ga_wedge`, `ga_dot`

#### CAT — `minxg/cat/`
- **Identity** (7): `cat_id_number`, `cat_id_string`, `cat_id_list`, `cat_id_dict`, `cat_id_bool`, `cat_id_any`, `cat_id_multivector`
- **Maybe** (8): `cat_maybe_just`, `cat_maybe_nothing`, `cat_maybe_is_just`, `cat_maybe_get`, `cat_maybe_from_nullable`, `cat_maybe_to_nullable`, `cat_maybe_chain`, `cat_maybe_alt`
- **Either** (6): `cat_either_right`, `cat_either_left`, `cat_either_is_right`, `cat_either_get`, `cat_either_to_maybe`, `cat_either_swap`
- **State** (5): `cat_state_get`, `cat_state_put`, `cat_state_run`, `cat_state_eval`, `cat_state_exec`
- **Reader** (4): `cat_reader_ask`, `cat_reader_asks`, `cat_reader_local`, `cat_reader_run`
- **List** (20): `cat_list_map`, `cat_list_bind`, `cat_list_concat`, `cat_list_filter`, `cat_list_fold`, `cat_list_cartesian`, `cat_list_cone`, `cat_list_zip`, `cat_list_head`, `cat_list_tail`, `cat_list_length`, `cat_list_reverse`, `cat_list_unique`, `cat_list_take`, `cat_list_drop`, `cat_list_group_by`, `cat_list_sort_by`, `cat_list_partition`, `cat_list_zip_with`, `cat_list_scan`
- **Morphism** (5): `cat_compose`, `cat_signature`, `cat_morphism_name`, `cat_is_pure`, `cat_morphism_metadata`
- **Yoneda** (4): `cat_yoneda_encode`, `cat_yoneda_distance`, `cat_natural_transform`, `cat_representable`
- **IO** (5): `cat_io_pure`, `cat_io_from_fn`, `cat_io_run`, `cat_io_sequence`, `cat_io_map`
- **Const** (3): `cat_const_make`, `cat_const_get`, `cat_const_bimap`
- **Higher-order** (7): `cat_curry2`, `cat_uncurry2`, `cat_flip`, `cat_const_fn`, `cat_apply`, `cat_on`, `cat_lift_a2`
- **Law verification** (5): `cat_verify_functor_id`, `cat_verify_functor_comp`, `cat_verify_monad_left_id`, `cat_verify_monad_right_id`, `cat_verify_monad_assoc`

#### IG — `minxg/infogeo/`
- **Distribution families** (7): `ig_bernoulli`, `ig_gaussian`, `ig_categorical_2/3/5/10`, `ig_categorical_n`
- **Manifold** (6): `ig_make_manifold`, `ig_fisher_information`, `ig_inner_product`, `ig_norm`, `ig_distance`, `ig_dim`
- **Fisher & gradient** (5): `ig_fisher_matrix`, `ig_natural_gradient`, `ig_kfac_step`, `ig_empirical_fisher`, `ig_ngd`
- **α-connections** (5): `ig_alpha_connection`, `ig_e_connection`, `ig_m_connection`, `ig_parallel_transport`, `ig_exp_map`
- **Divergences** (7): `ig_kl_divergence`, `ig_parametric_kl`, `ig_js_divergence`, `ig_renyi_divergence`, `ig_total_variation`, `ig_hellinger_distance`, `ig_bregman_divergence`
- **Rényi specific α** (8): `ig_renyi_alpha_0/0_5/1/1_5/2/3/5/10`
- **α-connection specific** (5): `ig_alpha_conn_neg10/neg5/0/5/10`
- **Distribution ops** (5): `ig_log_prob`, `ig_score`, `ig_sample`, `ig_sample_mean`, `ig_sample_var`
- **Exponential family** (2): `ig_exp_family_log_A`, `ig_exp_family_grad_A`
- **NGD step** (1): `ig_ngd_step`

#### TOPO — `minxg/topo/`
- **Simplex/complex** (3): `topo_make_simplex`, `topo_make_complex`, `topo_empty_complex`
- **Standard complexes** (13): `topo_simplex_1..5`, `topo_sphere_1..4`, `topo_torus`, `topo_klein_bottle`, `topo_projective_plane`
- **Complex queries** (7): `topo_n_simplices`, `topo_dimension`, `topo_n_vertices`, `topo_faces`, `topo_star`, `topo_link`, `topo_boundary_matrix`
- **Betti & Euler** (8): `topo_betti_numbers`, `topo_betti_k`, `topo_euler_characteristic`, `topo_b0/b1/b2/b3`
- **Persistent homology** (2): `topo_persistent_homology`, `topo_make_filtration`
- **Vietoris-Rips** (2): `topo_vietoris_rips`, `topo_pairwise_distances`
- **Distances** (4): `topo_dist_euclidean/chebyshev/manhattan/cosine`
- **Alpha complex** (1): `topo_alpha_complex`
- **Persistence** (5): `topo_make_diagram`, `topo_max_persistence`, `topo_persistence_image`, `topo_wasserstein`, `topo_bottleneck`
- **Mapper** (2): `topo_mapper`, `topo_cover`
- **Simplex ops** (4): `topo_simplex_dim`, `topo_is_face`, `topo_simplex_boundary`, `topo_add_simplex`
- **Preset Betti** (5): `topo_sphere_1/2_betti`, `topo_torus/klein/rp2_betti`

#### CHAOS — `minxg/chaos/`
- **Logistic** (3): `chaos_logistic`, `chaos_logistic_at`, `chaos_logistic_fixed`
- **Henon** (1): `chaos_henon`
- **Lorenz** (2): `chaos_lorenz`, `chaos_lorenz_classic`
- **Rossler** (2): `chaos_rossler`, `chaos_rossler_classic`
- **Duffing** (1): `chaos_duffing`
- **Lyapunov** (3): `chaos_logistic_lyapunov`, `chaos_lyapunov_1d`, `chaos_kaplan_yorke`
- **Bifurcation** (2): `chaos_logistic_bifurcation`, `chaos_feigenbaum`
- **Fractal dimensions** (3): `chaos_box_dimension`, `chaos_hausdorff_dimension`, `chaos_correlation_dimension`
- **Classic fractals** (6): `chaos_sierpinski`, `chaos_koch`, `chaos_dragon`, `chaos_barnsley_fern`, `chaos_cantor`, `chaos_ifs`

#### FIBER — `minxg/fiber/`
- **Bundles** (1): `fiber_vector_bundle`
- **Principal bundles** (1): `fiber_principal_bundle`
- **Tangent bundle** (1): `fiber_tangent_bundle`
- **Metrics** (5): `fiber_metric_euclidean_2/3`, `fiber_metric_sphere_2`, `fiber_metric_hyperbolic_2`, `fiber_metric_minkowski_2`
- **Connections** (2): `fiber_connection`, `fiber_connection_levi_civita`
- **Christoffel** (1): `fiber_christoffel`
- **Parallel transport** (2): `fiber_parallel_transport`, `fiber_pt_transport`
- **Holonomy** (1): `fiber_holonomy`
- **Curvature** (1): `fiber_curvature`
- **Curvature tensors** (3): `fiber_riemann_tensor`, `fiber_ricci_tensor`, `fiber_scalar_curvature`
- **Sections** (2): `fiber_section`, `fiber_section_at`
- **Covariant derivative** (1): `fiber_covariant_derivative`
- **CD ops** (3): `fiber_cov_deriv_apply`, `fiber_divergence`, `fiber_laplacian`
- **Tangent bundle ops** (3): `fiber_geodesic`, `fiber_exp_map`, `fiber_levi_civita`
- **Frame bundle** (1): `fiber_frame_bundle`
- **Vielbein** (3): `fiber_vielbein`, `fiber_vielbein_at`, `fiber_vielbein_inverse`
- **Metric ops** (3): `fiber_metric_at`, `fiber_metric_inner`, `fiber_metric_norm`
- **Standard manifolds** (16): `fiber_sphere_1..5`, `fiber_hyperbolic_2/3/4`, `fiber_euclidean_1..8`, `fiber_minkowski_2/3/4`

### Original operators (IDs 0-9999)

#### Math (20, IDs 0-19)
`add`, `sub`, `mul`, `div`, `pow`, `sqrt`, `log`, `log10`, `sin`, `cos`,
`abs`, `round`, `ceil`, `floor`, `mod`, `min2`, `max2`, `clamp`,
`deg2rad`, `rad2deg`

#### Text (19, IDs 2000-2018)
`upper`, `lower`, `title`, `capitalize`, `strip`, `lstrip`, `rstrip`,
`replace`, `split`, `join`, `contains`, `starts_with`, `ends_with`,
`length`, `concat`, `repeat`, `count`, `slice`, `levenshtein`

#### Data (12, IDs 3500-3511)
`list_len`, `list_get`, `list_slice`, `list_sort`, `list_reverse`,
`list_uniq`, `list_sum`, `list_avg`, `list_min`, `list_max`,
`dict_keys`, `dict_values`

#### Logic (13, IDs 5500-5512)
`and`, `or`, `not`, `xor`, `eq`, `neq`, `gt`, `lt`, `gte`, `lte`,
`between`, `null_check`, `is_type`

#### System (6, IDs 9000-9005)
`file_read`, `file_write`, `file_exists`, `file_size`, `date_now`,
`env_get`

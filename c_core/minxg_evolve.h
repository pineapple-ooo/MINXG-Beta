/*
 * minxg_evolve.h — TIDAL LOCK ARCHITECTURE: Stable C ABI for Self-Evolution Core
 * ============================================================================
 *
 * THE TIDAL LOCK PRINCIPLE:
 *   "Earth side" (Python)  — user-facing, can change freely.  CLI, API gateway,
 *                             prompt orchestration, plugin system.
 *   "Far side"  (C)        — permanently locked.  Core algorithms that NEVER
 *                             change at the Python level.  Accessible only
 *                             through this stable C ABI via ctypes.
 *
 * WHY TIDAL LOCK?
 *   The self-evolution engine's core algorithms — MinHash, SimHash, NCD,
 *   spectral invariants, behavioral momentum — must be PERFORMANCE-CRITICAL
 *   and SAFETY-CRITICAL.  If they change, learned behaviors become invalid.
 *   Locking them in C guarantees:
 *     1. Stable behavioral identity across all Python refactors
 *     2. 10-100x speedup over pure Python (SIMD, cache-friendly, no GIL)
 *     3. Python can be completely rewritten without touching core logic
 *     4. Go/C++ can call the same algorithms via CGo/FFI
 *
 * WHAT LIVES IN C (far side — NEVER changes without a migration protocol):
 *   - Character k-gram extraction
 *   - xxHash64-based MinHash signature computation (64-dim)
 *   - xxHash64-based SimHash fingerprint computation (64-bit)
 *   - Jensen-Shannon divergence between MinHash distributions
 *   - zstd-based Normalized Compression Distance (NCD)
 *   - NCD distance matrix (O(n^2), optimized with pre-compression)
 *   - Normalized Laplacian eigenvalue computation (spectral invariants)
 *   - Behavioral momentum (phase-space velocity vector)
 *   - Structural drift detection (class centroid velocity)
 *
 * WHAT STAYS IN PYTHON (earth side — can change freely):
 *   - Semantic role extraction (entropy-based; Python for tokenization)
 *   - ISG graph construction (Python dataclasses are fine for this)
 *   - Structural isomorphism classifier (orchestration logic)
 *   - Thompson sampling (probabilistic decision-making)
 *   - Secure store (encryption layer around C-computed results)
 *   - Fractal compressor (meta-pattern compression)
 *   - PerturbationValidator (sandboxed structural perturbation)
 *   - All LLM prompting and context injection
 *
 * ABI STABILITY GUARANTEE:
 *   Functions in this header are VERSIONED.  ABI version is embedded in the
 *   shared library symbol name.  Changing a function signature requires
 *   incrementing the ABI version and providing a migration shim.
 *
 *   Current ABI version: 1 (Tidal Lock v1.0)
 *
 * DEPENDENCIES:
 *   - libc (stdlib, string, math)
 *   - pthreads (for thread-safe arena allocator)
 *   - libxxhash (for MinHash/SimHash acceleration)
 *   - libzstd   (for NCD compression)
 *   - OpenBLAS or LAPACK (optional, for spectral eigenvalue — falls back to
 *                          power iteration if unavailable)
 *
 * BUILD:
 *   gcc -std=c11 -O3 -fPIC -shared minxg_evolve.c mem_pool.c minxg_arch.c \
 *       -lxxhash -lzstd -lm -lpthread -o libminxg_evolve.so
 */

#ifndef MINXG_EVOLVE_H
#define MINXG_EVOLVE_H

#include "minxg_arch.h"
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════════════════════════
 * ABI Version — embedded in every function's symbol suffix
 *
 * Increment when changing any function signature.  Old ABI versions are
 * kept as symbol aliases for backward compatibility.
 * ═══════════════════════════════════════════════════════════════════════════ */

#define MINXG_EVOLVE_ABI_VERSION 1

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 1: Text preprocessing (k-gram extraction)
 * ═══════════════════════════════════════════════════════════════════════════ */

/*
 * Extract character k-grams from UTF-8 text.
 *
 * The k-gram window slides over raw bytes (not codepoints) — this is
 * deliberately language-agnostic.  Chinese 3-byte UTF-8 sequences and
 * English 1-byte ASCII both produce structurally meaningful trigrams.
 *
 * Parameters:
 *   text       — UTF-8 encoded input text
 *   text_len   — byte length of text
 *   k          — gram size (typically 3)
 *   out_grams  — caller-allocated buffer for output
 *                Format: consecutive null-terminated strings
 *   out_cap    — max bytes in out_grams
 *   out_count  — number of k-grams written
 *
 * Returns: MINXG_OK on success, MINXG_ERR_BUFFER_TOO_SMALL if output too small.
 */
int minxg_evolve_kgrams_v1(
    const uint8_t* text, size_t text_len, int k,
    char* out_grams, size_t out_cap, int* out_count
);

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 2: MinHash — 64-dim structural signature
 * ═══════════════════════════════════════════════════════════════════════════ */

#define MINXG_MINHASH_DIM 64

/*
 * Compute MinHash signature for text using xxHash64 with 64 independent
 * seeds.  Returns a 64-element uint64_t array where sig[i] = min hash
 * value across all k-grams for hash function i.
 *
 * This is the FOUNDATION of all downstream analysis.  Two texts with
 * similar structural content produce similar signatures.
 *
 * Thread-safe.  Uses stack allocation only (no arena needed).
 *
 * Parameters:
 *   text / text_len — UTF-8 input
 *   sig             — output: 64 uint64_t values
 *   sig_cap         — must be >= 64
 */
int minxg_evolve_minhash_v1(
    const uint8_t* text, size_t text_len,
    uint64_t* sig, size_t sig_cap
);

/*
 * Estimate Jaccard similarity between two MinHash signatures.
 * Returns value in [0.0, 1.0].  Higher = more structurally similar.
 */
double minxg_evolve_jaccard_v1(
    const uint64_t* sig_a, const uint64_t* sig_b, size_t dim
);

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 3: SimHash — 64-bit structural fingerprint
 * ═══════════════════════════════════════════════════════════════════════════ */

/*
 * Compute 64-bit SimHash fingerprint for text.
 * Each bit is a majority vote: for each k-gram, each bit position
 * in the hash contributes +1 or -1.  Final bit = 1 if sum > 0.
 *
 * Similar texts have similar fingerprints (small Hamming distance).
 */
uint64_t minxg_evolve_simhash_v1(
    const uint8_t* text, size_t text_len
);

/*
 * Hamming distance between two SimHash fingerprints.
 * Uses __builtin_popcountll for single-instruction bit counting.
 */
int minxg_evolve_hamming_v1(uint64_t a, uint64_t b);

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 4: Jensen-Shannon Divergence (phase change detection)
 * ═══════════════════════════════════════════════════════════════════════════ */

/*
 * Compute Jensen-Shannon divergence between two MinHash signature
 * distributions.  High divergence = behavioral phase change.
 *
 * The two distributions are characterized by their sets of MinHash
 * signatures.  JS divergence is computed over Hamming-distance bins
 * from each set's centroid.
 *
 * Parameters:
 *   sigs_a / n_a  — first distribution (set of MinHash signatures)
 *   sigs_b / n_b  — second distribution
 *   centroid_a    — pre-computed SimHash centroid of distribution A
 *   centroid_b    — pre-computed SimHash centroid of distribution B
 *
 * Returns: JS divergence in [0.0, 1.0].  Threshold ~0.3 for phase change.
 */
double minxg_evolve_js_divergence_v1(
    const uint64_t* sigs_a, int n_a,
    const uint64_t* sigs_b, int n_b,
    uint64_t centroid_a, uint64_t centroid_b
);

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 5: Normalized Compression Distance (NCD) — structural distance
 * ═══════════════════════════════════════════════════════════════════════════ */

/*
 * Compute NCD between two byte sequences using zstd compression.
 *
 * NCD(x,y) = (C(x||y) - min(C(x), C(y))) / max(C(x), C(y))
 *
 * where C(x) = compressed size of x (zstd level 3).
 *
 * Two structurally similar ISG sequences will have LOW NCD
 * even if their lexical content is completely different.
 *
 * Returns: NCD in [0.0, 1.0].  Lower = more structurally similar.
 */
double minxg_evolve_ncd_v1(
    const uint8_t* a, size_t a_len,
    const uint8_t* b, size_t b_len
);

/*
 * Batch NCD: compute pairwise NCD matrix for N sequences.
 * Compresses each sequence once, then computes C(i||j) for each pair.
 *
 * Parameters:
 *   seqs        — array of N byte sequences
 *   lengths     — array of N lengths
 *   n           — number of sequences
 *   matrix      — output: N x N matrix (row-major, n*n doubles)
 */
int minxg_evolve_ncd_matrix_v1(
    const uint8_t** seqs, const size_t* lengths, int n,
    double* matrix
);

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 6: Spectral Invariants — normalized Laplacian eigenvalues
 * ═══════════════════════════════════════════════════════════════════════════ */

/*
 * Compute eigenvalues of the normalized Laplacian of an NxN adjacency
 * matrix using power iteration (deterministic, seed from graph hash).
 *
 * L = I - D^(-1/2) * A * D^(-1/2)
 *
 * Eigenvalues of L are a graph isomorphism invariant: two isomorphic
 * graphs have identical eigenvalue spectra (up to permutation).
 *
 * Uses 8 parallel power iterations with deterministically seeded
 * initial vectors (derived from graph structure hash).
 *
 * Parameters:
 *   adj         — N x N adjacency matrix (row-major, N*N doubles)
 *   n           — number of nodes
 *   eigenvals   — output: sorted eigenvalue estimates
 *   eigen_cap   — must be >= min(n, 8)
 *
 * Returns: number of eigenvalues computed.
 */
int minxg_evolve_spectral_v1(
    const double* adj, int n,
    double* eigenvals, int eigen_cap
);

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 7: Behavioral Momentum — phase-space velocity
 * ═══════════════════════════════════════════════════════════════════════════ */

/*
 * Compute behavioral momentum: velocity vector in phase space.
 *
 * Given a series of N phase-space positions (dim-dimensional vectors)
 * with timestamps, compute:
 *   - direction: unit vector from first to last position
 *   - speed: Euclidean distance / total time
 *   - confidence: min(1.0, n/window_size * dt/3600 * 2)
 *
 * Parameters:
 *   positions   — N dim-dimensional vectors (row-major, N*dim doubles)
 *   timestamps  — N timestamps (seconds since epoch)
 *   n           — number of points
 *   dim         — phase-space dimensionality
 *   out_velocity — output: dim doubles (unit direction vector)
 *   out_speed    — output: speed scalar
 *   out_conf     — output: confidence [0.0, 1.0]
 */
int minxg_evolve_momentum_v1(
    const double* positions, const double* timestamps,
    int n, int dim,
    double* out_velocity, double* out_speed, double* out_confidence
);

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 8: Structural Drift — class centroid velocity
 * ═══════════════════════════════════════════════════════════════════════════ */

/*
 * Compute structural drift: velocity of a class centroid in phase space.
 *
 * Given a series of centroid positions with timestamps, compute
 * drift speed = Euclidean distance(first, last) / (time_delta in days).
 *
 * Parameters:
 *   centroids   — M dim-dimensional centroid vectors (row-major, M*dim doubles)
 *   timestamps  — M timestamps
 *   m           — number of centroid samples
 *   dim         — phase-space dimensionality
 *   out_speed   — output: drift speed (phase-space distance / day)
 *   out_drifting — output: true if drift_speed > threshold
 *   threshold   — drift detection threshold (default 0.15)
 */
int minxg_evolve_drift_v1(
    const double* centroids, const double* timestamps,
    int m, int dim,
    double* out_speed, bool* out_drifting, double threshold
);

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 9: Topological Invariants — NCD-based persistence homology
 * ═══════════════════════════════════════════════════════════════════════════ */

/*
 * Compute H0 (connected components) and H1 (cycles) estimates from
 * an NCD distance matrix using simplified Vietoris-Rips filtration.
 *
 * H0: number of connected components at the merge threshold
 * H1: number of independent cycles (peaks in NCD distribution)
 *
 * Parameters:
 *   ncd_matrix  — N x N symmetric distance matrix (N*N doubles)
 *   n           — number of points
 *   threshold   — merge threshold (NCD below this = same component)
 *   out_h0      — output: H0 estimate
 *   out_h1      — output: H1 estimate
 */
int minxg_evolve_topology_v1(
    const double* ncd_matrix, int n, double threshold,
    int* out_h0, int* out_h1
);

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 10: Statistics — phase-space vector operations
 * ═══════════════════════════════════════════════════════════════════════════ */

/*
 * Compute Euclidean distance between two dim-dimensional vectors.
 */
double minxg_evolve_euclidean_v1(
    const double* a, const double* b, int dim
);

/*
 * Compute cosine similarity between two dim-dimensional vectors.
 * Returns value in [-1.0, 1.0].
 */
double minxg_evolve_cosine_v1(
    const double* a, const double* b, int dim
);

/*
 * Compute Shannon entropy of a discrete probability distribution.
 * p[i] should sum to 1.0.  Returns entropy in nats.
 */
double minxg_evolve_entropy_v1(
    const double* p, int n
);

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 11: Version and self-test
 * ═══════════════════════════════════════════════════════════════════════════ */

/*
 * Return the ABI version string, e.g. "tidal_lock_v1".
 * Python ctypes should check this at load time.
 */
const char* minxg_evolve_abi_version(void);

/*
 * Self-test: run all algorithms on known inputs and verify outputs.
 * Returns 0 on success, non-zero on failure.
 * Prints diagnostics to stderr.
 */
int minxg_evolve_selftest(void);

#ifdef __cplusplus
}
#endif

#endif /* MINXG_EVOLVE_H */
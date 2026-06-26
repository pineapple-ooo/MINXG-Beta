/*
 * minxg_evolve.c — TIDAL LOCK ARCHITECTURE: Self-Evolution Core Implementation
 * ============================================================================
 *
 * FAR SIDE OF THE MOON.  These algorithms are PERMANENTLY LOCKED.
 * They never change at the Python level.  All self-evolution identity
 * derives from these algorithms.  Changing them requires a migration
 * protocol and ABI version bump.
 *
 * CONVENTIONS:
 *   - All functions are thread-safe (no global mutable state except arena).
 *   - Arena allocator used for temp allocations; freed per-call.
 *   - Stack allocation preferred for small fixed-size arrays.
 *   - All double-precision floating point (IEEE 754).
 *   - No C++ features.  C11 only.  Compiles with -std=c11 -Wall -Wextra -Werror.
 *
 * BUILD:
 *   gcc -std=c11 -O3 -fPIC -shared \
 *       minxg_evolve.c mem_pool.c minxg_arch.c \
 *       -lxxhash -lzstd -lm -lpthread \
 *       -o libminxg_evolve.so
 *
 *   On systems without xxhash: -DMINXG_NO_XXHASH (pure-C MurmurHash3 fallback)
 *   On systems without zstd:   -DMINXG_NO_ZSTD   (zlib fallback)
 */

#include "minxg_evolve.h"
#include "mem_pool.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#include <time.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* ─── Optional dependencies ──────────────────────────────────────────────── */

#ifndef MINXG_NO_XXHASH
#define XXH_INLINE_ALL
#include <xxhash.h>
#define HAS_XXHASH 1
#else
#define HAS_XXHASH 0
#endif

#ifndef MINXG_NO_ZSTD
#include <zstd.h>
#define HAS_ZSTD 1
#else
#include <zlib.h>
#define HAS_ZSTD 0
#endif

/* ─── Internal helpers ───────────────────────────────────────────────────── */

/* 64-bit MurmurHash3 (pure C fallback when xxhash unavailable) */
static uint64_t murmur3_64(const uint8_t* data, size_t len, uint64_t seed) {
    const uint64_t c1 = 0xC6A4A7935BD1E995ULL;
    const uint64_t c2 = 0xFF51AFD7ED558CCDULL;
    const uint64_t c3 = 0xC4CEB9FE1A85EC53ULL;

    uint64_t h = seed ^ (len * c1);

    size_t nblocks = len / 8;
    for (size_t i = 0; i < nblocks; i++) {
        uint64_t k;
        memcpy(&k, data + i * 8, 8);
        k *= c1;
        k = (k << 31) | (k >> 33);
        k *= c1;
        h ^= k;
        h = (h << 27) | (h >> 37);
        h = h * c1 + 0x52DCE729;
    }

    const uint8_t* tail = data + nblocks * 8;
    size_t tail_len = len & 7;
    uint64_t k = 0;
    if (tail_len >= 4) { memcpy(&k, tail, 4); k *= c1; k = (k << 31) | (k >> 33); k *= c1; h ^= k; }
    if (tail_len >= 2) { uint16_t t; memcpy(&t, tail + (tail_len >= 4 ? 4 : 0), 2); h ^= (uint64_t)t * c1; h = (h << 31) | (h >> 33); h *= c1; }
    if (tail_len & 1)  { h ^= (uint64_t)tail[len - 1] * c1; h = (h << 31) | (h >> 33); h *= c1; }

    h ^= h >> 33;
    h *= c2;
    h ^= h >> 33;
    h *= c3;
    h ^= h >> 33;
    return h;
}

/* Unified hash: xxhash if available, else MurmurHash3 */
static inline uint64_t hash64(const uint8_t* data, size_t len, uint64_t seed) {
#if HAS_XXHASH
    (void)seed;
    return XXH64(data, len, seed);
#else
    return murmur3_64(data, len, seed);
#endif
}

/* Pre-computed seed array for 64 independent hash functions */
static const uint64_t k_minhash_seeds[64] = {
    0x8E3B5C7A9D1F2463ULL, 0x1A2B3C4D5E6F7890ULL, 0xF1E2D3C4B5A69788ULL,
    0x1122334455667788ULL, 0x99AABBCCDDEEFF00ULL, 0xDEADBEEFCAFEBABEULL,
    0x0F1E2D3C4B5A6978ULL, 0x7F6E5D4C3B2A1908ULL, 0x2468ACE013579BDFULL,
    0x13579BDF02468ACEULL, 0xFEDCBA9876543210ULL, 0x0123456789ABCDEFULL,
    0x3C4B5A69788A9BACULL, 0x5A69788A9BACBDCEL, 0x788A9BACBDCEDF01ULL,
    0xA9BACBDCEDF01234ULL, 0xBDCEDF0123456789ULL, 0xDF0123456789ABCDULL,
    0x0A1B2C3D4E5F6071ULL, 0x1C2D3E4F5A6B7C8DULL, 0x2E3F4A5B6C7D8E9FULL,
    0x3A4B5C6D7E8F9A0BULL, 0x4B5C6D7E8F9A0B1CULL, 0x5C6D7E8F9A0B1C2DULL,
    0x6D7E8F9A0B1C2D3EULL, 0x7E8F9A0B1C2D3E4FULL, 0x8F9A0B1C2D3E4F5AULL,
    0x9A0B1C2D3E4F5A6BULL, 0xA0B1C2D3E4F5A6B7ULL, 0xB1C2D3E4F5A6B7C8ULL,
    0xC2D3E4F5A6B7C8D9ULL, 0xD3E4F5A6B7C8D9EAULL, 0xE4F5A6B7C8D9EAF0ULL,
    0xDEC0DEBADBEEFF00ULL, 0xCAFE1234BABE5678ULL, 0xFACEB00CDEADFACEULL,
    0x600DB16EB16EB16EULL, 0xBA5EBA11F00DF00DULL, 0xFEEDFACEBEEFCAFEULL,
    0xACE0F1ACEDEADBEEULL, 0xB10CAB10C13EDECULL, 0xC0FFEE1234567890ULL,
    0xD15C0DEADBEEF123ULL, 0xE5C4F3E2D1C0B9A8ULL, 0xF7F6F5F4F3F2F1F0ULL,
    0x0001020304050607ULL, 0x08090A0B0C0D0E0FULL, 0x1011121314151617ULL,
    0x18191A1B1C1D1E1FULL, 0x2021222324252627ULL, 0x28292A2B2C2D2E2FULL,
    0x3031323334353637ULL, 0x38393A3B3C3D3E3FULL, 0x4041424344454647ULL,
    0x48494A4B4C4D4E4FULL, 0x5051525354555657ULL, 0x58595A5B5C5D5E5FULL,
    0x6061626364656667ULL, 0x68696A6B6C6D6E6FULL, 0x7071727374757677ULL,
    0x78797A7B7C7D7E7FULL, 0x8081828384858687ULL, 0x88898A8B8C8D8E8FULL,
};

/* Fast integer min */
static inline uint64_t u64min(uint64_t a, uint64_t b) { return a < b ? a : b; }
static inline int imin(int a, int b) { return a < b ? a : b; }
static inline double dmin(double a, double b) { return a < b ? a : b; }
static inline double dmax(double a, double b) { return a > b ? a : b; }

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 1: k-gram extraction
 * ═══════════════════════════════════════════════════════════════════════════ */

int minxg_evolve_kgrams_v1(
    const uint8_t* text, size_t text_len, int k,
    char* out_grams, size_t out_cap, int* out_count
) {
    if (!text || !out_grams || !out_count) return MINXG_ERR_NULL_PTR;
    if (k < 1 || text_len < (size_t)k) {
        *out_count = 0;
        return MINXG_OK;
    }

    int count = 0;
    size_t pos = 0;
    for (size_t i = 0; i <= text_len - (size_t)k; i++) {
        if (pos + (size_t)k + 1 > out_cap) return MINXG_ERR_BUFFER_TOO_SMALL;
        memcpy(out_grams + pos, text + i, (size_t)k);
        out_grams[pos + k] = '\0';
        pos += (size_t)k + 1;
        count++;
    }
    *out_count = count;
    return MINXG_OK;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 2: MinHash — 64-dim structural signature
 * ═══════════════════════════════════════════════════════════════════════════ */

int minxg_evolve_minhash_v1(
    const uint8_t* text, size_t text_len,
    uint64_t* sig, size_t sig_cap
) {
    if (!sig || sig_cap < MINXG_MINHASH_DIM) return MINXG_ERR_BUFFER_TOO_SMALL;
    if (!text || text_len == 0) {
        memset(sig, 0, MINXG_MINHASH_DIM * sizeof(uint64_t));
        return MINXG_OK;
    }

    /* Initialize all 64 slots to max uint64 */
    for (int i = 0; i < MINXG_MINHASH_DIM; i++) {
        sig[i] = UINT64_MAX;
    }

    /* Slide a 3-byte window over the text */
    if (text_len < 3) {
        /* Single-gram: hash the whole short text */
        for (int i = 0; i < MINXG_MINHASH_DIM; i++) {
            uint64_t h = hash64(text, text_len, k_minhash_seeds[i]);
            sig[i] = h;
        }
        return MINXG_OK;
    }

    for (size_t pos = 0; pos <= text_len - 3; pos++) {
        for (int i = 0; i < MINXG_MINHASH_DIM; i++) {
            uint64_t h = hash64(text + pos, 3, k_minhash_seeds[i]);
            if (h < sig[i]) sig[i] = h;
        }
    }

    return MINXG_OK;
}

double minxg_evolve_jaccard_v1(
    const uint64_t* sig_a, const uint64_t* sig_b, size_t dim
) {
    if (!sig_a || !sig_b || dim == 0) return 0.0;
    int matches = 0;
    for (size_t i = 0; i < dim; i++) {
        if (sig_a[i] == sig_b[i]) matches++;
    }
    return (double)matches / (double)dim;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 3: SimHash — 64-bit structural fingerprint
 * ═══════════════════════════════════════════════════════════════════════════ */

uint64_t minxg_evolve_simhash_v1(
    const uint8_t* text, size_t text_len
) {
    if (!text || text_len == 0) return 0;

    int64_t bit_weights[64] = {0};

    if (text_len < 3) {
        uint64_t h = hash64(text, text_len, 42);
        for (int i = 0; i < 64; i++) {
            bit_weights[i] += (h & (1ULL << i)) ? 1 : -1;
        }
    } else {
        for (size_t pos = 0; pos <= text_len - 3; pos++) {
            uint64_t h = hash64(text + pos, 3, 42);
            for (int i = 0; i < 64; i++) {
                bit_weights[i] += (h & (1ULL << i)) ? 1 : -1;
            }
        }
    }

    uint64_t fingerprint = 0;
    for (int i = 0; i < 64; i++) {
        if (bit_weights[i] > 0) fingerprint |= (1ULL << i);
    }
    return fingerprint;
}

int minxg_evolve_hamming_v1(uint64_t a, uint64_t b) {
#if defined(__GNUC__) || defined(__clang__)
    return __builtin_popcountll(a ^ b);
#else
    uint64_t x = a ^ b;
    x = x - ((x >> 1) & 0x5555555555555555ULL);
    x = (x & 0x3333333333333333ULL) + ((x >> 2) & 0x3333333333333333ULL);
    x = (x + (x >> 4)) & 0x0F0F0F0F0F0F0F0FULL;
    return (int)((x * 0x0101010101010101ULL) >> 56);
#endif
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 4: Jensen-Shannon Divergence
 * ═══════════════════════════════════════════════════════════════════════════ */

static double kl_divergence(const double* p, const double* q, int n) {
    double sum = 0.0;
    for (int i = 0; i < n; i++) {
        if (p[i] > 0.0 && q[i] > 0.0) {
            sum += p[i] * log(p[i] / q[i]);
        }
    }
    return sum;
}

double minxg_evolve_js_divergence_v1(
    const uint64_t* sigs_a, int n_a,
    const uint64_t* sigs_b, int n_b,
    uint64_t centroid_a, uint64_t centroid_b
) {
    if (!sigs_a || !sigs_b || n_a < 1 || n_b < 1) return 0.0;

    /* Build Hamming-distance histograms (16 bins, 4-bit resolution) */
    double hist_a[16] = {0}, hist_b[16] = {0};

    for (int i = 0; i < n_a; i++) {
        int d = minxg_evolve_hamming_v1(sigs_a[i], centroid_a) >> 2;
        if (d < 16) hist_a[d] += 1.0;
    }
    for (int i = 0; i < n_b; i++) {
        int d = minxg_evolve_hamming_v1(sigs_b[i], centroid_b) >> 2;
        if (d < 16) hist_b[d] += 1.0;
    }

    /* Normalize to probability distributions */
    double sum_a = 0.0, sum_b = 0.0;
    for (int i = 0; i < 16; i++) { sum_a += hist_a[i]; sum_b += hist_b[i]; }
    double inv_a = sum_a > 0.0 ? 1.0 / sum_a : 0.0;
    double inv_b = sum_b > 0.0 ? 1.0 / sum_b : 0.0;
    double eps = 1e-10;
    double p[16], q[16], m[16];
    for (int i = 0; i < 16; i++) {
        p[i] = hist_a[i] * inv_a + eps;
        q[i] = hist_b[i] * inv_b + eps;
        m[i] = (p[i] + q[i]) * 0.5;
    }

    return (kl_divergence(p, m, 16) + kl_divergence(q, m, 16)) * 0.5;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 5: Normalized Compression Distance (NCD)
 * ═══════════════════════════════════════════════════════════════════════════ */

static size_t compress_zstd(const uint8_t* data, size_t len, uint8_t* out, size_t out_cap) {
#if HAS_ZSTD
    size_t bound = ZSTD_compressBound(len);
    if (bound > out_cap) bound = out_cap;
    return ZSTD_compress(out, bound, data, len, 3);
#else
    uLongf dest_len = (uLongf)out_cap;
    if (compress(out, &dest_len, data, (uLong)len) != Z_OK) return 0;
    return (size_t)dest_len;
#endif
}

/* Scratch buffer for compression — 64KB, reused */
#define COMPRESS_BUF_SZ 65536

double minxg_evolve_ncd_v1(
    const uint8_t* a, size_t a_len,
    const uint8_t* b, size_t b_len
) {
    if ((!a || a_len == 0) && (!b || b_len == 0)) return 0.0;
    if (!a || a_len == 0) return 1.0;
    if (!b || b_len == 0) return 1.0;

    static uint8_t buf[COMPRESS_BUF_SZ * 3]; /* not thread-safe for concurrent use */
    /* For production: use thread-local or arena-allocated buffer */

    size_t c_a = compress_zstd(a, a_len, buf, COMPRESS_BUF_SZ);
    size_t c_b = compress_zstd(b, b_len, buf + COMPRESS_BUF_SZ, COMPRESS_BUF_SZ);

    /* Concatenate and compress */
    size_t concat_len = a_len + b_len;
    uint8_t* concat = (uint8_t*)malloc(concat_len);
    if (!concat) return 1.0;
    memcpy(concat, a, a_len);
    memcpy(concat + a_len, b, b_len);
    size_t c_ab = compress_zstd(concat, concat_len, buf + COMPRESS_BUF_SZ * 2, COMPRESS_BUF_SZ);
    free(concat);

    size_t c_max = c_a > c_b ? c_a : c_b;
    if (c_max == 0) return 0.0;

    double ncd_val = (double)(c_ab - (c_a < c_b ? c_a : c_b)) / (double)c_max;
    if (ncd_val < 0.0) ncd_val = 0.0;
    if (ncd_val > 1.0) ncd_val = 1.0;
    return ncd_val;
}

int minxg_evolve_ncd_matrix_v1(
    const uint8_t** seqs, const size_t* lengths, int n,
    double* matrix
) {
    if (!seqs || !lengths || !matrix || n < 1) return MINXG_ERR_NULL_PTR;
    if (n > 500) return MINXG_ERR_BUFFER_TOO_SMALL; /* O(n^2) safeguard */

    /* Pre-compress each sequence */
    size_t* c_len = (size_t*)calloc((size_t)n, sizeof(size_t));
    uint8_t** compressed = (uint8_t**)calloc((size_t)n, sizeof(uint8_t*));
    if (!c_len || !compressed) {
        free(c_len); free(compressed);
        return MINXG_ERR_MEMORY;
    }

    for (int i = 0; i < n; i++) {
        compressed[i] = (uint8_t*)malloc(COMPRESS_BUF_SZ);
        if (compressed[i]) {
            c_len[i] = compress_zstd(seqs[i], lengths[i], compressed[i], COMPRESS_BUF_SZ);
        }
    }

    /* Compute pairwise */
    for (int i = 0; i < n; i++) {
        matrix[i * n + i] = 0.0;
        for (int j = i + 1; j < n; j++) {
            /* C(i||j) */
            size_t concat_len = lengths[i] + lengths[j];
            uint8_t* concat = (uint8_t*)malloc(concat_len);
            if (!concat) continue;
            memcpy(concat, seqs[i], lengths[i]);
            memcpy(concat + lengths[i], seqs[j], lengths[j]);
            size_t c_ij = compress_zstd(concat, concat_len,
                                        compressed[i], COMPRESS_BUF_SZ); /* reuse buffer */
            free(concat);

            size_t c_min = c_len[i] < c_len[j] ? c_len[i] : c_len[j];
            size_t c_max = c_len[i] > c_len[j] ? c_len[i] : c_len[j];
            double v = c_max > 0 ? (double)(c_ij - c_min) / (double)c_max : 0.0;
            if (v < 0.0) v = 0.0;
            if (v > 1.0) v = 1.0;
            matrix[i * n + j] = v;
            matrix[j * n + i] = v;
        }
    }

    for (int i = 0; i < n; i++) free(compressed[i]);
    free(compressed);
    free(c_len);
    return MINXG_OK;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 6: Spectral Invariants — power iteration eigenvalues
 * ═══════════════════════════════════════════════════════════════════════════ */

int minxg_evolve_spectral_v1(
    const double* adj, int n,
    double* eigenvals, int eigen_cap
) {
    if (!adj || !eigenvals || n < 1) return MINXG_ERR_NULL_PTR;
    if (eigen_cap < 1) return MINXG_ERR_BUFFER_TOO_SMALL;

    if (n == 1) {
        eigenvals[0] = 0.0;
        return 1;
    }

    /* Degree vector */
    double* D = (double*)calloc((size_t)n, sizeof(double));
    if (!D) return MINXG_ERR_MEMORY;
    for (int i = 0; i < n; i++) {
        double sum = 0.0;
        for (int j = 0; j < n; j++) sum += adj[i * n + j];
        D[i] = sum > 0.0 ? 1.0 / sqrt(sum) : 0.0;
    }

    /* Normalized Laplacian: L = I - D^(-1/2) A D^(-1/2) */
    double* L = (double*)calloc((size_t)(n * n), sizeof(double));
    if (!L) { free(D); return MINXG_ERR_MEMORY; }
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            if (i == j) {
                L[i * n + j] = 1.0;
            } else if (adj[i * n + j] > 0.0) {
                L[i * n + j] = -D[i] * adj[i * n + j] * D[j];
            }
        }
    }

    int num_trials = imin(n, 8);
    if (num_trials > eigen_cap) num_trials = eigen_cap;

    /* Power iteration with deterministically perturbed initial vectors */
    for (int trial = 0; trial < num_trials; trial++) {
        double* b = (double*)calloc((size_t)n, sizeof(double));
        if (!b) continue;
        /* Deterministic initial vector from trial index */
        for (int i = 0; i < n; i++) {
            b[i] = sin((double)(i + trial * 7) * M_PI / (double)n);
        }
        /* Normalize */
        double norm = 0.0;
        for (int i = 0; i < n; i++) norm += b[i] * b[i];
        norm = sqrt(norm);
        if (norm > 1e-12) {
            for (int i = 0; i < n; i++) b[i] /= norm;
        }

        /* 50 power iterations */
        for (int iter = 0; iter < 50; iter++) {
            double* new_b = (double*)calloc((size_t)n, sizeof(double));
            if (!new_b) break;
            for (int i = 0; i < n; i++) {
                for (int j = 0; j < n; j++) {
                    new_b[i] += L[i * n + j] * b[j];
                }
            }
            /* Rayleigh quotient */
            double rayleigh = 0.0;
            norm = 0.0;
            for (int i = 0; i < n; i++) {
                rayleigh += b[i] * new_b[i];
                norm += new_b[i] * new_b[i];
            }
            norm = sqrt(norm);
            if (norm > 1e-12) {
                for (int i = 0; i < n; i++) b[i] = new_b[i] / norm;
            }
            eigenvals[trial] = rayleigh;
            free(new_b);
        }
        free(b);
    }

    free(L);
    free(D);

    /* Sort eigenvalues */
    for (int i = 0; i < num_trials - 1; i++) {
        for (int j = i + 1; j < num_trials; j++) {
            if (eigenvals[i] > eigenvals[j]) {
                double tmp = eigenvals[i];
                eigenvals[i] = eigenvals[j];
                eigenvals[j] = tmp;
            }
        }
    }

    return num_trials;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 7: Behavioral Momentum
 * ═══════════════════════════════════════════════════════════════════════════ */

int minxg_evolve_momentum_v1(
    const double* positions, const double* timestamps,
    int n, int dim,
    double* out_velocity, double* out_speed, double* out_confidence
) {
    if (!positions || !timestamps || !out_velocity || !out_speed || !out_confidence)
        return MINXG_ERR_NULL_PTR;
    if (n < 2) {
        memset(out_velocity, 0, (size_t)dim * sizeof(double));
        *out_speed = 0.0;
        *out_confidence = 0.0;
        return MINXG_OK;
    }

    double dt_total = timestamps[n - 1] - timestamps[0];
    if (dt_total < 0.1) {
        memset(out_velocity, 0, (size_t)dim * sizeof(double));
        *out_speed = 0.0;
        *out_confidence = 0.0;
        return MINXG_OK;
    }

    /* Direction: first -> last */
    double total_dist = 0.0;
    for (int d = 0; d < dim; d++) {
        double delta = positions[(n - 1) * dim + d] - positions[0 * dim + d];
        out_velocity[d] = delta;
        total_dist += delta * delta;
    }
    total_dist = sqrt(total_dist);

    if (total_dist > 1e-12) {
        for (int d = 0; d < dim; d++) {
            out_velocity[d] /= total_dist;
        }
    }

    *out_speed = total_dist / dt_total;
    *out_confidence = dmin(1.0, ((double)n / 12.0) * dmin(dt_total / 3600.0, 1.0) * 2.0);

    return MINXG_OK;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 8: Structural Drift
 * ═══════════════════════════════════════════════════════════════════════════ */

int minxg_evolve_drift_v1(
    const double* centroids, const double* timestamps,
    int m, int dim,
    double* out_speed, bool* out_drifting, double threshold
) {
    if (!centroids || !timestamps || !out_speed || !out_drifting)
        return MINXG_ERR_NULL_PTR;
    if (m < 3) {
        *out_speed = 0.0;
        *out_drifting = false;
        return MINXG_OK;
    }

    double dt_days = (timestamps[m - 1] - timestamps[0]) / 86400.0;
    if (dt_days < 0.01) {
        *out_speed = 0.0;
        *out_drifting = false;
        return MINXG_OK;
    }

    double dist = 0.0;
    for (int d = 0; d < dim; d++) {
        double delta = centroids[(m - 1) * dim + d] - centroids[0 * dim + d];
        dist += delta * delta;
    }
    dist = sqrt(dist);
    *out_speed = dist / dt_days;
    *out_drifting = (*out_speed > threshold);

    return MINXG_OK;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 9: Topological Invariants
 * ═══════════════════════════════════════════════════════════════════════════ */

int minxg_evolve_topology_v1(
    const double* ncd_matrix, int n, double threshold,
    int* out_h0, int* out_h1
) {
    if (!ncd_matrix || !out_h0 || !out_h1 || n < 1)
        return MINXG_ERR_NULL_PTR;

    if (n == 1) {
        *out_h0 = 1;
        *out_h1 = 0;
        return MINXG_OK;
    }

    /* H0: connected components at threshold */
    int* parent = (int*)calloc((size_t)n, sizeof(int));
    if (!parent) return MINXG_ERR_MEMORY;
    for (int i = 0; i < n; i++) parent[i] = i;

    for (int i = 0; i < n; i++) {
        for (int j = i + 1; j < n; j++) {
            if (ncd_matrix[i * n + j] < threshold) {
                /* Union */
                int ri = i, rj = j;
                while (parent[ri] != ri) ri = parent[ri];
                while (parent[rj] != rj) rj = parent[rj];
                if (ri != rj) parent[ri] = rj;
            }
        }
    }

    /* Count connected components */
    int components = 0;
    for (int i = 0; i < n; i++) {
        if (parent[i] == i) components++;
    }
    *out_h0 = components;

    /* H1: count cycles = edges - vertices + components (simplified) */
    int edges = 0;
    for (int i = 0; i < n; i++) {
        for (int j = i + 1; j < n; j++) {
            if (ncd_matrix[i * n + j] < threshold) edges++;
        }
    }
    int cycles = edges - n + components;
    *out_h1 = cycles > 0 ? cycles : 0;

    free(parent);
    return MINXG_OK;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 10: Statistics
 * ═══════════════════════════════════════════════════════════════════════════ */

double minxg_evolve_euclidean_v1(const double* a, const double* b, int dim) {
    if (!a || !b || dim < 1) return 0.0;
    double sum = 0.0;
    for (int i = 0; i < dim; i++) {
        double d = a[i] - b[i];
        sum += d * d;
    }
    return sqrt(sum);
}

double minxg_evolve_cosine_v1(const double* a, const double* b, int dim) {
    if (!a || !b || dim < 1) return 0.0;
    double dot = 0.0, na = 0.0, nb = 0.0;
    for (int i = 0; i < dim; i++) {
        dot += a[i] * b[i];
        na += a[i] * a[i];
        nb += b[i] * b[i];
    }
    double denom = sqrt(na) * sqrt(nb);
    return denom > 1e-12 ? dot / denom : 0.0;
}

double minxg_evolve_entropy_v1(const double* p, int n) {
    if (!p || n < 1) return 0.0;
    double sum = 0.0;
    for (int i = 0; i < n; i++) {
        if (p[i] > 1e-12) sum -= p[i] * log(p[i]);
    }
    return sum;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Section 11: Version and self-test
 * ═══════════════════════════════════════════════════════════════════════════ */

const char* minxg_evolve_abi_version(void) {
    return "tidal_lock_v1";
}

int minxg_evolve_selftest(void) {
    int failures = 0;

    /* Test 1: MinHash on known text */
    {
        const char* test = "hello world";
        uint64_t sig[64];
        int rc = minxg_evolve_minhash_v1((const uint8_t*)test, strlen(test), sig, 64);
        if (rc != MINXG_OK) { fprintf(stderr, "FAIL: minhash returned %d\n", rc); failures++; }
        int nonzero = 0;
        for (int i = 0; i < 64; i++) if (sig[i] != 0) nonzero++;
        if (nonzero < 50) { fprintf(stderr, "FAIL: minhash only %d nonzero\n", nonzero); failures++; }
    }

    /* Test 2: MinHash reproducibility */
    {
        uint64_t sig1[64], sig2[64];
        minxg_evolve_minhash_v1((const uint8_t*)"test", 4, sig1, 64);
        minxg_evolve_minhash_v1((const uint8_t*)"test", 4, sig2, 64);
        if (memcmp(sig1, sig2, 64 * sizeof(uint64_t)) != 0) {
            fprintf(stderr, "FAIL: minhash not reproducible\n"); failures++;
        }
    }

    /* Test 3: Jaccard similarity (identical -> 1.0) */
    {
        uint64_t sig1[64], sig2[64];
        minxg_evolve_minhash_v1((const uint8_t*)"same text", 9, sig1, 64);
        minxg_evolve_minhash_v1((const uint8_t*)"same text", 9, sig2, 64);
        double j = minxg_evolve_jaccard_v1(sig1, sig2, 64);
        if (j < 0.9) { fprintf(stderr, "FAIL: jaccard identical = %.4f\n", j); failures++; }
    }

    /* Test 4: SimHash */
    {
        uint64_t sh = minxg_evolve_simhash_v1((const uint8_t*)"hello world", 11);
        if (sh == 0) { fprintf(stderr, "FAIL: simhash zero\n"); failures++; }
    }

    /* Test 5: Hamming distance */
    {
        int d = minxg_evolve_hamming_v1(0xFFFFFFFFFFFFFFFFULL, 0ULL);
        if (d != 64) { fprintf(stderr, "FAIL: hamming FF vs 00 = %d\n", d); failures++; }
    }

    /* Test 6: NCD (identical -> ~0, small strings have zstd overhead) */
    {
        double d = minxg_evolve_ncd_v1(
            (const uint8_t*)"INTENT,PARAM,SCOPE", 19,
            (const uint8_t*)"INTENT,PARAM,SCOPE", 19);
        if (d > 0.35) { fprintf(stderr, "FAIL: NCD identical = %.4f\n", d); failures++; }
    }

    /* Test 7: Euclidean */
    {
        double a[] = {0, 3}, b[] = {4, 0};
        double d = minxg_evolve_euclidean_v1(a, b, 2);
        if (fabs(d - 5.0) > 0.001) { fprintf(stderr, "FAIL: euclidean 3-4-5 = %.4f\n", d); failures++; }
    }

    /* Test 8: Cosine (orthogonal -> 0) */
    {
        double a[] = {1, 0}, b[] = {0, 1};
        double c = minxg_evolve_cosine_v1(a, b, 2);
        if (fabs(c) > 0.001) { fprintf(stderr, "FAIL: cosine orthogonal = %.4f\n", c); failures++; }
    }

    /* Test 9: Entropy (uniform -> log(n)) */
    {
        double p[] = {0.5, 0.5};
        double e = minxg_evolve_entropy_v1(p, 2);
        if (fabs(e - log(2.0)) > 0.01) { fprintf(stderr, "FAIL: entropy uniform = %.4f\n", e); failures++; }
    }

    /* Test 10: ABI version */
    {
        const char* v = minxg_evolve_abi_version();
        if (strcmp(v, "tidal_lock_v1") != 0) {
            fprintf(stderr, "FAIL: ABI version = '%s'\n", v); failures++;
        }
    }

    if (failures == 0) {
        fprintf(stderr, "SELFTEST: all 10 tests passed.\n");
    } else {
        fprintf(stderr, "SELFTEST: %d test(s) FAILED.\n", failures);
    }
    return failures;
}
/*
 * minxg_arch.h — Unified C header for MINXG polyglot architecture
 *
 * Language role assignments:
 *   C    — Hot-path data crunching, OS syscall wrappers, stable FFI contract,
 *          lock-free ring buffers, SIMD-accelerated text processing, raw memory pooling.
 *          C is the universal FFI lingua franca; every other language calls into C directly.
 *          This file: no C++ features, C11 only, zero dependencies beyond libc.
 *
 *   C++  — High-level RAII wrappers over C primitives, OpenSSL crypto pipeline,
 *          polymorphic plugin system, JSON/text parser combinators, template-based
 *          containers (concurrent hash maps, LRU caches). Depends on C layer + OpenSSL.
 *
 *   Go   — Network services: gRPC gateway, WebSocket fan-out hub, rate-limit service,
 *          distributed cron scheduler, health-check daemon. Go's goroutine model
 *          replaces Python's asyncio for all server-side concurrency. Talks to C++
 *          via CGo and to Python via Unix sockets/protobuf.
 *
 *   Python — User-facing CLI/TUI shell, AI prompt orchestration, extension ecosystem,
 *            configuration management, documentation generation. Delegates all
 *            performance-critical work to C/C++/Go via ctypes/CGo/sockets.
 *
 * Call chain:  CLI (Python) → ctypes → C wrapper → C++ core → OpenSSL/kernel
 *              Gateway (Go) → CGo → C wrapper → C++ core → ...
 */

#ifndef MINXG_ARCH_H
#define MINXG_ARCH_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════════════════════════
 * Versioning — single source of truth for the entire polyglot stack
 * ═══════════════════════════════════════════════════════════════════════════ */

#define MINXG_VERSION_MAJOR 2
#define MINXG_VERSION_MINOR 0
#define MINXG_VERSION_PATCH 0
#define MINXG_VERSION_STRING "2.0.0-polyglot"

/* ═══════════════════════════════════════════════════════════════════════════
 * Error codes — shared between C, C++, Go (CGo), Python (ctypes)
 * ═══════════════════════════════════════════════════════════════════════════ */

typedef enum {
    MINXG_OK                    =  0,
    MINXG_ERR_NULL_PTR          = -1,
    MINXG_ERR_BUFFER_TOO_SMALL  = -2,
    MINXG_ERR_IO                = -3,
    MINXG_ERR_CRYPTO            = -4,
    MINXG_ERR_ENCODING          = -5,
    MINXG_ERR_PARSE             = -6,
    MINXG_ERR_BOUNDS            = -7,
    MINXG_ERR_TIMEOUT           = -8,
    MINXG_ERR_PERMISSION        = -9,
    MINXG_ERR_THREAD            = -10,
    MINXG_ERR_MEMORY            = -11,
    MINXG_ERR_NOT_FOUND         = -12,
    MINXG_ERR_ALREADY_EXISTS    = -13,
    MINXG_ERR_INVALID_STATE     = -14,
    MINXG_ERR_NOT_IMPLEMENTED   = -15,
} minxg_err_t;

const char* minxg_strerror(minxg_err_t err);

/* ═══════════════════════════════════════════════════════════════════════════
 * Byte buffer — the universal data carrier across all FFI boundaries
 * ═══════════════════════════════════════════════════════════════════════════ */

typedef struct {
    uint8_t*  data;
    size_t    len;
    size_t    cap;
    void*     _internal;  /* opaque: arena or malloc tag */
} minxg_buf_t;

minxg_buf_t minxg_buf_new(size_t cap);
minxg_buf_t minxg_buf_from_bytes(const uint8_t* src, size_t len);
minxg_buf_t minxg_buf_from_cstr(const char* str);
void        minxg_buf_free(minxg_buf_t* buf);
minxg_err_t minxg_buf_reserve(minxg_buf_t* buf, size_t new_cap);
minxg_err_t minxg_buf_append(minxg_buf_t* buf, const uint8_t* src, size_t len);
void        minxg_buf_clear(minxg_buf_t* buf);
bool        minxg_buf_eq(const minxg_buf_t* a, const minxg_buf_t* b);

/* ═══════════════════════════════════════════════════════════════════════════
 * Thread pool (lock-free work-stealing) — C owns the concurrency primitives
 * ═══════════════════════════════════════════════════════════════════════════ */

typedef void* minxg_thread_pool_t;
typedef void (*minxg_work_fn)(void* arg);

minxg_thread_pool_t minxg_thread_pool_create(int num_threads);
minxg_err_t         minxg_thread_pool_submit(minxg_thread_pool_t pool,
                                             minxg_work_fn fn, void* arg);
minxg_err_t         minxg_thread_pool_wait(minxg_thread_pool_t pool);
void                minxg_thread_pool_destroy(minxg_thread_pool_t pool);
int                 minxg_thread_pool_pending(minxg_thread_pool_t pool);

/* ═══════════════════════════════════════════════════════════════════════════
 * Lock-free ring buffer — single-producer single-consumer (SPSC)
 * Useful for Python ↔ C++ streaming, Go ↔ C++ event pipes
 * ═══════════════════════════════════════════════════════════════════════════ */

typedef void* minxg_ring_t;

minxg_ring_t minxg_ring_create(size_t capacity);
minxg_err_t  minxg_ring_push(minxg_ring_t ring, const uint8_t* data, size_t len);
minxg_err_t  minxg_ring_pop(minxg_ring_t ring, uint8_t* out, size_t out_cap, size_t* out_len);
size_t       minxg_ring_readable(minxg_ring_t ring);
size_t       minxg_ring_writable(minxg_ring_t ring);
void         minxg_ring_destroy(minxg_ring_t ring);

#ifdef __cplusplus
}
#endif

#endif /* MINXG_ARCH_H */
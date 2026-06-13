/*
 * minxg_arch.c — Core C implementations: thread pool, ring buffer, buffer ops
 *
 * C11, no external dependencies beyond pthreads + libc.
 * These are the building blocks that C++, Go (via CGo), and Python (via ctypes)
 * all share. Keep these functions allocation-small and lock-contention-free.
 */

#include "minxg_arch.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <pthread.h>
#include <stdatomic.h>
#include <errno.h>

/* ═══════════════════════════════════════════════════════════════════════════
 * Error strings
 * ═══════════════════════════════════════════════════════════════════════════ */

const char* minxg_strerror(minxg_err_t err) {
    switch (err) {
        case MINXG_OK:                    return "OK";
        case MINXG_ERR_NULL_PTR:          return "NULL pointer";
        case MINXG_ERR_BUFFER_TOO_SMALL:  return "Buffer too small";
        case MINXG_ERR_IO:                return "I/O error";
        case MINXG_ERR_CRYPTO:            return "Crypto error";
        case MINXG_ERR_ENCODING:          return "Encoding error";
        case MINXG_ERR_PARSE:             return "Parse error";
        case MINXG_ERR_BOUNDS:            return "Out of bounds";
        case MINXG_ERR_TIMEOUT:           return "Timeout";
        case MINXG_ERR_PERMISSION:        return "Permission denied";
        case MINXG_ERR_THREAD:            return "Thread error";
        case MINXG_ERR_MEMORY:            return "Memory error";
        case MINXG_ERR_NOT_FOUND:         return "Not found";
        case MINXG_ERR_ALREADY_EXISTS:    return "Already exists";
        case MINXG_ERR_INVALID_STATE:     return "Invalid state";
        case MINXG_ERR_NOT_IMPLEMENTED:   return "Not implemented";
        default:                          return "Unknown error";
    }
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Byte buffer
 * ═══════════════════════════════════════════════════════════════════════════ */

minxg_buf_t minxg_buf_new(size_t cap) {
    minxg_buf_t buf = {0};
    if (cap == 0) return buf;
    buf.data = (uint8_t*)calloc(1, cap);
    if (!buf.data) return buf;
    buf.cap  = cap;
    buf.len  = 0;
    return buf;
}

minxg_buf_t minxg_buf_from_bytes(const uint8_t* src, size_t len) {
    minxg_buf_t buf = minxg_buf_new(len ? len : 1);
    if (buf.data && len > 0) {
        memcpy(buf.data, src, len);
        buf.len = len;
    }
    return buf;
}

minxg_buf_t minxg_buf_from_cstr(const char* str) {
    size_t len = str ? strlen(str) : 0;
    return minxg_buf_from_bytes((const uint8_t*)str, len);
}

void minxg_buf_free(minxg_buf_t* buf) {
    if (buf && buf->data) {
        free(buf->data);
        memset(buf, 0, sizeof(*buf));
    }
}

minxg_err_t minxg_buf_reserve(minxg_buf_t* buf, size_t new_cap) {
    if (!buf) return MINXG_ERR_NULL_PTR;
    if (new_cap <= buf->cap) return MINXG_OK;
    uint8_t* new_data = (uint8_t*)realloc(buf->data, new_cap);
    if (!new_data) return MINXG_ERR_MEMORY;
    if (new_data != buf->data) {
        buf->data = new_data;
    }
    buf->cap = new_cap;
    return MINXG_OK;
}

minxg_err_t minxg_buf_append(minxg_buf_t* buf, const uint8_t* src, size_t len) {
    if (!buf || !src) return MINXG_ERR_NULL_PTR;
    if (len == 0) return MINXG_OK;
    if (buf->len + len > buf->cap) {
        size_t new_cap = buf->cap ? buf->cap * 2 : 64;
        while (new_cap < buf->len + len) new_cap *= 2;
        minxg_err_t e = minxg_buf_reserve(buf, new_cap);
        if (e != MINXG_OK) return e;
    }
    memcpy(buf->data + buf->len, src, len);
    buf->len += len;
    return MINXG_OK;
}

void minxg_buf_clear(minxg_buf_t* buf) {
    if (buf) buf->len = 0;
}

bool minxg_buf_eq(const minxg_buf_t* a, const minxg_buf_t* b) {
    if (!a || !b) return false;
    if (a->len != b->len) return false;
    if (a->len == 0) return true;
    return memcmp(a->data, b->data, a->len) == 0;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Thread pool — bounded work-stealing with atomic queue
 * ═══════════════════════════════════════════════════════════════════════════ */

#define MINXG_MAX_THREADS    64
#define MINXG_POOL_QUEUE_SZ 1024

typedef struct {
    minxg_work_fn fn;
    void*         arg;
    atomic_bool   used;
} pool_item_t;

typedef struct {
    pool_item_t  queue[MINXG_POOL_QUEUE_SZ];
    atomic_int   head;
    atomic_int   tail;
    atomic_int   pending;
    int          num_threads;
    pthread_t    threads[MINXG_MAX_THREADS];
    atomic_bool  running;
    pthread_mutex_t mutex;
    pthread_cond_t  cond;
    pthread_cond_t  done_cond;
} pool_impl_t;

static void* pool_worker(void* arg) {
    pool_impl_t* p = (pool_impl_t*)arg;

    while (atomic_load(&p->running)) {
        pthread_mutex_lock(&p->mutex);

        while (atomic_load(&p->pending) == 0 && atomic_load(&p->running)) {
            struct timespec ts;
            clock_gettime(CLOCK_REALTIME, &ts);
            ts.tv_sec += 1;
            pthread_cond_timedwait(&p->cond, &p->mutex, &ts);
            if (!atomic_load(&p->running)) {
                pthread_mutex_unlock(&p->mutex);
                return NULL;
            }
        }

        if (!atomic_load(&p->running)) {
            pthread_mutex_unlock(&p->mutex);
            return NULL;
        }

        // dequeue
        int head = atomic_load(&p->head);
        int tail = atomic_load(&p->tail);
        if (head == tail) {
            pthread_mutex_unlock(&p->mutex);
            continue;
        }

        pool_item_t* item = &p->queue[head];
        minxg_work_fn fn = item->fn;
        void* fn_arg   = item->arg;
        item->used = false;
        int new_head = (head + 1) % MINXG_POOL_QUEUE_SZ;
        atomic_store(&p->head, new_head);

        pthread_mutex_unlock(&p->mutex);

        if (fn) fn(fn_arg);

        if (atomic_fetch_sub(&p->pending, 1) == 1) {
            pthread_cond_broadcast(&p->done_cond);
        }
    }
    return NULL;
}

minxg_thread_pool_t minxg_thread_pool_create(int num_threads) {
    if (num_threads <= 0 || num_threads > MINXG_MAX_THREADS) return NULL;

    pool_impl_t* p = (pool_impl_t*)calloc(1, sizeof(pool_impl_t));
    if (!p) return NULL;

    p->num_threads = num_threads;
    atomic_init(&p->head, 0);
    atomic_init(&p->tail, 0);
    atomic_init(&p->pending, 0);
    atomic_init(&p->running, true);
    pthread_mutex_init(&p->mutex, NULL);
    pthread_cond_init(&p->cond, NULL);
    pthread_cond_init(&p->done_cond, NULL);

    for (int i = 0; i < num_threads; i++) {
        if (pthread_create(&p->threads[i], NULL, pool_worker, p) != 0) {
            atomic_store(&p->running, false);
            pthread_cond_broadcast(&p->cond);
            for (int j = 0; j < i; j++) pthread_join(p->threads[j], NULL);
            pthread_mutex_destroy(&p->mutex);
            pthread_cond_destroy(&p->cond);
            pthread_cond_destroy(&p->done_cond);
            free(p);
            return NULL;
        }
    }

    return p;
}

minxg_err_t minxg_thread_pool_submit(minxg_thread_pool_t pool,
                                     minxg_work_fn fn, void* arg) {
    if (!pool || !fn) return MINXG_ERR_NULL_PTR;
    pool_impl_t* p = (pool_impl_t*)pool;

    pthread_mutex_lock(&p->mutex);
    int tail = atomic_load(&p->tail);
    int next = (tail + 1) % MINXG_POOL_QUEUE_SZ;
    if (next == atomic_load(&p->head)) {
        pthread_mutex_unlock(&p->mutex);
        return MINXG_ERR_BUFFER_TOO_SMALL; // queue full
    }

    p->queue[tail].fn   = fn;
    p->queue[tail].arg  = arg;
    p->queue[tail].used = true;
    atomic_store(&p->tail, next);
    atomic_fetch_add(&p->pending, 1);

    pthread_cond_signal(&p->cond);
    pthread_mutex_unlock(&p->mutex);
    return MINXG_OK;
}

minxg_err_t minxg_thread_pool_wait(minxg_thread_pool_t pool) {
    if (!pool) return MINXG_ERR_NULL_PTR;
    pool_impl_t* p = (pool_impl_t*)pool;

    pthread_mutex_lock(&p->mutex);
    while (atomic_load(&p->pending) > 0) {
        pthread_cond_wait(&p->done_cond, &p->mutex);
    }
    pthread_mutex_unlock(&p->mutex);
    return MINXG_OK;
}

void minxg_thread_pool_destroy(minxg_thread_pool_t pool) {
    if (!pool) return;
    pool_impl_t* p = (pool_impl_t*)pool;

    atomic_store(&p->running, false);
    pthread_cond_broadcast(&p->cond);

    for (int i = 0; i < p->num_threads; i++) {
        pthread_join(p->threads[i], NULL);
    }

    pthread_mutex_destroy(&p->mutex);
    pthread_cond_destroy(&p->cond);
    pthread_cond_destroy(&p->done_cond);
    free(p);
}

int minxg_thread_pool_pending(minxg_thread_pool_t pool) {
    if (!pool) return 0;
    return atomic_load(&((pool_impl_t*)pool)->pending);
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Lock-free SPSC ring buffer (Lamport-style)
 * ═══════════════════════════════════════════════════════════════════════════ */

typedef struct {
    uint8_t*   buf;
    size_t     cap;
    size_t     mask;
    atomic_ullong write_seq;
    atomic_ullong read_seq;
    char       _pad1[64];  /* cache-line isolation */
    char       _pad2[64];
} ring_impl_t;

minxg_ring_t minxg_ring_create(size_t capacity) {
    /* round up to power of 2 */
    size_t cap = 64;
    while (cap < capacity) cap *= 2;

    ring_impl_t* r = (ring_impl_t*)calloc(1, sizeof(ring_impl_t));
    if (!r) return NULL;
    r->buf = (uint8_t*)calloc(1, cap);
    if (!r->buf) { free(r); return NULL; }
    r->cap  = cap;
    r->mask = cap - 1;
    atomic_init(&r->write_seq, 0);
    atomic_init(&r->read_seq, 0);
    return r;
}

minxg_err_t minxg_ring_push(minxg_ring_t ring, const uint8_t* data, size_t len) {
    if (!ring || !data || len == 0) return MINXG_ERR_NULL_PTR;
    ring_impl_t* r = (ring_impl_t*)ring;
    if (len + sizeof(uint32_t) > minxg_ring_writable(ring))
        return MINXG_ERR_BUFFER_TOO_SMALL;

    uint64_t pos = atomic_load(&r->write_seq) & r->mask;
    /* header: 4 bytes length */
    uint32_t hdr = (uint32_t)len;
    memcpy(r->buf + pos, &hdr, 4); pos = (pos + 4) & r->mask;
    memcpy(r->buf + pos, data, len);
    atomic_fetch_add(&r->write_seq, 4 + len);
    return MINXG_OK;
}

minxg_err_t minxg_ring_pop(minxg_ring_t ring, uint8_t* out, size_t out_cap, size_t* out_len) {
    if (!ring || !out || !out_len) return MINXG_ERR_NULL_PTR;
    ring_impl_t* r = (ring_impl_t*)ring;
    if (minxg_ring_readable(ring) < 4) return MINXG_ERR_BUFFER_TOO_SMALL;

    uint64_t pos = atomic_load(&r->read_seq) & r->mask;
    uint32_t hdr = 0;
    memcpy(&hdr, r->buf + pos, 4);
    if (hdr > out_cap) return MINXG_ERR_BUFFER_TOO_SMALL;

    pos = (pos + 4) & r->mask;
    memcpy(out, r->buf + pos, hdr);
    *out_len = hdr;
    atomic_fetch_add(&r->read_seq, 4 + hdr);
    return MINXG_OK;
}

size_t minxg_ring_readable(minxg_ring_t ring) {
    if (!ring) return 0;
    ring_impl_t* r = (ring_impl_t*)ring;
    uint64_t w = atomic_load(&r->write_seq);
    uint64_t rd = atomic_load(&r->read_seq);
    return w >= rd ? (size_t)(w - rd) : 0;
}

size_t minxg_ring_writable(minxg_ring_t ring) {
    if (!ring) return 0;
    ring_impl_t* r = (ring_impl_t*)ring;
    return r->cap - minxg_ring_readable(ring) - 1;
}

void minxg_ring_destroy(minxg_ring_t ring) {
    if (ring) {
        ring_impl_t* r = (ring_impl_t*)ring;
        free(r->buf);
        free(r);
    }
}
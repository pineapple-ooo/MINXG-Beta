/*
 * mem_pool.h — C arena allocator + slab allocator for hot-path memory management
 *
 * Arena: bump-pointer allocator for short-lived allocations (one request lifetime).
 *        Allocates once, frees all at once. No fragmentation.
 * Slab:  per-size-class pre-allocated pools, no locks for owner-thread,
 *        ideal for fixed-size objects (tokens, nodes, events).
 */

#ifndef MINXG_MEM_POOL_H
#define MINXG_MEM_POOL_H

#include "minxg_arch.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════════════════════════
 * Arena allocator (linear bump-pointer)
 * ═══════════════════════════════════════════════════════════════════════════ */

typedef void* minxg_arena_t;

/*
 * Create an arena with initial block size (grows in 2x increments).
 * Recommended: minxg_arena_create(65536) for 64KB initial block.
 */
minxg_arena_t minxg_arena_create(size_t block_size);

/*
 * Allocate aligned memory from arena. Freeing individual allocations
 * is a no-op — the arena frees everything at once on destroy.
 */
void* minxg_arena_alloc(minxg_arena_t arena, size_t size);
void* minxg_arena_realloc(minxg_arena_t arena, void* ptr, size_t old_size, size_t new_size);

/*
 * Reset: keeps all blocks but resets bump pointer (reuse memory).
 */
void minxg_arena_reset(minxg_arena_t arena);
void minxg_arena_destroy(minxg_arena_t arena);

/* Stats: total allocated, used, blocks */
size_t minxg_arena_total(minxg_arena_t arena);
size_t minxg_arena_used(minxg_arena_t arena);
int    minxg_arena_block_count(minxg_arena_t arena);

/* ═══════════════════════════════════════════════════════════════════════════
 * Slab allocator — fixed-size object pool per size class
 * ═══════════════════════════════════════════════════════════════════════════ */

typedef void* minxg_slab_t;

/* item_size: what the user allocates. slab_size: total objects per slab. */
minxg_slab_t minxg_slab_create(size_t item_size, size_t slab_size);
void*        minxg_slab_alloc(minxg_slab_t slab);
void         minxg_slab_free(minxg_slab_t slab, void* ptr);
void         minxg_slab_destroy(minxg_slab_t slab);

/* Stats */
size_t minxg_slab_total_allocated(minxg_slab_t slab);
size_t minxg_slab_free_count(minxg_slab_t slab);

/* ═══════════════════════════════════════════════════════════════════════════
 * Fixed-size ring buffer (fast allocation for messages, events, packets)
 * ═══════════════════════════════════════════════════════════════════════════ */

typedef void* minxg_rb_t;

minxg_rb_t minxg_rb_create(size_t item_size, size_t capacity);
minxg_err_t minxg_rb_push(minxg_rb_t rb, const void* item);
minxg_err_t minxg_rb_pop(minxg_rb_t rb, void* out_item);
size_t      minxg_rb_count(minxg_rb_t rb);
void        minxg_rb_destroy(minxg_rb_t rb);

#ifdef __cplusplus
}
#endif

#endif /* MINXG_MEM_POOL_H */
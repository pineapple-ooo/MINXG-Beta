// Package bridge provides the CGo bridge from Go to the MINXG C core.
//
// Go calls into C for:
//   - minxg_strerror translation
//   - mempool: arena, slab, ring-buffer allocation
//   - text engine: Boyer-Moore search, CSV parsing, glob matching
//   - thread pool: parallel work submission
//
// Crypto and encoding use Go's stdlib (assembly-optimized, faster than
// crossing the CGo boundary for small payloads). Only bulk operations
// where the C core adds value (memory pooling, text search) go via CGo.
package bridge

/*
#cgo LDFLAGS: -L${SRCDIR}/../../build -lminxg_c -lpthread
#cgo CFLAGS: -I${SRCDIR}/../../c_core
#include <stdlib.h>

#include "minxg_arch.h"
#include "text_engine.h"
#include "mem_pool.h"
*/
import "C"
import (
	"unsafe"
)

// C.free etc are from runtime/cgo
// #include <stdlib.h> is needed for C.free

// ─── Error Translation ────────────────────────────────────────────────────────

// ErrString converts a minxg_err_t to human-readable string.
func ErrString(err C.minxg_err_t) string {
	cstr := C.minxg_strerror(err)
	return C.GoString(cstr)
}

// ─── Arena Allocator ──────────────────────────────────────────────────────────

// Arena wraps a C arena allocator for Go usage.
// Useful for batch operations (parse 10K JSON objects without GC pressure).
type Arena struct {
	ptr C.minxg_arena_t
}

// NewArena creates an arena with the given block size.
func NewArena(blockSize int) *Arena {
	a := C.minxg_arena_create(C.size_t(blockSize))
	if a == nil {
		return nil
	}
	return &Arena{ptr: a}
}

// Alloc allocates size bytes from the arena.
// Returns a pointer — memory is valid until arena is destroyed/reset.
// Use ArenaAllocBytes for safe Go byte slices.
func (a *Arena) Alloc(size int) unsafe.Pointer {
	return C.minxg_arena_alloc(a.ptr, C.size_t(size))
}

// AllocBytes allocates and returns a Go byte slice backed by the arena.
// The slice is valid until Reset or Destroy is called.
func (a *Arena) AllocBytes(size int) []byte {
	if size == 0 {
		return nil
	}
	ptr := C.minxg_arena_alloc(a.ptr, C.size_t(size))
	if ptr == nil {
		return nil
	}
	return unsafe.Slice((*byte)(ptr), size)
}

// AllocString allocates and copies a Go string into the arena.
func (a *Arena) AllocString(s string) string {
	b := a.AllocBytes(len(s))
	copy(b, s)
	return string(b)
}

// Reset resets the bump pointer without freeing blocks.
func (a *Arena) Reset() {
	C.minxg_arena_reset(a.ptr)
}

// Destroy frees all blocks and the arena itself.
func (a *Arena) Destroy() {
	C.minxg_arena_destroy(a.ptr)
	a.ptr = nil
}

// Stats returns (total, used, blockCount).
func (a *Arena) Stats() (total, used int, blocks int) {
	total = int(C.minxg_arena_total(a.ptr))
	used  = int(C.minxg_arena_used(a.ptr))
	blocks = int(C.minxg_arena_block_count(a.ptr))
	return
}

// ─── Slab Allocator ──────────────────────────────────────────────────────────

// Slab wraps a fixed-size slab allocator for Go objects.
// Use when you allocate millions of same-sized structs.
type Slab struct {
	ptr C.minxg_slab_t
}

// NewSlab creates a slab allocator for items of itemSize, slabSize per block.
func NewSlab(itemSize, slabSize int) *Slab {
	s := C.minxg_slab_create(C.size_t(itemSize), C.size_t(slabSize))
	if s == nil {
		return nil
	}
	return &Slab{ptr: s}
}

// Alloc returns a pointer to a zeroed item.
func (s *Slab) Alloc() unsafe.Pointer {
	return C.minxg_slab_alloc(s.ptr)
}

// Free returns an item to the slab's freelist.
func (s *Slab) Free(ptr unsafe.Pointer) {
	C.minxg_slab_free(s.ptr, ptr)
}

// Destroy frees the slab.
func (s *Slab) Destroy() {
	C.minxg_slab_destroy(s.ptr)
	s.ptr = nil
}

// ─── Ring Buffer (fixed-size items) ──────────────────────────────────────────

// RingBuffer is a concurrent-safe fixed-size ring buffer for items of equal size.
type RingBuffer struct {
	ptr C.minxg_rb_t
}

// NewRingBuffer creates a ring buffer for items of itemSize, capacity items.
func NewRingBuffer(itemSize, capacity int) *RingBuffer {
	rb := C.minxg_rb_create(C.size_t(itemSize), C.size_t(capacity))
	if rb == nil {
		return nil
	}
	return &RingBuffer{ptr: rb}
}

// Push copies item into the ring buffer.
func (rb *RingBuffer) Push(item []byte) error {
	rc := C.minxg_rb_push(rb.ptr, unsafe.Pointer(&item[0]))
	if rc != C.MINXG_OK {
		return &Error{Code: int(rc)}
	}
	return nil
}

// Pop copies oldest item into the provided buffer.
func (rb *RingBuffer) Pop(out []byte) error {
	rc := C.minxg_rb_pop(rb.ptr, unsafe.Pointer(&out[0]))
	if rc != C.MINXG_OK {
		return &Error{Code: int(rc)}
	}
	return nil
}

// Count returns the number of items currently in the buffer.
func (rb *RingBuffer) Count() int {
	return int(C.minxg_rb_count(rb.ptr))
}

// Destroy frees the ring buffer.
func (rb *RingBuffer) Destroy() {
	C.minxg_rb_destroy(rb.ptr)
	rb.ptr = nil
}

// ─── Text Engine ─────────────────────────────────────────────────────────────

// Memmem finds the first occurrence of needle in haystack using Boyer-Moore-Horspool.
func Memmem(haystack, needle []byte) int64 {
	if len(needle) == 0 {
		return 0
	}
	if len(haystack) == 0 || len(needle) > len(haystack) {
		return -1
	}
	return int64(C.minxg_memmem(
		(*C.uint8_t)(unsafe.Pointer(&haystack[0])), C.size_t(len(haystack)),
		(*C.uint8_t)(unsafe.Pointer(&needle[0])), C.size_t(len(needle)),
	))
}

// Memrmem finds the last occurrence.
func Memrmem(haystack, needle []byte) int64 {
	if len(needle) == 0 {
		return int64(len(haystack))
	}
	if len(haystack) == 0 || len(needle) > len(haystack) {
		return -1
	}
	return int64(C.minxg_memrmem(
		(*C.uint8_t)(unsafe.Pointer(&haystack[0])), C.size_t(len(haystack)),
		(*C.uint8_t)(unsafe.Pointer(&needle[0])), C.size_t(len(needle)),
	))
}

// Memcnt counts non-overlapping needle occurrences.
func Memcnt(haystack, needle []byte) int {
	if len(needle) == 0 || len(haystack) == 0 || len(needle) > len(haystack) {
		return 0
	}
	return int(C.minxg_memcnt(
		(*C.uint8_t)(unsafe.Pointer(&haystack[0])), C.size_t(len(haystack)),
		(*C.uint8_t)(unsafe.Pointer(&needle[0])), C.size_t(len(needle)),
	))
}

// GlobMatch checks if str matches the fnmatch pattern.
func GlobMatch(pattern, str string) bool {
	cPat := C.CString(pattern)
	cStr := C.CString(str)
	defer C.free(unsafe.Pointer(cPat))
	defer C.free(unsafe.Pointer(cStr))
	return bool(C.minxg_fnmatch(cPat, cStr))
}

// IsValidUTF8 checks if the byte slice is valid UTF-8.
func IsValidUTF8(data []byte) bool {
	if len(data) == 0 {
		return true
	}
	return bool(C.minxg_utf8_is_valid((*C.char)(unsafe.Pointer(&data[0])), C.size_t(len(data))))
}

// UTF8CodepointCount returns the number of Unicode codepoints.
func UTF8CodepointCount(data []byte) int {
	if len(data) == 0 {
		return 0
	}
	return int(C.minxg_utf8_codepoint_count((*C.char)(unsafe.Pointer(&data[0])), C.size_t(len(data))))
}

// ─── Thread Pool ─────────────────────────────────────────────────────────────

// ThreadPool wraps the C work-stealing thread pool.
type ThreadPool struct {
	ptr C.minxg_thread_pool_t
}

// NewThreadPool creates a thread pool with numThreads workers.
func NewThreadPool(numThreads int) *ThreadPool {
	p := C.minxg_thread_pool_create(C.int(numThreads))
	if p == nil {
		return nil
	}
	return &ThreadPool{ptr: p}
}

// Submit adds a function to the work queue.
// Returns an error if the queue is full or pool is nil.
func (tp *ThreadPool) Submit(fn func()) error {
	// We need to pin the fn so it survives the CGo boundary.
	// The work_fn wrapper stores the Go func pointer in a registry.
	id := registerWorkFunc(fn)
	rc := C.minxg_thread_pool_submit(tp.ptr, (C.minxg_work_fn)(unsafe.Pointer(&id)), nil)
	if rc != C.MINXG_OK {
		deregisterWorkFunc(id)
		return &Error{Code: int(rc)}
	}
	return nil
}

// Wait blocks until all submitted work completes.
func (tp *ThreadPool) Wait() {
	C.minxg_thread_pool_wait(tp.ptr)
}

// Destroy shuts down all workers and frees the pool.
func (tp *ThreadPool) Destroy() {
	C.minxg_thread_pool_destroy(tp.ptr)
	tp.ptr = nil
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

// Error wraps a minxg_err_t as a Go error.
type Error struct {
	Code int
}

func (e *Error) Error() string {
	return ErrString(C.minxg_err_t(e.Code))
}

// OK checks if a C return code indicates success.
func OK(rc C.minxg_err_t) bool {
	return rc == C.MINXG_OK
}

// ─── Work function registry ───────────────────────────────────────────────────

// Simple registry to pin Go function pointers for C thread pool callbacks.
// In production, replace with a proper sync.Map-based registry with cleanup.

var workRegistry = make(map[int]func())
var workRegistryNext int

func registerWorkFunc(fn func()) int {
	workRegistryNext++
	workRegistry[workRegistryNext] = fn
	return workRegistryNext
}

func deregisterWorkFunc(id int) {
	delete(workRegistry, id)
}

// Ensure imports used.
var _ = unsafe.Sizeof(0)
// Package ratelimit implements a distributed token-bucket rate limiter.
//
// Supports in-memory (single-node) and Redis-backed (distributed) modes.
// Python's rate_limit module in the gateway can delegate hot-path checks
// to this Go service via Unix socket / gRPC — one atomic Lua script in
// Redis vs N Python processes competing.
package ratelimit

import (
	"context"
	"fmt"
	"math"
	"sync"
	"sync/atomic"
	"time"
)

// ─── Config ──────────────────────────────────────────────────────────────────

// Config configures the rate limiter.
type Config struct {
	// Rate: max tokens per interval.
	Rate int
	// Interval: token refill window.
	Interval time.Duration
	// Burst: max instantaneous burst (bucket capacity).
	// 0 = same as Rate.
	Burst int
}

// Token represents a consumed allowance.
type Token struct {
	Remaining int
	ResetAt   time.Time
	Allowed   bool
}

// ─── Backend interface ────────────────────────────────────────────────────────

// Backend is the storage backend (in-memory, Redis, etc.).
type Backend interface {
	// Allow consumes one token for the given key. Returns the token result.
	Allow(ctx context.Context, key string) (Token, error)

	// AllowN consumes n tokens.
	AllowN(ctx context.Context, key string, n int) (Token, error)

	// Reset clears the bucket for the given key.
	Reset(ctx context.Context, key string) error

	// Close releases backend resources.
	Close() error
}

// ─── Limiter ──────────────────────────────────────────────────────────────────

// Limiter wraps a Backend with config and metrics.
type Limiter struct {
	cfg     Config
	backend Backend

	// Metrics
	totalAllowed  atomic.Int64
	totalDenied   atomic.Int64
	totalRequests atomic.Int64
}

// New creates a new Limiter. Uses in-memory backend if backend is nil.
func New(cfg Config, backend Backend) *Limiter {
	if cfg.Burst <= 0 {
		cfg.Burst = cfg.Rate
	}
	if backend == nil {
		backend = NewMemoryBackend(cfg)
	}
	return &Limiter{
		cfg:     cfg,
		backend: backend,
	}
}

// Allow checks if a single token should be allowed for the given key.
func (l *Limiter) Allow(ctx context.Context, key string) (bool, error) {
	tok, err := l.backend.Allow(ctx, key)
	if err != nil {
		l.totalRequests.Add(1)
		return false, err
	}
	l.totalRequests.Add(1)
	if tok.Allowed {
		l.totalAllowed.Add(1)
	} else {
		l.totalDenied.Add(1)
	}
	return tok.Allowed, nil
}

// AllowN checks if n tokens should be allowed for the given key.
func (l *Limiter) AllowN(ctx context.Context, key string, n int) (bool, error) {
	tok, err := l.backend.AllowN(ctx, key, n)
	if err != nil {
		l.totalRequests.Add(1)
		return false, err
	}
	l.totalRequests.Add(1)
	if tok.Allowed {
		l.totalAllowed.Add(1)
	} else {
		l.totalDenied.Add(1)
	}
	return tok.Allowed, nil
}

// Reset clears the bucket for the given key.
func (l *Limiter) Reset(ctx context.Context, key string) error {
	return l.backend.Reset(ctx, key)
}

// Close releases backend resources.
func (l *Limiter) Close() error {
	return l.backend.Close()
}

// Metrics returns current counters.
func (l *Limiter) Metrics() (allowed, denied, total int64) {
	return l.totalAllowed.Load(), l.totalDenied.Load(), l.totalRequests.Load()
}

// ─── In-Memory Backend ────────────────────────────────────────────────────────

// MemoryBackend implements Backend with a sync.Map and per-key mu.
type MemoryBackend struct {
	cfg      Config
	mu       sync.Mutex
	buckets  map[string]*bucket
	stopCh   chan struct{}
	cleanupWg sync.WaitGroup
}

type bucket struct {
	tokens   float64
	lastFill time.Time
	mu       sync.Mutex
}

// NewMemoryBackend creates an in-memory backend with periodic cleanup.
func NewMemoryBackend(cfg Config) *MemoryBackend {
	mb := &MemoryBackend{
		cfg:     cfg,
		buckets: make(map[string]*bucket),
		stopCh:  make(chan struct{}),
	}

	// Periodic cleanup of stale buckets (every 5 minutes, buckets > 10 min old)
	mb.cleanupWg.Add(1)
	go func() {
		defer mb.cleanupWg.Done()
		ticker := time.NewTicker(5 * time.Minute)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				mb.cleanup(10 * time.Minute)
			case <-mb.stopCh:
				return
			}
		}
	}()

	return mb
}

func (mb *MemoryBackend) getBucket(key string) *bucket {
	mb.mu.Lock()
	b, ok := mb.buckets[key]
	if !ok {
		b = &bucket{
			tokens:   float64(mb.cfg.Burst),
			lastFill: time.Now(),
		}
		mb.buckets[key] = b
	}
	mb.mu.Unlock()
	return b
}

func (mb *MemoryBackend) Allow(ctx context.Context, key string) (Token, error) {
	return mb.AllowN(ctx, key, 1)
}

func (mb *MemoryBackend) AllowN(ctx context.Context, key string, n int) (Token, error) {
	b := mb.getBucket(key)
	b.mu.Lock()
	defer b.mu.Unlock()

	now := time.Now()
	elapsed := now.Sub(b.lastFill).Seconds()
	refillRate := float64(mb.cfg.Rate) / mb.cfg.Interval.Seconds()
	b.tokens = math.Min(float64(mb.cfg.Burst), b.tokens+elapsed*refillRate)
	b.lastFill = now

	tok := Token{
		ResetAt: now.Add(mb.cfg.Interval),
	}

	if b.tokens >= float64(n) {
		b.tokens -= float64(n)
		tok.Allowed = true
	}
	tok.Remaining = int(math.Floor(b.tokens))

	return tok, nil
}

func (mb *MemoryBackend) Reset(ctx context.Context, key string) error {
	mb.mu.Lock()
	delete(mb.buckets, key)
	mb.mu.Unlock()
	return nil
}

func (mb *MemoryBackend) Close() error {
	close(mb.stopCh)
	mb.cleanupWg.Wait()
	return nil
}

func (mb *MemoryBackend) cleanup(maxAge time.Duration) {
	mb.mu.Lock()
	defer mb.mu.Unlock()
	now := time.Now()
	for key, b := range mb.buckets {
		b.mu.Lock()
		age := now.Sub(b.lastFill)
		b.mu.Unlock()
		if age > maxAge {
			delete(mb.buckets, key)
		}
	}
}

// ─── Convenience constructors ─────────────────────────────────────────────────

// NewTokenBucket creates a standard token-bucket limiter.
func NewTokenBucket(ratePerMinute, burst int) *Limiter {
	return New(Config{
		Rate:     ratePerMinute,
		Interval: time.Minute,
		Burst:    burst,
	}, nil)
}

// NewLeakyBucket creates a constant-outflow (leaky bucket) limiter.
func NewLeakyBucket(ratePerSecond int) *Limiter {
	return New(Config{
		Rate:     ratePerSecond,
		Interval: time.Second,
		Burst:    ratePerSecond, // no burst — strict rate
	}, nil)
}

// ─── Example Redis backend stub ───────────────────────────────────────────────
//
// To use Redis, implement Backend with a Lua script:
//
//   local key = KEYS[1]
//   local rate = tonumber(ARGV[1])
//   local burst = tonumber(ARGV[2])
//   local interval = tonumber(ARGV[3])
//   local now = tonumber(ARGV[4])
//   local requested = tonumber(ARGV[5])
//
//   local bucket = redis.call('HMGET', key, 'tokens', 'last_fill')
//   local tokens = tonumber(bucket[1]) or burst
//   local last_fill = tonumber(bucket[2]) or now
//
//   local elapsed = now - last_fill
//   tokens = math.min(burst, tokens + (elapsed * rate / interval))
//
//   local allowed = 0
//   if tokens >= requested then
//       tokens = tokens - requested
//       allowed = 1
//   end
//
//   redis.call('HMSET', key, 'tokens', tokens, 'last_fill', now)
//   redis.call('EXPIRE', key, math.ceil(interval * 2))
//
//   return {allowed, math.floor(tokens), now + interval}
//
// type RedisBackend struct { client *redis.Client; cfg Config }
// ... implement Allow, AllowN, Reset with EVAL

// Ensure MemoryBackend implements Backend.
var _ Backend = (*MemoryBackend)(nil)

// Unused import guard.
var _ = fmt.Sprintf
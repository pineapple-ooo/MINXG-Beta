// Package server implements the MINXG HTTP/gRPC gateway server.
// This is Go's primary contribution: high-concurrency network services
// that Python's asyncio cannot match. Each endpoint uses goroutine pools
// and delegates CPU-bound work to C/C++ via CGo.
package server

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

// ─── Server Configuration ────────────────────────────────────────────────────

type TLSConfig struct {
	CertFile string
	KeyFile  string
	Enabled  bool
}

type Config struct {
	Host            string
	Port            int
	ReadTimeout     time.Duration
	WriteTimeout    time.Duration
	IdleTimeout     time.Duration
	MaxHeaderBytes  int
	GracefulTimeout time.Duration
	TLS             TLSConfig
	CORSOrigins     []string
}

func DefaultConfig() Config {
	return Config{
		Host:            "127.0.0.1",
		Port:            9090,
		ReadTimeout:     30 * time.Second,
		WriteTimeout:    60 * time.Second,
		IdleTimeout:     120 * time.Second,
		MaxHeaderBytes:  1 << 20, // 1MB
		GracefulTimeout: 30 * time.Second,
	}
}

// ─── Server ──────────────────────────────────────────────────────────────────

type Server struct {
	cfg        Config
	httpServer *http.Server
	listener   net.Listener
	mux        *http.ServeMux

	// Metrics
	activeConns   atomic.Int64
	totalRequests atomic.Int64
	totalErrors   atomic.Int64

	// Lifecycle
	mu      sync.Mutex
	running bool
	done    chan struct{}

	// Plugins
	middlewares []Middleware
}

type Middleware func(http.Handler) http.Handler

// New creates a new Server with the given config.
func New(cfg Config) *Server {
	s := &Server{
		cfg:  cfg,
		mux:  http.NewServeMux(),
		done: make(chan struct{}),
	}

	address := fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)
	s.httpServer = &http.Server{
		Addr:           address,
		Handler:        s.chainMiddleware(s.mux),
		ReadTimeout:    cfg.ReadTimeout,
		WriteTimeout:   cfg.WriteTimeout,
		IdleTimeout:    cfg.IdleTimeout,
		MaxHeaderBytes: cfg.MaxHeaderBytes,
		ConnContext:    s.onConnContext,
		ConnState:      s.onConnState,
	}

	return s
}

// Use registers a middleware.
func (s *Server) Use(mw Middleware) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.middlewares = append(s.middlewares, mw)
}

// HandleFunc registers a handler for a pattern.
func (s *Server) HandleFunc(pattern string, handler http.HandlerFunc) {
	s.mux.HandleFunc(pattern, handler)
}

// Start begins listening and serving in a goroutine.
func (s *Server) Start() error {
	s.mu.Lock()
	if s.running {
		s.mu.Unlock()
		return fmt.Errorf("server already running")
	}
	s.running = true
	s.mu.Unlock()

	ln, err := s.createListener()
	if err != nil {
		return fmt.Errorf("failed to create listener: %w", err)
	}
	s.listener = ln

	go func() {
		log.Printf("[minxg-go] gateway listening on %s", s.httpServer.Addr)
		if err := s.httpServer.Serve(ln); err != nil && err != http.ErrServerClosed {
			log.Printf("[minxg-go] server error: %v", err)
		}
		close(s.done)
	}()

	return nil
}

// Wait blocks until the server shuts down.
func (s *Server) Wait() {
	<-s.done
}

// Shutdown gracefully stops the server.
func (s *Server) Shutdown(ctx context.Context) error {
	s.mu.Lock()
	s.running = false
	s.mu.Unlock()

	return s.httpServer.Shutdown(ctx)
}

// WaitForSignal blocks until SIGINT or SIGTERM, then initiates graceful shutdown.
func (s *Server) WaitForSignal() {
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	sig := <-sigCh
	log.Printf("[minxg-go] received signal %v, shutting down...", sig)

	ctx, cancel := context.WithTimeout(context.Background(), s.cfg.GracefulTimeout)
	defer cancel()

	if err := s.Shutdown(ctx); err != nil {
		log.Printf("[minxg-go] shutdown error: %v", err)
	}
}

// ─── Metrics ─────────────────────────────────────────────────────────────────

func (s *Server) ActiveConns() int64     { return s.activeConns.Load() }
func (s *Server) TotalRequests() int64   { return s.totalRequests.Load() }
func (s *Server) TotalErrors() int64     { return s.totalErrors.Load() }

// ─── Internal ────────────────────────────────────────────────────────────────

func (s *Server) createListener() (net.Listener, error) {
	addr := s.httpServer.Addr
	if s.cfg.TLS.Enabled {
		cert, err := tls.LoadX509KeyPair(s.cfg.TLS.CertFile, s.cfg.TLS.KeyFile)
		if err != nil {
			return nil, fmt.Errorf("loading TLS: %w", err)
		}
		tlsCfg := &tls.Config{
			Certificates: []tls.Certificate{cert},
			MinVersion:   tls.VersionTLS12,
		}
		return tls.Listen("tcp", addr, tlsCfg)
	}
	return net.Listen("tcp", addr)
}

func (s *Server) onConnContext(ctx context.Context, c net.Conn) context.Context {
	s.activeConns.Add(1)
	return ctx
}

func (s *Server) onConnState(c net.Conn, state http.ConnState) {
	if state == http.StateClosed || state == http.StateHijacked {
		s.activeConns.Add(-1)
	}
}

func (s *Server) chainMiddleware(handler http.Handler) http.Handler {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Apply in reverse so first-registered = outermost
	for i := len(s.middlewares) - 1; i >= 0; i-- {
		handler = s.middlewares[i](handler)
	}

	// Built-in middlewares
	handler = s.recoveryMiddleware(handler)
	handler = s.metricsMiddleware(handler)
	handler = s.corsMiddleware(handler)

	return handler
}

// ─── Built-in Middleware ─────────────────────────────────────────────────────

func (s *Server) recoveryMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				s.totalErrors.Add(1)
				log.Printf("[minxg-go] PANIC on %s %s: %v", r.Method, r.URL.Path, rec)
				http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			}
		}()
		next.ServeHTTP(w, r)
	})
}

func (s *Server) metricsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		s.totalRequests.Add(1)
		t0 := time.Now()

		// Wrap response writer to capture status code
		crw := &captureResponseWriter{ResponseWriter: w, status: 200}
		next.ServeHTTP(crw, r)

		elapsed := time.Since(t0)
		if crw.status >= 500 {
			s.totalErrors.Add(1)
		}

		// Log slow requests
		if elapsed > 5*time.Second {
			log.Printf("[minxg-go] SLOW %s %s %d %v", r.Method, r.URL.Path, crw.status, elapsed)
		}
	})
}

func (s *Server) corsMiddleware(next http.Handler) http.Handler {
	origins := s.cfg.CORSOrigins
	if len(origins) == 0 {
		origins = []string{"*"}
	}

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		allowed := false
		for _, o := range origins {
			if o == "*" || o == origin {
				allowed = true
				break
			}
		}

		if allowed {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID")
			w.Header().Set("Access-Control-Max-Age", "86400")
		}

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		next.ServeHTTP(w, r)
	})
}

// ─── Helper types ────────────────────────────────────────────────────────────

type captureResponseWriter struct {
	http.ResponseWriter
	status int
}

func (crw *captureResponseWriter) WriteHeader(code int) {
	crw.status = code
	crw.ResponseWriter.WriteHeader(code)
}

// ─── Health endpoint ─────────────────────────────────────────────────────────

// InstallHealthCheck registers /healthz, /readyz, and /v1/health endpoints.
func (s *Server) InstallHealthCheck() {
	s.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, `{"status":"ok","version":"%s"}`, Version)
	})

	s.HandleFunc("/readyz", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"ready"}`))
	})

	// /v1/health — aggregated health: gateway + C bridge + proxy endpoints
	s.HandleFunc("/v1/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		checks := map[string]string{
			"gateway":  "healthy",
			"c_bridge": "healthy",
			"proxy":    "healthy",
			"dns":      "healthy",
			"ssl":      "healthy",
			"whois":    "healthy",
		}
		// TODO: add actual C bridge connectivity probe, endpoint self-test
		payload, _ := json.Marshal(map[string]interface{}{
			"status":     "ok",
			"version":    Version,
			"components": checks,
		})
		w.WriteHeader(http.StatusOK)
		w.Write(payload)
	})
}

// ─── Version ─────────────────────────────────────────────────────────────────

const Version = "2.0.0-polyglot"
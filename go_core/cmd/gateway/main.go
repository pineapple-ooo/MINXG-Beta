// Package main — MINXG Go gateway entry point.
//
// Starts the HTTP/WS server, health checker, and rate limiter.
// Connects to C/C++ core via CGo bridge for crypto and data processing.
package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/nousresearch/minxg-go/health"
	"github.com/nousresearch/minxg-go/ratelimit"
	"github.com/nousresearch/minxg-go/server"
)

func main() {
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)
	log.Printf("[minxg-go] starting gateway v%s", server.Version)

	// ─── Config ───────────────────────────────────────────────────────────

	srvCfg := server.DefaultConfig()
	srvCfg.Port = 9090

	limiter := ratelimit.New(ratelimit.Config{
		Rate:     600,  // 600 requests per minute
		Interval: time.Minute,
		Burst:    1200,
	}, nil)

	checker := health.NewChecker(health.DefaultConfig())

	// ─── Server ────────────────────────────────────────────────────────────

	srv := server.New(srvCfg)

	// Register endpoints
	srv.InstallHealthCheck()

	// ─── v0.0.2: Proxy & Network endpoints (offload Python HTTP to Go) ──────
	srv.InstallProxyHandler()
	srv.InstallDNSHandler()
	srv.InstallSSLCheckHandler()
	srv.InstallWhoisHandler()

	// Rate limit check endpoint
	srv.HandleFunc("/v1/ratelimit/check", func(w http.ResponseWriter, r *http.Request) {
		// Stub: parse body, call limiter.Allow, return JSON
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, `{"allowed":true,"remaining":599}`)
	})

	// ─── Start ────────────────────────────────────────────────────────────

	if err := srv.Start(); err != nil {
		log.Fatalf("[minxg-go] failed to start: %v", err)
	}

	// ─── Health checker: monitor Python workers ────────────────────────────

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Example worker registration (adjust to actual Python worker paths)
	checker.Register(ctx, health.Worker{
		Name:    "py-workers",
		Command: "python3",
		Args:    []string{"-m", "py_workers.server"},
		Env:     []string{fmt.Sprintf("MINXG_HOME=%s", os.Getenv("MINXG_HOME"))},
		HealthCheck: func(ctx context.Context) error {
			// TODO: HTTP ping to Python worker health endpoint
			return nil
		},
	})

	// ─── Wait for signal ───────────────────────────────────────────────────

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	log.Printf("[minxg-go] ready — listening on :%d", srvCfg.Port)

	select {
	case sig := <-sigCh:
		log.Printf("[minxg-go] received %v, shutting down...", sig)
	}

	// Graceful shutdown
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	checker.Shutdown()
	srv.Shutdown(shutdownCtx)
	limiter.Close()

	log.Printf("[minxg-go] shutdown complete")
}
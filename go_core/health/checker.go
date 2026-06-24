// Package health implements a health-check daemon that monitors Python
// worker processes and restarts them on crash. Uses goroutine-per-worker
// with heartbeat timeouts.
package health

import (
	"context"
	"fmt"
	"log"
	"os/exec"
	"sync"
	"sync/atomic"
	"time"
)

// ─── Config ──────────────────────────────────────────────────────────────────

// Config for the health checker.
type Config struct {
	// CheckInterval is how often to ping workers.
	CheckInterval time.Duration

	// RestartDelay is how long to wait before restarting a failed worker.
	RestartDelay time.Duration

	// MaxRestarts limits consecutive restarts before giving up.
	// 0 = unlimited.
	MaxRestarts int
}

// DefaultConfig returns sensible defaults.
func DefaultConfig() Config {
	return Config{
		CheckInterval: 5 * time.Second,
		RestartDelay:  1 * time.Second,
		MaxRestarts:   10,
	}
}

// ─── Worker Definition ───────────────────────────────────────────────────────

// Worker represents a monitored process.
type Worker struct {
	Name    string
	Command string   // e.g. "python3"
	Args    []string // e.g. ["-m", "py_workers.server"]
	Env     []string // e.g. ["MINXG_HOME=/opt/minxg"]

	// HealthCheck is called periodically to verify the worker is alive.
	// Return nil if healthy, error otherwise.
	HealthCheck func(ctx context.Context) error

	// OnCrash is called when a worker crashes. If it returns false,
	// the worker won't be restarted.
	OnCrash func(workerName string, exitCode int, restartCount int) bool
}

// ─── Checker ─────────────────────────────────────────────────────────────────

// Checker manages health checks for multiple workers.
type Checker struct {
	cfg     Config
	mu      sync.Mutex
	workers map[string]*managedWorker

	// Metrics
	totalRestarts atomic.Int64
	activeWorkers atomic.Int64
}

type managedWorker struct {
	Worker
	cmd          *exec.Cmd
	cancel       context.CancelFunc
	restartCount int
	done         chan struct{}
}

// NewChecker creates a health checker.
func NewChecker(cfg Config) *Checker {
	if cfg.CheckInterval <= 0 {
		cfg.CheckInterval = 5 * time.Second
	}
	if cfg.RestartDelay <= 0 {
		cfg.RestartDelay = 1 * time.Second
	}
	return &Checker{
		cfg:     cfg,
		workers: make(map[string]*managedWorker),
	}
}

// Register adds a worker to monitor and starts it.
func (c *Checker) Register(ctx context.Context, w Worker) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if _, exists := c.workers[w.Name]; exists {
		return fmt.Errorf("worker %q already registered", w.Name)
	}

	mw := &managedWorker{
		Worker: w,
		done:   make(chan struct{}),
	}

	ctx, mw.cancel = context.WithCancel(ctx)
	c.workers[w.Name] = mw

	go c.runWorker(ctx, mw)
	c.activeWorkers.Add(1)
	return nil
}

// Unregister stops monitoring a worker and terminates it.
func (c *Checker) Unregister(name string) error {
	c.mu.Lock()
	mw, ok := c.workers[name]
	if !ok {
		c.mu.Unlock()
		return fmt.Errorf("worker %q not found", name)
	}
	delete(c.workers, name)
	c.mu.Unlock()

	mw.cancel()
	<-mw.done
	c.activeWorkers.Add(-1)
	return nil
}

// Shutdown stops all workers and waits for them to exit.
func (c *Checker) Shutdown() {
	c.mu.Lock()
	for _, mw := range c.workers {
		mw.cancel()
	}
	c.mu.Unlock()

	// Wait with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	for _, mw := range c.workers {
		select {
		case <-mw.done:
		case <-ctx.Done():
			log.Printf("[minxg-health] timeout waiting for %q", mw.Name)
		}
	}
}

// TotalRestarts returns the cumulative restart count.
func (c *Checker) TotalRestarts() int64 { return c.totalRestarts.Load() }

// ActiveWorkers returns the number of registered workers.
func (c *Checker) ActiveWorkers() int64 { return c.activeWorkers.Load() }

// ─── Internal ────────────────────────────────────────────────────────────────

func (c *Checker) runWorker(ctx context.Context, mw *managedWorker) {
	defer close(mw.done)

	for {
		// Start the process
		cmd := exec.CommandContext(ctx, mw.Command, mw.Args...)
		if len(mw.Env) > 0 {
			cmd.Env = mw.Env
		}
		mw.cmd = cmd

		log.Printf("[minxg-health] starting worker %q: %s %v", mw.Name, mw.Command, mw.Args)

		err := cmd.Start()
		if err != nil {
			log.Printf("[minxg-health] worker %q failed to start: %v", mw.Name, err)
			if !c.shouldRestart(mw) {
				return
			}
			continue
		}

		// Health check loop
		ticker := time.NewTicker(c.cfg.CheckInterval)
		doneCh := make(chan error, 1)

		go func() {
			doneCh <- cmd.Wait()
		}()

	healthLoop:
		for {
			select {
			case <-ctx.Done():
				// Graceful stop
				if cmd.Process != nil {
					cmd.Process.Kill()
				}
				<-doneCh
				return

			case err := <-doneCh:
				ticker.Stop()
				exitCode := -1
				if err != nil {
					if exitErr, ok := err.(*exec.ExitError); ok {
						exitCode = exitErr.ExitCode()
					}
				}
				log.Printf("[minxg-health] worker %q exited (code=%d): %v", mw.Name, exitCode, err)

				if !c.shouldRestart(mw) {
					return
				}
				// Break out of health loop, back to outer loop to restart
				mw.restartCount++
				c.totalRestarts.Add(1)

				select {
				case <-time.After(c.cfg.RestartDelay):
				case <-ctx.Done():
					return
				}
				break healthLoop

			case <-ticker.C:
				if mw.HealthCheck != nil {
					if err := mw.HealthCheck(ctx); err != nil {
						log.Printf("[minxg-health] worker %q health check failed: %v", mw.Name, err)
						// Kill and restart
						if cmd.Process != nil {
							cmd.Process.Kill()
						}
						<-doneCh
						ticker.Stop()

						if !c.shouldRestart(mw) {
							return
						}
						mw.restartCount++
						c.totalRestarts.Add(1)
						break healthLoop
					}
				}
			}
		}
		ticker.Stop()
	}
}

func (c *Checker) shouldRestart(mw *managedWorker) bool {
	if c.cfg.MaxRestarts > 0 && mw.restartCount >= c.cfg.MaxRestarts {
		log.Printf("[minxg-health] worker %q reached max restarts (%d), giving up",
			mw.Name, c.cfg.MaxRestarts)
		return false
	}

	if mw.OnCrash != nil && !mw.OnCrash(mw.Name, -1, mw.restartCount) {
		return false
	}

	return true
}

// Ensure imports are used.
var _ = fmt.Sprintf
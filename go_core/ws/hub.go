// Package ws implements the MINXG WebSocket fan-out hub.
//
// Python CLI/TUI instances connect as WebSocket clients. The hub
// broadcasts AI inference streaming results (token-by-token deltas)
// to all connected subscribers on a given channel (session ID or
// room name). This replaces Python's asyncio event loop with Go's
// goroutine-per-conn model — 10K+ concurrent clients on a single node.
package ws

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"sync/atomic"
	"time"

	"nhooyr.io/websocket"
	"nhooyr.io/websocket/wsjson"
)

// ─── Hub ─────────────────────────────────────────────────────────────────────

// Hub manages WebSocket connections grouped by channels (rooms/sessions).
// Each channel fans out broadcasts to all subscribed peers.
type Hub struct {
	mu       sync.RWMutex
	channels map[string]*Channel

	// Global metrics
	totalConns   atomic.Int64
	totalMessages atomic.Int64

	// Config
	maxChannels  int
	maxPerChannel int
	writeTimeout time.Duration
}

// Channel represents a single subscription group (e.g. one AI session).
type Channel struct {
	id    string
	mu    sync.RWMutex
	conns map[*websocket.Conn]context.CancelFunc
	hub   *Hub

	// Per-channel metrics
	connCount atomic.Int64
	msgCount  atomic.Int64
}

// Config for Hub initialization.
type Config struct {
	MaxChannels    int           // 0 = unlimited
	MaxPeersPerRoom int          // 0 = unlimited
	WriteTimeout   time.Duration // default 10s
}

// DefaultConfig returns sane defaults.
func DefaultConfig() Config {
	return Config{
		MaxChannels:    10000,
		MaxPeersPerRoom: 500,
		WriteTimeout:   10 * time.Second,
	}
}

// NewHub creates a new Hub.
func NewHub(cfg Config) *Hub {
	if cfg.WriteTimeout <= 0 {
		cfg.WriteTimeout = 10 * time.Second
	}
	return &Hub{
		channels:     make(map[string]*Channel),
		maxChannels:  cfg.MaxChannels,
		maxPerChannel: cfg.MaxPeersPerRoom,
		writeTimeout: cfg.WriteTimeout,
	}
}

// getOrCreateChannel returns an existing or new channel.
func (h *Hub) getOrCreateChannel(channelID string) (*Channel, error) {
	h.mu.Lock()
	defer h.mu.Unlock()

	if ch, ok := h.channels[channelID]; ok {
		return ch, nil
	}

	if h.maxChannels > 0 && len(h.channels) >= h.maxChannels {
		return nil, fmt.Errorf("max channels (%d) reached", h.maxChannels)
	}

	ch := &Channel{
		id:    channelID,
		conns: make(map[*websocket.Conn]context.CancelFunc),
		hub:   h,
	}
	h.channels[channelID] = ch
	return ch, nil
}

// removeChannelIfEmpty removes the channel when last peer leaves.
func (h *Hub) removeChannelIfEmpty(channelID string) {
	h.mu.Lock()
	defer h.mu.Unlock()

	if ch, ok := h.channels[channelID]; ok {
		ch.mu.RLock()
		empty := len(ch.conns) == 0
		ch.mu.RUnlock()
		if empty {
			delete(h.channels, channelID)
		}
	}
}

// Broadcast pushes a message to all peers in a channel.
// Returns number of peers that received the message.
func (h *Hub) Broadcast(channelID string, msg interface{}) int {
	h.mu.RLock()
	ch, ok := h.channels[channelID]
	h.mu.RUnlock()
	if !ok {
		return 0
	}

	return ch.Broadcast(msg)
}

// BroadcastAll pushes to every peer on every channel.
func (h *Hub) BroadcastAll(msg interface{}) int {
	h.mu.RLock()
	defer h.mu.RUnlock()

	count := 0
	for _, ch := range h.channels {
		count += ch.Broadcast(msg)
	}
	return count
}

// ChannelCount returns active channel count.
func (h *Hub) ChannelCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.channels)
}

// TotalConns returns total connected peers.
func (h *Hub) TotalConns() int64 { return h.totalConns.Load() }

// TotalMessages returns total messages sent.
func (h *Hub) TotalMessages() int64 { return h.totalMessages.Load() }

// ─── Channel ─────────────────────────────────────────────────────────────────

// Broadcast sends a message to all peers in this channel.
func (ch *Channel) Broadcast(msg interface{}) int {
	ch.mu.RLock()
	defer ch.mu.RUnlock()

	if len(ch.conns) == 0 {
		return 0
	}

	// Serialize once, send to all
	data, err := json.Marshal(msg)
	if err != nil {
		log.Printf("[minxg-ws] broadcast marshal error: %v", err)
		return 0
	}

	count := 0
	dead := make([]*websocket.Conn, 0)

	for conn := range ch.conns {
		ctx, cancel := context.WithTimeout(context.Background(), ch.hub.writeTimeout)
		err := conn.Write(ctx, websocket.MessageText, data)
		cancel()

		if err != nil {
			log.Printf("[minxg-ws] write error to %s: %v", conn.RemoteAddr(), err)
			dead = append(dead, conn)
		} else {
			count++
		}
	}

	// Clean up dead connections outside the read lock
	ch.hub.totalMessages.Add(int64(count))
	if len(dead) > 0 {
		ch.mu.RUnlock()
		ch.mu.Lock()
		for _, conn := range dead {
			ch.removeConn(conn)
		}
		ch.mu.Unlock()
		ch.mu.RLock()
	}

	return count
}

// ConnCount returns the number of peers in the channel.
func (ch *Channel) ConnCount() int64 { return ch.connCount.Load() }

// MsgCount returns the number of messages broadcast on this channel.
func (ch *Channel) MsgCount() int64 { return ch.msgCount.Load() }

// removeConn must be called with ch.mu held (write lock).
func (ch *Channel) removeConn(conn *websocket.Conn) {
	if cancel, ok := ch.conns[conn]; ok {
		cancel()
		delete(ch.conns, conn)
		ch.connCount.Add(-1)
		ch.hub.totalConns.Add(-1)
	}
}

// ─── HTTP Handler ────────────────────────────────────────────────────────────

// HandleWS returns an http.HandlerFunc that upgrades to WebSocket.
// URL pattern: /ws/:channel — extracts channel ID from path.
func (h *Hub) HandleWS() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		channelID := r.URL.Query().Get("channel")
		if channelID == "" {
			channelID = r.URL.Path
			// Strip leading /ws/ if present
			if len(channelID) > 4 && channelID[:4] == "/ws/" {
				channelID = channelID[4:]
			}
		}

		if channelID == "" {
			http.Error(w, "channel required", http.StatusBadRequest)
			return
		}

		ch, err := h.getOrCreateChannel(channelID)
		if err != nil {
			http.Error(w, err.Error(), http.StatusServiceUnavailable)
			return
		}

		// Check per-channel limits
		if h.maxPerChannel > 0 && int(ch.ConnCount()) >= h.maxPerChannel {
			http.Error(w, "channel full", http.StatusServiceUnavailable)
			return
		}

		conn, err := websocket.Accept(w, r, &websocket.AcceptOptions{
			InsecureSkipVerify: true, // allow any origin for dev
		})
		if err != nil {
			log.Printf("[minxg-ws] accept error: %v", err)
			return
		}

		h.totalConns.Add(1)
		ch.connCount.Add(1)

		ctx, cancel := context.WithCancel(r.Context())

		ch.mu.Lock()
		ch.conns[conn] = cancel
		ch.mu.Unlock()

		log.Printf("[minxg-ws] new conn %s -> channel %q (%d peers)",
			conn.RemoteAddr(), channelID, ch.ConnCount())

		// Read pump — processes incoming messages from client
		go h.readPump(ctx, conn, ch)

		// Write pump — drains when context is cancelled
		<-ctx.Done()

		ch.mu.Lock()
		ch.removeConn(conn)
		ch.mu.Unlock()

		conn.Close(websocket.StatusNormalClosure, "closed")
		h.removeChannelIfEmpty(channelID)

		log.Printf("[minxg-ws] conn %s left channel %q", conn.RemoteAddr(), channelID)
	}
}

// readPump reads messages from the client. For now just echo-back / discard.
func (h *Hub) readPump(ctx context.Context, conn *websocket.Conn, ch *Channel) {
	defer conn.Close(websocket.StatusNormalClosure, "read pump closed")

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		_, msg, err := conn.Read(ctx)
		if err != nil {
			if websocket.CloseStatus(err) == -1 {
				log.Printf("[minxg-ws] read error: %v", err)
			}
			return
		}

		// Incoming client messages go to the channel's broadcast
		ch.Broadcast(json.RawMessage(msg))
	}
}

// ─── Typed Messages ──────────────────────────────────────────────────────────

// TokenDelta represents a single streaming token for AI inference.
type TokenDelta struct {
	Type      string `json:"type"`       // "token"
	SessionID string `json:"session_id"`
	Token     string `json:"token"`
	Index     int    `json:"index"`
	Done      bool   `json:"done,omitempty"`
}

// SystemMessage represents a system event broadcast to all peers.
type SystemMessage struct {
	Type    string `json:"type"` // "system", "error", "join", "leave"
	Payload interface{} `json:"payload"`
}

// SendToken sends a token delta to a specific channel.
func (h *Hub) SendToken(channelID, sessionID, token string, index int) int {
	return h.Broadcast(channelID, TokenDelta{
		Type:      "token",
		SessionID: sessionID,
		Token:     token,
		Index:     index,
	})
}

// SendDone signals end-of-stream for a session.
func (h *Hub) SendDone(channelID, sessionID string, index int) int {
	return h.Broadcast(channelID, TokenDelta{
		Type:      "token",
		SessionID: sessionID,
		Token:     "",
		Index:     index,
		Done:      true,
	})
}

// SendSystem broadcasts a system message to all peers in a channel.
func (h *Hub) SendSystem(channelID, msgType string, payload interface{}) int {
	return h.Broadcast(channelID, SystemMessage{
		Type:    msgType,
		Payload: payload,
	})
}

// ─── Unused import guard ─────────────────────────────────────────────────────
var _ = wsjson.Write // keep import; used in future typed message helpers
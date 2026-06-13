// Package server — HTTP proxy endpoints for offloading Python network calls.
// Each endpoint here replaces a Python urllib/aiohttp call with Go's native
// net/http, DNS, TLS, and whois libraries.
package server

import (
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"strings"
	"time"
)

// ─── Proxy Request ────────────────────────────────────────────────────────────

// ProxyRequest is the JSON body for /v1/proxy.
type ProxyRequest struct {
	URL             string            `json:"url"`
	Method          string            `json:"method"` // GET, POST, PUT, DELETE, HEAD
	Headers         map[string]string `json:"headers"`
	Body            string            `json:"body"`            // raw body string
	Timeout         int               `json:"timeout"`         // seconds, default 10
	FollowRedirects bool              `json:"follow_redirects"` // default true
	MaxBodyBytes    int               `json:"max_body_bytes"`  // default 500_000
}

// ProxyResponse is the JSON response.
type ProxyResponse struct {
	URL        string            `json:"url"`
	Status     int               `json:"status"`
	Headers    map[string]string `json:"headers"`
	Body       string            `json:"body"`
	BodySize   int               `json:"body_size"`
	Truncated  bool              `json:"truncated"`
	Error      string            `json:"error,omitempty"`
	ElapsedMs  float64           `json:"elapsed_ms"`
}

// InstallProxyHandler registers /v1/proxy for HTTP request forwarding.
func (s *Server) InstallProxyHandler() {
	s.HandleFunc("/v1/proxy", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		if r.Method != http.MethodPost {
			writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "POST required"})
			return
		}

		var req ProxyRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON: " + err.Error()})
			return
		}

		if req.URL == "" {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "url is required"})
			return
		}

		resp := doProxyRequest(req)
		writeJSON(w, http.StatusOK, resp)
	})
}

func doProxyRequest(req ProxyRequest) ProxyResponse {
	t0 := time.Now()

	if req.Method == "" {
		req.Method = "GET"
	}
	if req.Timeout <= 0 {
		req.Timeout = 10
	}
	if req.MaxBodyBytes <= 0 {
		req.MaxBodyBytes = 500_000
	}

	client := &http.Client{
		Timeout: time.Duration(req.Timeout) * time.Second,
	}

	if !req.FollowRedirects {
		client.CheckRedirect = func(req *http.Request, via []*http.Request) error {
			return http.ErrUseLastResponse
		}
	}

	var bodyReader io.Reader
	if req.Body != "" && (req.Method == "POST" || req.Method == "PUT" || req.Method == "PATCH") {
		bodyReader = strings.NewReader(req.Body)
	}

	httpReq, err := http.NewRequest(strings.ToUpper(req.Method), req.URL, bodyReader)
	if err != nil {
		return ProxyResponse{URL: req.URL, Error: err.Error(), ElapsedMs: sinceMs(t0)}
	}

	// Default headers
	httpReq.Header.Set("User-Agent", "MINXG-Go/2.0")
	if req.Body != "" && req.Headers != nil && req.Headers["Content-Type"] == "" {
		httpReq.Header.Set("Content-Type", "application/json")
	}

	for k, v := range req.Headers {
		httpReq.Header.Set(k, v)
	}

	httpResp, err := client.Do(httpReq)
	if err != nil {
		return ProxyResponse{URL: req.URL, Error: err.Error(), ElapsedMs: sinceMs(t0)}
	}
	defer httpResp.Body.Close()

	respHeaders := make(map[string]string)
	for k := range httpResp.Header {
		respHeaders[k] = httpResp.Header.Get(k)
	}

	// Read body, respect max size
	limited := io.LimitReader(httpResp.Body, int64(req.MaxBodyBytes+1))
	raw, err := io.ReadAll(limited)
	if err != nil {
		return ProxyResponse{URL: req.URL, Status: httpResp.StatusCode, Error: err.Error(), ElapsedMs: sinceMs(t0)}
	}

	truncated := len(raw) > req.MaxBodyBytes
	if truncated {
		raw = raw[:req.MaxBodyBytes]
	}

	return ProxyResponse{
		URL:       req.URL,
		Status:    httpResp.StatusCode,
		Headers:   respHeaders,
		Body:      string(raw),
		BodySize:  len(raw),
		Truncated: truncated,
		ElapsedMs: sinceMs(t0),
	}
}

// ─── DNS Lookup ───────────────────────────────────────────────────────────────

// InstallDNSHandler registers /v1/dns/lookup endpoint.
func (s *Server) InstallDNSHandler() {
	s.HandleFunc("/v1/dns/lookup", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		host := r.URL.Query().Get("host")
		if host == "" {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "host query param required"})
			return
		}

		t0 := time.Now()
		ips, err := net.LookupIP(host)
		if err != nil {
			writeJSON(w, http.StatusOK, map[string]interface{}{
				"host": host, "error": err.Error(), "elapsed_ms": sinceMs(t0),
			})
			return
		}

		cname, _ := net.LookupCNAME(host)
		mxRecords, _ := net.LookupMX(host)
		nsRecords, _ := net.LookupNS(host)

		ipStrs := make([]string, 0, len(ips))
		for _, ip := range ips {
			ipStrs = append(ipStrs, ip.String())
		}

		mxStrs := make([]map[string]interface{}, 0, len(mxRecords))
		for _, mx := range mxRecords {
			mxStrs = append(mxStrs, map[string]interface{}{
				"host": mx.Host, "pref": mx.Pref,
			})
		}

		nsStrs := make([]string, 0, len(nsRecords))
		for _, ns := range nsRecords {
			nsStrs = append(nsStrs, ns.Host)
		}

		writeJSON(w, http.StatusOK, map[string]interface{}{
			"host":       host,
			"ips":        ipStrs,
			"cname":      cname,
			"mx":         mxStrs,
			"ns":         nsStrs,
			"elapsed_ms": sinceMs(t0),
		})
	})
}

// ─── SSL/TLS Certificate Check ────────────────────────────────────────────────

// InstallSSLCheckHandler registers /v1/ssl/check endpoint.
func (s *Server) InstallSSLCheckHandler() {
	s.HandleFunc("/v1/ssl/check", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		host := r.URL.Query().Get("host")
		if host == "" {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "host query param required"})
			return
		}

		t0 := time.Now()

		// Ensure port
		if !strings.Contains(host, ":") {
			host = host + ":443"
		}

		conn, err := tls.DialWithDialer(
			&net.Dialer{Timeout: 5 * time.Second},
			"tcp", host,
			&tls.Config{InsecureSkipVerify: true},
		)
		if err != nil {
			writeJSON(w, http.StatusOK, map[string]interface{}{
				"host": host, "error": err.Error(), "elapsed_ms": sinceMs(t0),
			})
			return
		}
		defer conn.Close()

		state := conn.ConnectionState()
		if len(state.PeerCertificates) == 0 {
			writeJSON(w, http.StatusOK, map[string]interface{}{
				"host": host, "error": "no certificates", "elapsed_ms": sinceMs(t0),
			})
			return
		}

		cert := state.PeerCertificates[0]
		now := time.Now()
		daysLeft := int(cert.NotAfter.Sub(now).Hours() / 24)

		sans := make([]string, 0)
		sans = append(sans, cert.DNSNames...)
		for _, ip := range cert.IPAddresses {
			sans = append(sans, ip.String())
		}

		issuer := ""
		if len(cert.Issuer.Organization) > 0 {
			issuer = cert.Issuer.Organization[0]
		}

		writeJSON(w, http.StatusOK, map[string]interface{}{
			"host":            host,
			"subject":         cert.Subject.CommonName,
			"issuer":          issuer,
			"serial":          fmt.Sprintf("%X", cert.SerialNumber),
			"not_before":      cert.NotBefore.Format(time.RFC3339),
			"not_after":       cert.NotAfter.Format(time.RFC3339),
			"days_remaining":  daysLeft,
			"expired":         daysLeft <= 0,
			"expiring_soon":   daysLeft > 0 && daysLeft <= 30,
			"sans":            sans,
			"version":         cert.Version,
			"sig_algorithm":   cert.SignatureAlgorithm.String(),
			"tls_version":     tls.VersionName(state.Version),
			"cipher_suite":    tls.CipherSuiteName(state.CipherSuite),
			"elapsed_ms":      sinceMs(t0),
		})
	})
}

// ─── WHOIS Lookup ─────────────────────────────────────────────────────────────

// InstallWhoisHandler registers /v1/whois endpoint.
func (s *Server) InstallWhoisHandler() {
	s.HandleFunc("/v1/whois", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		domain := r.URL.Query().Get("domain")
		if domain == "" {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "domain query param required"})
			return
		}

		t0 := time.Now()

		// Simple WHOIS via TCP to whois.iana.org (port 43).
		// For production, use a proper whois library or delegate to a service.
		conn, err := net.DialTimeout("tcp", "whois.iana.org:43", 5*time.Second)
		if err != nil {
			writeJSON(w, http.StatusOK, map[string]interface{}{
				"domain": domain, "error": "WHOIS server unreachable: " + err.Error(),
				"elapsed_ms": sinceMs(t0),
			})
			return
		}
		defer conn.Close()

		fmt.Fprintf(conn, "%s\r\n", domain)
		raw, _ := io.ReadAll(io.LimitReader(conn, 65536))

		writeJSON(w, http.StatusOK, map[string]interface{}{
			"domain":     domain,
			"raw":        string(raw),
			"whois_host": "whois.iana.org:43",
			"elapsed_ms": sinceMs(t0),
		})
	})
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

func sinceMs(t0 time.Time) float64 {
	return float64(time.Since(t0).Microseconds()) / 1000.0
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}
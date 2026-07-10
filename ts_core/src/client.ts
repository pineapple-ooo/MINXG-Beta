/**
 * MinxgClient — type-safe HTTP client for the MINXG Gateway.
 *
 * Features:
 * - Immutable config (freeze on construct, open new client for changes)
 * - Streaming SSE parser with typed events
 * - Automatic retry with exponential backoff (no infinite loops)
 * - Connection reuse (keep-alive by default)
 * - Timeout enforcement per request
 */

import type {
  ChatCompletionRequest,
  ChatCompletionResponse,
  ChatStreamEvent,
  GatewayInfo,
  HealthResponse,
  GatewayError,
} from "./schema.js";

// ─── Configuration ────────────────────────────────────────────────────────────

export interface MinxgClientConfig {
  /** Gateway base URL (default: http://127.0.0.1:18080) */
  baseUrl: string;
  /** API key (Bearer auth). If omitted, reads from MINXG_API_KEY env. */
  apiKey?: string;
  /** Request timeout in ms (default: 30_000). */
  timeoutMs?: number;
  /** Max retry attempts for transient errors (default: 3). */
  maxRetries?: number;
  /** Custom headers to inject into every request. */
  headers?: Record<string, string>;
}

const DEFAULT_CONFIG: Required<Omit<MinxgClientConfig, "apiKey">> = {
  baseUrl: "http://127.0.0.1:18080",
  timeoutMs: 30_000,
  maxRetries: 3,
  headers: {},
};

// ─── Client ────────────────────────────────────────────────────────────────────

export class MinxgClient {
  private readonly config: Readonly<
    Required<Omit<MinxgClientConfig, "apiKey">> & { apiKey?: string }
  >;

  constructor(config: Partial<MinxgClientConfig> = {}) {
    this.config = Object.freeze({
      ...DEFAULT_CONFIG,
      ...config,
      apiKey: config.apiKey ?? process.env["MINXG_API_KEY"],
    });
  }

  /** Create a new client with overridden configuration (immutable pattern). */
  with(overrides: Partial<MinxgClientConfig>): MinxgClient {
    return new MinxgClient({ ...this.config, ...overrides });
  }

  /** Get current readonly config. */
  getConfig(): Readonly<MinxgClientConfig> {
    return this.config as Readonly<MinxgClientConfig>;
  }

  // ─── Health ────────────────────────────────────────────────────────────────

  /** GET /health — returns gateway status and registered workers. */
  async health(): Promise<HealthResponse> {
    const res = await this.fetchJSON<HealthResponse>("/health");
    return res;
  }

  // ─── Models ────────────────────────────────────────────────────────────────

  /** GET /v1/models — list available models. */
  async models(): Promise<GatewayInfo> {
    const res = await this.fetchJSON<GatewayInfo>("/v1/models");
    return res;
  }

  // ─── Chat Completions ──────────────────────────────────────────────────────

  /** POST /v1/chat/completions — non-streaming chat. */
  async chat(req: ChatCompletionRequest): Promise<ChatCompletionResponse> {
    const body = req.stream === true ? { ...req, stream: false } : req;
    const res = await this.fetchJSON<ChatCompletionResponse>(
      "/v1/chat/completions",
      { method: "POST", body },
    );
    return res;
  }

  /** POST /v1/chat/completions — streaming chat (returns async iterable). */
  async *chatStream(
    req: ChatCompletionRequest,
  ): AsyncIterable<ChatStreamEvent> {
    const controller = new AbortController();
    const timeout = setTimeout(
      () => controller.abort(),
      this.config.timeoutMs,
    );

    try {
      const url = `${this.config.baseUrl}/v1/chat/completions`;
      const headers = this.buildHeaders();
      headers["Accept"] = "text/event-stream";

      const response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify({ ...req, stream: true }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const err = await this.parseError(response);
        yield { type: "error", message: err.error.message, code: response.status };
        return;
      }

      if (!response.body) {
        yield { type: "error", message: "No response body", code: 500 };
        return;
      }

      // Parse SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? ""; // keep incomplete line

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6).trim();
              if (data === "[DONE]") {
                yield { type: "done", finish_reason: "stop" };
                return;
              }
              try {
                const event = this.parseStreamData(data);
                yield event;
              } catch {
                // Skip unparseable chunks (malformed SSE)
                continue;
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        yield { type: "error", message: "Request timed out", code: 408 };
      } else {
        yield {
          type: "error",
          message: err instanceof Error ? err.message : "Unknown streaming error",
          code: 0,
        };
      }
    } finally {
      clearTimeout(timeout);
    }
  }

  // ─── Internal helpers ──────────────────────────────────────────────────────

  private buildHeaders(): Record<string, string> {
    const h: Record<string, string> = {
      "Content-Type": "application/json",
      ...this.config.headers,
    };
    if (this.config.apiKey) {
      h["Authorization"] = `Bearer ${this.config.apiKey}`;
    }
    return h;
  }

  private async fetchJSON<T>(
    path: string,
    opts?: { method?: string; body?: unknown },
  ): Promise<T> {
    const url = `${this.config.baseUrl}${path}`;
    const headers = this.buildHeaders();
    let lastErr: Error | null = null;
    const maxRetries = this.config.maxRetries;
    const timeoutMs = this.config.timeoutMs;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), timeoutMs);

      try {
        const response = await fetch(url, {
          method: opts?.method ?? "GET",
          headers,
          body: opts?.body ? JSON.stringify(opts.body) : undefined,
          signal: controller.signal,
          // keep-alive for connection reuse
        });

        if (response.ok) {
          const json = (await response.json()) as T;
          return json;
        }

        const errBody = await this.parseError(response);

        // Only retry on 429, 503, 502 (transient)
        if (
          attempt < maxRetries &&
          (response.status === 429 ||
            response.status === 503 ||
            response.status === 502)
        ) {
          const delay = Math.min(1000 * 2 ** attempt, 10000);
          await sleep(delay + Math.random() * 500);
          continue;
        }

        throw new MinxgGatewayError(
          errBody.error.message,
          response.status,
          errBody.error.type,
        );
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          lastErr = new MinxgGatewayError("Request timed out", 408, "timeout");
        } else if (err instanceof MinxgGatewayError) {
          throw err;
        } else {
          lastErr = err instanceof Error ? err : new Error(String(err));
        }

        if (attempt >= maxRetries) break;

        const delay = Math.min(500 * 2 ** attempt, 5000);
        await sleep(delay);
      } finally {
        clearTimeout(timeout);
      }
    }

    throw lastErr ?? new Error("Unknown fetch error");
  }

  private async parseError(response: Response): Promise<GatewayError> {
    try {
      return (await response.json()) as GatewayError;
    } catch {
      return {
        error: {
          message: response.statusText || "Unknown error",
          type: "http_error",
          code: response.status,
        },
      };
    }
  }

  private parseStreamData(data: string): ChatStreamEvent {
    // Try JSON delta format (OpenAI style)
    try {
      const parsed = JSON.parse(data);
      if (parsed.choices?.[0]?.delta?.content) {
        return {
          type: "text",
          content: parsed.choices[0].delta.content as string,
        };
      }
      if (parsed.choices?.[0]?.delta?.tool_calls) {
        return {
          type: "tool_call",
          call: parsed.choices[0].delta.tool_calls[0] as ChatStreamEvent & {
            type: "tool_call";
          },
        };
      }
      if (parsed.choices?.[0]?.finish_reason) {
        return {
          type: "done",
          finish_reason: parsed.choices[0].finish_reason as string,
        };
      }
      // MINXG custom events
      if (parsed.type === "thinking") {
        return { type: "thinking", content: parsed.content as string };
      }
      if (parsed.type === "tool_result") {
        return {
          type: "tool_result",
          call_id: parsed.call_id as string,
          result: parsed.result as string,
        };
      }
      // Fallback: treat as text chunk
      return { type: "text", content: "" };
    } catch {
      // Plain text SSE
      return { type: "text", content: data };
    }
  }
}

// ─── Custom error ──────────────────────────────────────────────────────────────

export class MinxgGatewayError extends Error {
  public readonly statusCode: number;
  public readonly errorType: string;

  constructor(message: string, statusCode: number, errorType: string) {
    super(`MINXG Gateway ${statusCode}: ${message}`);
    this.name = "MinxgGatewayError";
    this.statusCode = statusCode;
    this.errorType = errorType;
  }
}

// ─── Utility ───────────────────────────────────────────────────────────────────

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
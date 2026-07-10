/**
 * Schema definitions for MINXG Gateway — strictly typed, no `any`.
 *
 * Every type here corresponds to a JSON payload that the gateway
 * sends or receives. These are the source of truth for the TypeScript SDK.
 */

// ─── Chat Completion ──────────────────────────────────────────────────────────

/** A single chat message (system/user/assistant/tool). */
export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string | null;
  name?: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
}

/** A tool call function block (OpenAI format). */
export interface ToolCallFunction {
  name: string;
  arguments: string; // JSON-encoded, validated on parse
}

/** A tool call object (request or response). */
export interface ToolCall {
  id: string;
  type: "function";
  function: ToolCallFunction;
  index?: number;
}

/** Tool definition (sent in request). */
export interface ToolDefinition {
  type: "function";
  function: {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
  };
}

/** OpenAI-compatible chat completion request. */
export interface ChatCompletionRequest {
  model: string;
  messages: ChatMessage[];
  temperature?: number;
  top_p?: number;
  n?: number;
  stream?: boolean;
  stop?: string | string[];
  max_tokens?: number;
  presence_penalty?: number;
  frequency_penalty?: number;
  tools?: ToolDefinition[];
  tool_choice?: "auto" | "none" | { type: "function"; function: { name: string } };
  reasoning_effort?: "xhigh" | "high" | "medium" | "low" | "minimal" | "none";
  user?: string;
}

/** A single completion choice. */
export interface ChatCompletionChoice {
  index: number;
  message: ChatMessage;
  finish_reason: "stop" | "length" | "tool_calls" | "content_filter" | null;
  logprobs?: null;
}

/** OpenAI-compatible chat completion response. */
export interface ChatCompletionResponse {
  id: string;
  object: "chat.completion";
  created: number;
  model: string;
  choices: ChatCompletionChoice[];
  usage?: TokenUsage;
  system_fingerprint?: string;
}

/** Token usage statistics. */
export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

// ─── Streaming (SSE) ──────────────────────────────────────────────────────────

/** Parsed SSE event chunk from streaming chat. */
export type ChatStreamEvent =
  | { type: "text"; content: string }
  | { type: "thinking"; content: string }
  | { type: "tool_call"; call: ToolCall }
  | { type: "tool_result"; call_id: string; result: string }
  | { type: "done"; finish_reason: string }
  | { type: "error"; message: string; code?: number };

// ─── Gateway ───────────────────────────────────────────────────────────────────

/** Gateway health/info endpoint response. */
export interface HealthResponse {
  status: "ok" | "degraded" | "down";
  version: string;
  registered_workers: string[];
  uptime_seconds: number;
}

/** Individual model descriptor. */
export interface ModelInfo {
  id: string;
  object: "model";
  created: number;
  owned_by: string;
  permission?: unknown[];
}

/** /v1/models response. */
export interface GatewayInfo {
  object: "list";
  data: ModelInfo[];
}

// ─── Workspace ─────────────────────────────────────────────────────────────────

/** Individual workspace slot (structured context). */
export interface WorkspaceSlot {
  name: string;
  content: string;
  max_chars: number;
  version: number;
  updated_at: string;
}

/** Workspace status response. */
export interface WorkspaceStatus {
  session_id: string;
  slots: Record<string, WorkspaceSlot>;
  total_chars_used: number;
  total_chars_capacity: number;
}

/** Workspace session summary. */
export interface WorkspaceSession {
  session_id: string;
  active: boolean;
  created_at: string;
  slot_count: number;
}

// ─── RAG ───────────────────────────────────────────────────────────────────────

/** A knowledge chunk in the RAG store. */
export interface RagDocument {
  id: string;
  content: string;
  metadata?: Record<string, string>;
  source?: string;
  added_at?: string;
}

/** RAG search request. */
export interface RagAddRequest {
  documents: RagDocument[];
}

/** RAG search result. */
export interface RagSearchResult {
  document: RagDocument;
  score: number;
  method: "bm25" | "semantic" | "hybrid";
}

// ─── Error ─────────────────────────────────────────────────────────────────────

/** Standardized error response from gateway. */
export interface GatewayError {
  error: {
    message: string;
    type: string;
    code?: number;
    param?: string;
  };
}

// ─── Utility types ─────────────────────────────────────────────────────────────

/** Branded string type for validated tool names. */
declare const ToolNameBrand: unique symbol;
export type ToolName = string & { [ToolNameBrand]: true };

/** Known MINXG tool names (exhaustive — when a new tool is added, this must grow). */
export const KNOWN_TOOLS = [
  "fs_read", "fs_write", "fs_list", "fs_search", "fs_copy",
  "web_search", "web_fetch", "web_extract",
  "sh_exec", "sh_query", "system_info",
  "math_eval", "text_process", "datetime_now",
  "crypto_hash", "crypto_encrypt", "crypto_decrypt",
  "encoding_convert",
  "db_query", "media_convert",
  "gateway_start", "gateway_stop", "gateway_status",
] as const;

export type KnownTool = (typeof KNOWN_TOOLS)[number];
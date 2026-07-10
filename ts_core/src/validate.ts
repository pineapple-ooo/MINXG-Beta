/**
 * Schema validation — zero-cost runtime type guards for MINXG JSON payloads.
 *
 * Philosophy: validate at boundaries (HTTP ingress/egress), trust internally.
 * No `any` — every validator returns a narrowed type.
 */

import type { ChatMessage, ChatCompletionRequest, ToolCall } from "./schema.js";

// ─── Messages ─────────────────────────────────────────────────────────────────

const VALID_ROLES = new Set(["system", "user", "assistant", "tool"] as const);

/**
 * Validate a single chat message. Returns `null` if invalid (instead of
 * throwing — message-level, not request-level).
 */
export function validateMessage(raw: unknown): ChatMessage | null {
  if (typeof raw !== "object" || raw === null) return null;
  const m = raw as Record<string, unknown>;

  const role = m["role"];
  if (typeof role !== "string" || !VALID_ROLES.has(role as ChatMessage["role"]))
    return null;

  const content = m["content"];
  if (content !== null && typeof content !== "string") return null;

  const name = m["name"];
  if (name !== undefined && typeof name !== "string") return null;

  const toolCalls = m["tool_calls"];
  if (toolCalls !== undefined) {
    if (!Array.isArray(toolCalls)) return null;
    for (const tc of toolCalls) {
      if (!tc || typeof tc !== "object" || !tc["id"] || tc["type"] !== "function")
        return null;
    }
  }

  const toolCallId = m["tool_call_id"];
  if (toolCallId !== undefined && typeof toolCallId !== "string") return null;

  return {
    role: role as ChatMessage["role"],
    content: content as string | null,
    ...(name !== undefined && { name: name as string }),
    ...(toolCalls !== undefined && {
      tool_calls: toolCalls as ToolCall[],
    }),
    ...(toolCallId !== undefined && { tool_call_id: toolCallId as string }),
  };
}

/** Validate an array of chat messages. */
export function validateMessages(raw: unknown): ChatMessage[] | null {
  if (!Array.isArray(raw)) return null;
  const result: ChatMessage[] = [];
  for (const item of raw) {
    const validated = validateMessage(item);
    if (!validated) return null;
    result.push(validated);
  }
  if (result.length === 0) return null;
  return result;
}

/** Coerce unknown input to a message (non-null always — fills defaults). */
export function coerceToMessage(raw: unknown): ChatMessage {
  const validated = validateMessage(raw);
  if (validated) return validated;
  // Best-effort coercion
  if (typeof raw === "object" && raw !== null) {
    const m = raw as Record<string, unknown>;
    return {
      role: (typeof m["role"] === "string" && VALID_ROLES.has(m["role"] as ChatMessage["role"])
        ? m["role"]
        : "user") as ChatMessage["role"],
      content: typeof m["content"] === "string" ? m["content"] : null,
    };
  }
  return { role: "user", content: typeof raw === "string" ? raw : null };
}

// ─── Chat Request ─────────────────────────────────────────────────────────────

/**
 * Validate a chat completion request. Returns narrowed request or an
 * error message string.
 */
export function validateChatRequest(
  raw: unknown,
): { ok: true; value: ChatCompletionRequest } | { ok: false; error: string } {
  if (typeof raw !== "object" || raw === null) {
    return { ok: false, error: "Request must be an object" };
  }
  const r = raw as Record<string, unknown>;

  if (typeof r["model"] !== "string" || r["model"].length === 0) {
    return { ok: false, error: "Missing 'model' field" };
  }

  const messages = r["messages"];
  const validated = validateMessages(messages);
  if (!validated) {
    return { ok: false, error: "'messages' must be a non-empty array of valid messages" };
  }

  const request: ChatCompletionRequest = {
    model: r["model"] as string,
    messages: validated,
  };

  // Optional numeric fields
  for (const f of [
    "temperature",
    "top_p",
    "max_tokens",
    "presence_penalty",
    "frequency_penalty",
  ] as const) {
    const v = r[f];
    if (v !== undefined) {
      if (typeof v !== "number") return { ok: false, error: `'${f}' must be a number` };
      (request as Record<string, unknown>)[f] = v;
    }
  }

  if (r["stop"] !== undefined) {
    if (typeof r["stop"] !== "string" && !Array.isArray(r["stop"])) {
      return { ok: false, error: "'stop' must be a string or array of strings" };
    }
    request.stop = r["stop"] as string | string[];
  }

  if (r["stream"] !== undefined) {
    if (typeof r["stream"] !== "boolean")
      return { ok: false, error: "'stream' must be a boolean" };
    request.stream = r["stream"] as boolean;
  }

  if (r["n"] !== undefined) {
    if (typeof r["n"] !== "number" || (r["n"] as number) < 1)
      return { ok: false, error: "'n' must be a positive integer" };
    request.n = r["n"] as number;
  }

  return { ok: true, value: request };
}

// ─── Tool Calls ───────────────────────────────────────────────────────────────

export function validateToolCall(raw: unknown): ToolCall | null {
  if (typeof raw !== "object" || raw === null) return null;
  const tc = raw as Record<string, unknown>;

  if (typeof tc["id"] !== "string") return null;
  if (tc["type"] !== "function") return null;

  const fn = tc["function"];
  if (typeof fn !== "object" || fn === null) return null;
  const f = fn as Record<string, unknown>;
  if (typeof f["name"] !== "string") return null;
  if (typeof f["arguments"] !== "string") return null;

  // Verify arguments is valid JSON
  try {
    JSON.parse(f["arguments"]);
  } catch {
    return null;
  }

  return {
    id: tc["id"] as string,
    type: "function",
    function: {
      name: f["name"] as string,
      arguments: f["arguments"] as string,
    },
    ...(typeof tc["index"] === "number" && { index: tc["index"] as number }),
  };
}
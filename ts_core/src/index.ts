/**
 * MINXG Gateway TypeScript SDK — type-safe client, middleware, schema.
 *
 * Design:
 * - **No `any`** — every JSON payload is validated via TypeScript interfaces.
 * - **Immutable request builders** — chainable, never mutate input config.
 * - **Streaming-first** — SSE parser emits typed events, not raw strings.
 * - **Zero runtime deps** — depends only on Node.js standard library.
 *
 * @module @minxg/gateway-ts
 * @version 0.14.1
 */

export { MinxgClient, type MinxgClientConfig } from "./client.js";
export {
  // Chat Completion types (OpenAI-compatible)
  type ChatMessage,
  type ChatCompletionRequest,
  type ChatCompletionResponse,
  type ChatCompletionChoice,
  type ToolCall,
  type ToolCallFunction,
  type ChatStreamEvent,
  // Workspace types
  type WorkspaceSlot,
  type WorkspaceStatus,
  type WorkspaceSession,
  // RAG types
  type RagDocument,
  type RagSearchResult,
  type RagAddRequest,
  // Gateway types
  type GatewayInfo,
  type HealthResponse,
  type ModelInfo,
} from "./schema.js";
export {
  // Validation utilities
  validateMessage,
  validateMessages,
  validateChatRequest,
  validateToolCall,
  coerceToMessage,
} from "./validate.js";

/** Semver version synced with `minxg._version.VERSION`. */
export const VERSION = "0.14.1" as const;

/** Number of TypeScript-schema-covered operators. */
export const TS_OPERATOR_COUNT = 20 as const;
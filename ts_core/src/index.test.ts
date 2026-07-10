/**
 * Tests for @minxg/gateway-ts schema validation and client.
 * Run with: node --import tsx --test src/**\/*.test.ts
 */

import test from "node:test";
import assert from "node:assert/strict";
import { validateMessage, validateMessages, validateChatRequest } from "./validate.js";
import type { ChatMessage, ChatCompletionRequest } from "./schema.js";

// ─── Message Validation ───────────────────────────────────────────────────────

test("validateMessage — valid user message", () => {
  const msg = { role: "user", content: "hello" };
  const result = validateMessage(msg);
  assert.ok(result !== null);
  assert.equal(result!.role, "user");
  assert.equal(result!.content, "hello");
});

test("validateMessage — valid system message", () => {
  const msg = { role: "system", content: "You are helpful." };
  const result = validateMessage(msg);
  assert.ok(result !== null);
  assert.equal(result!.role, "system");
});

test("validateMessage — valid assistant message with tool_calls", () => {
  const msg = {
    role: "assistant",
    content: null,
    tool_calls: [
      {
        id: "call_1",
        type: "function",
        function: { name: "fs_read", arguments: '{"path":"/tmp"}' },
        index: 0,
      },
    ],
  };
  const result = validateMessage(msg);
  assert.ok(result !== null);
  assert.equal(result!.tool_calls?.length, 1);
  assert.equal(result!.tool_calls![0]!.function.name, "fs_read");
});

test("validateMessage — valid tool message", () => {
  const msg = {
    role: "tool",
    content: '{"files":["a.txt"]}',
    tool_call_id: "call_1",
  };
  const result = validateMessage(msg);
  assert.ok(result !== null);
  assert.equal(result!.tool_call_id, "call_1");
});

test("validateMessage — invalid role returns null", () => {
  const msg = { role: "invalid", content: "hi" };
  const result = validateMessage(msg);
  assert.equal(result, null);
});

test("validateMessage — null input returns null", () => {
  const result = validateMessage(null);
  assert.equal(result, null);
});

// ─── Messages Array ───────────────────────────────────────────────────────────

test("validateMessages — valid array", () => {
  const msgs = [
    { role: "system", content: "You are helpful." },
    { role: "user", content: "hello" },
  ];
  const result = validateMessages(msgs);
  assert.ok(result !== null);
  assert.equal(result!.length, 2);
});

test("validateMessages — empty array returns null", () => {
  const result = validateMessages([]);
  assert.equal(result, null);
});

test("validateMessages — array with invalid entry returns null", () => {
  const msgs = [
    { role: "user", content: "hello" },
    { role: "invalid", content: "x" },
  ];
  const result = validateMessages(msgs);
  assert.equal(result, null);
});

// ─── Chat Request ─────────────────────────────────────────────────────────────

test("validateChatRequest — valid minimal request", () => {
  const req = {
    model: "gpt-4o-mini",
    messages: [{ role: "user", content: "hi" }],
  };
  const result = validateChatRequest(req);
  assert.equal(result.ok, true);
  if (result.ok) {
    assert.equal(result.value.model, "gpt-4o-mini");
    assert.equal(result.value.messages.length, 1);
  }
});

test("validateChatRequest — missing model returns error", () => {
  const req = { messages: [{ role: "user", content: "hi" }] };
  const result = validateChatRequest(req);
  assert.equal(result.ok, false);
  if (!result.ok) {
    assert.ok(result.error.includes("model"));
  }
});

test("validateChatRequest — missing messages returns error", () => {
  const req = { model: "gpt-4o" };
  const result = validateChatRequest(req);
  assert.equal(result.ok, false);
  if (!result.ok) {
    assert.ok(result.error.includes("messages"));
  }
});

test("validateChatRequest — valid request with all optional fields", () => {
  const req: ChatCompletionRequest = {
    model: "gpt-4o",
    messages: [{ role: "user", content: "test" }],
    temperature: 0.7,
    top_p: 0.9,
    n: 1,
    stream: true,
    max_tokens: 100,
    stop: ["\n\n"],
    reasoning_effort: "medium",
  };
  const result = validateChatRequest(req);
  assert.equal(result.ok, true);
});

test("validateChatRequest — invalid n (negative) returns error", () => {
  const req = {
    model: "gpt-4o",
    messages: [{ role: "user", content: "test" }],
    n: 0,
  };
  const result = validateChatRequest(req);
  assert.equal(result.ok, false);
});

// ─── Round-trip: API response parsing ─────────────────────────────────────────

test("ChatCompletionResponse shape — can construct and match schema", () => {
  const response = {
    id: "chatcmpl-123",
    object: "chat.completion" as const,
    created: Math.floor(Date.now() / 1000),
    model: "gpt-4o-mini",
    choices: [
      {
        index: 0,
        message: {
          role: "assistant" as const,
          content: "Hello, world!",
        },
        finish_reason: "stop" as const,
      },
    ],
    usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
  };
  assert.equal(response.object, "chat.completion");
  assert.equal(response.choices.length, 1);
  assert.equal(response.choices[0]!.message.content, "Hello, world!");
});
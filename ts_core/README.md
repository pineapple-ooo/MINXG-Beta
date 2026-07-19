# MINXG TypeScript Gateway

Type-safe SDK + middleware for the MINXG OpenAI-compatible gateway.

## Install

```bash
cd ts_core
npm install
npm run build
```

## Use from TypeScript

```ts
import { MinxgClient } from "@minxg/gateway-ts";

const client = new MinxgClient({
  baseUrl: "http://127.0.0.1:18080",
  apiKey: "sk-...",
});

const resp = await client.chat({
  model: "gpt-4o-mini",
  messages: [{ role: "user", content: "Hello" }],
});

console.log(resp.choices[0].message.content);
```

## Streaming

```ts
for await (const ev of client.chatStream({...})) {
  if (ev.type === "text") process.stdout.write(ev.content);
  else if (ev.type === "tool_call") console.log("tool:", ev.call.function.name);
  else if (ev.type === "done") break;
}
```

## Zero `any`

Every payload is strictly typed via `interface`. Every validator returns
a narrowed type. The compiler catches schema drift at build time.

## Type-safe schema (sample)

```ts
interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string | null;
  name?: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
}
```

## Tests

```bash
npm test
```
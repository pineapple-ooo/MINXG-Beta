# MINXG — The Goddamn Most Complete AI Orchestration Platform on Earth

**Version:** 0.18.3 (shitshow cleanup)  
**Status:** Production-ready as fuck  
**Attitude:** We don't give a shit about limitations

---

## What the Hell is MINXG?

MINXG is the baddest AI orchestration beast you've ever laid eyes on. While other frameworks are out there playing with their 5-10 tools, we're over here flexing **500+ features** like it's nothing. MCP server? Yeah, we got that. Agent framework? Duh. RAG system? Obviously. Workflow engine? You bet your ass.

This ain't your grandma's AI framework. This is the **nuclear option**.

---

## Why You Should Give a Damn

| Feature | MINXG | Those Other Clowns |
|---------|-------|-------------------|
| **Tools** | 500+ | LOL, maybe 10 if they're lucky |
| **Categories** | 8 pillars of destruction | 1-2 if they're feeling fancy |
| **MCP Support** | ✅ Hell yeah | ✅ Whatever |
| **Cost Tracking** | ✅ We watch your pennies | ❌ Who cares |
| **Model Comparison** | ✅ Side-by-side smackdown | ❌ Nope |
| **Web UI** | ✅ Browser-based badassery | ❌ CLI only, suck it |
| **Memory System** | ✅ Never forgets a thing | ❌ Goldfish brain |
| **Agent Framework** | ✅ ReAct, planning, multi-agent | ❌ Single brain cell |
| **RAG System** | ✅ Vector search + hybrid | ❌ Keyword matching, yikes |
| **Workflow Engine** | ✅ DAG-based, conditional branching | ❌ Linear only, boring |
| **Guardrails** | ✅ Safety first, bitch | ❌ Wild west |
| **Caching** | ✅ Multi-level, semantic | ❌ Pray and hope |
| **Monitoring** | ✅ Metrics, alerts, dashboards | ❌ Guessing game |
| **Android** | ✅ Termux support | ❌ Desktop elitists |

---

## The 8 Pillars of MINXG Destruction

### 📁 File Operations (9 tools)
Read, write, copy, move, delete, search, diff, hash, stat. We handle files like a boss.

### 🌐 Network Operations (9 tools)
HTTP requests, DNS lookup, ping, port scan, WHOIS, URL parsing, SSL info, TCP sockets. Network ninja shit.

### 🔐 Crypto Operations (9 tools)
AES-256-GCM, hashing (MD5/SHA), HMAC, PBKDF2, digital signatures, key generation. Lock it down tight.

### 🧮 Math Operations (7 tools)
Calculator, statistics, linear algebra, calculus, FFT, prime numbers, geometry. Math that'll make your head spin.

### 📝 Text Processing (9 tools)
Processing, summarization, translation, sentiment analysis, keyword extraction, entity extraction, regex, diff, plagiarism check. Words are our playground.

### 💻 System Operations (9 tools)
System info, process management, disk usage, memory, CPU, network interfaces, environment, uptime, file descriptors. Know thy machine.

### 🤖 AI Operations (10 tools)
Chat, embeddings, classification, extraction, OCR, speech-to-text, text-to-speech, summarization, QA, image tools. AI for days.

### 🖼️ Image Processing (17 tools)
Format conversion, resize, thumbnail, metadata, compress, crop, rotate, filters, grayscale, histogram, batch convert, watermark, collage, GIF creation, EXIF extraction, color analysis, image comparison. Pixels bend to our will.

### 🎵 Audio Processing (10 tools)
Format conversion, metadata, trim, merge, volume, silence removal, speed change, audio extraction, normalize, fade. Audio wizardry.

### 🎬 Video Processing (14 tools)
Format conversion, metadata, trim, merge, resize, frame extraction, video from frames, audio extraction, add audio, compress, speed change, thumbnail, video to GIF, subtitles. Video voodoo.

### 📄 PDF Processing (11 tools)
Merge, split, extract pages, extract text, extract images, add watermark, rotate, compress, PDF to images, get info. PDF domination.

### 📊 Data Processing (17 tools)
CSV read/write/convert/stats, JSON read/write/query/merge, YAML read/write/convert, XML read/convert, validate JSON/YAML, filter rows, sort data. Data wrangling at its finest.

---

## Advanced Shit That'll Blow Your Mind

### 🧠 Memory System
Multi-tier memory (working, short-term, long-term) with automatic compression, similarity search, and visualization. Never forget a goddamn thing.

### 🤖 Agent Framework
ReAct agents with reasoning traces, planning agents with task decomposition, multi-agent orchestration, and self-reflective agents that learn from their own bullshit mistakes.

### 📚 RAG System
Retrieval Augmented Generation with vector search, hybrid search (keyword + semantic), document ingestion, text chunking, and knowledge base management. Knowledge is power, baby.

### ⚡ Workflow Engine
DAG-based workflow execution with conditional branching, loops, parallel execution, retries, error handling, and a fluent builder API. Automate all the things.

### 🔌 Function Calling
Structured output with Pydantic models, function registry with OpenAI-compatible format, tool calling agent with automatic execution. Functions schemas for calculator, search, email, weather, calendar, and more.

### 📡 Streaming
Server-Sent Events (SSE) streaming, async streaming, token-by-token callbacks, stream parsing, chunk aggregation, OpenAI-compatible stream format. Real-time as fuck.

### 🛡️ Guardrails
Input validation with injection detection, PII redaction, toxicity filtering, output validation with hallucination detection, repetition checks, code injection prevention. Safety first, no exceptions.

### 💾 Caching
Multi-level caching (L1 memory, L2 disk, L3 semantic), semantic similarity cache, TTL-based eviction, cost savings tracking, Prometheus-compatible export. Cache like a champion.

### 📊 Monitoring
Real-time metrics collection (counters, gauges, histograms), request latency tracking, token usage monitoring, cost tracking, alert rules with webhooks, health checks, dashboards. Observability on steroids.

---

## CLI Commands That'll Make You Feel Powerful

```bash
# Start the damn thing
minxg

# Setup wizard — for newbies
minxg setup

# Check what tools we're packing
minxg tools

# Set your API key (don't lose it)
minxg key set sk-your-key-here

# Start the web UI (fancy pants)
minxg web

# Check your damn costs
minxg cost

# Compare models like a pro
minxg compare

# Memory dashboard
minxg memory

# Feature showcase
minxg features

# Theme switching
minxg themes

# Export/import memories
minxg export
minxg import

# Doctor diagnosis
minxg doctor

# API gateway
minxg gateway

# Extension management
minxg ext list

# Screen operations
minxg screen

# Update check
minxg update

# Skill management
minxg skill list

# Benchmark
minxg bench

# Replay session
minxg replay
```

---

## Installation — Get This Bad Boy Running

```bash
# The easy way
pip install minxg-beta

# The "I like pain" way
git clone https://github.com/pineapple-ooo/MINXG-Beta.git
cd MINXG-Beta
pip install -e .

# Verify it's not totally broken
minxg doctor
```

---

## MCP Server Setup — For the Cool Kids

### Claude Desktop
Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "minxg": {
      "command": "minxg",
      "args": ["gateway", "--mcp"]
    }
  }
}
```

### Cursor
```json
{
  "mcpServers": {
    "minxg": {
      "command": "minxg",
      "args": ["gateway", "--mcp"]
    }
  }
}
```

### Any MCP Client
```python
from minxg.mcp_server import WorkerRegistry

registry = WorkerRegistry()
print(f"Registered {len(registry.list_all())} tools. Take that, amateurs.")
```

---

## Stats That'll Make You Drool

- **429 Python files** — That's a lot of code, buddy
- **1,248 total files** — We don't play small
- **35 MB** — And growing like a monster
- **96 tests** — All passing, no BS
- **8 theme options** — Pick your poison
- **32+ AI providers** — More than you can shake a stick at
- **300+ math operators** — For the nerds
- **7 polyglot bridges** — C, Rust, Go, Java, Julia, R, WASM
- **12 languages supported** — We're worldly, damn it
- **5 platforms** — Linux, macOS, Windows, Android, Docker

---

## Contributing — Yeah, You Can Help

1. Fork this bad boy
2. Make your changes
3. Don't break the tests (or we'll find you)
4. Submit a PR
5. Profit (emotionally, not financially)

See [CONTRIBUTING.md](CONTRIBUTING.md) for the nitty-gritty.

---

## License

MIT. Do whatever the hell you want with it. Just don't blame us if your AI takes over the world.

---

## Final Words

MINXG isn't just a framework. It's a **statement**. A statement that says "we're not here to play nice, we're here to dominate."

500+ features. Zero apologies.

**Welcome to the big leagues, kid.**

---

*Built with rage, caffeine, and an unhealthy amount of determination.*  
*Version 0.18.3 (shitshow cleanup) — because someone had to clean up this mess.*

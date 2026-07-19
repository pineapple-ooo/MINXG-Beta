# MINXG MCP Server

[![PyPI version](https://img.shields.io/pypi/v/minxg-beta.svg)](https://pypi.org/project/minxg-beta/)
[![MCP](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Connect Claude Code, Cursor, and ChatGPT to 70+ AI workers — file I/O, network, crypto, math, and more.**

One command gives your AI agent superpowers:

```bash
pip install minxg-beta
```

## What is this?

MINXG is a modular AI worker platform. This repo exposes all workers as **MCP tools**, so any MCP-compatible AI client (Claude Code, Cursor, Windsurf, VS Code Copilot, ChatGPT) can call them directly.

No more copy-pasting results between tools. Your AI agent just *has* these capabilities built in.

## Quick Start

### 1. Install

```bash
pip install minxg-beta
```

### 2. Add to Claude Code

```bash
claude mcp add minxg -s user -- python -m minxg.mcp_server
```

### 3. Done. Start chatting.

```
Claude, read /etc/hosts and hash it with SHA-256
Claude, list all files in ~/projects and find Python files
Claude, make an HTTP request to api.example.com
```

## Available Tools

| Category | Tools |
|----------|-------|
| **File I/O** | read, write, tail, head, list, search, copy, move, delete |
| **Network** | HTTP GET/POST, DNS lookup, ping, port scan |
| **Crypto** | hash (MD5/SHA/AES), encrypt, decrypt, sign, verify |
| **Math** | 300+ operators: eval, matrix, stats, calculus, linear algebra |
| **Text** | format, template, markdown, regex, encoding |
| **Data** | CSV, JSON, compression, encoding conversion |
| **System** | process management, platform detection, shell exec |
| **AI** | LLM integration, RAG, embeddings |

## CLI Usage

```bash
# List all tools
python -m minxg.mcp_server list

# Call a tool directly
python -m minxg.mcp_server call fs_io read_file --path /etc/hosts

# Start MCP server (stdio)
python -m minxg.mcp_server

# Start MCP server (HTTP, for remote deployment)
MCP_TRANSPORT=http python -m minxg.mcp_server
```

## Claude Code Integration

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "minxg": {
      "command": "python",
      "args": ["-m", "minxg.mcp_server"]
    }
  }
}
```

Or use the CLI:

```bash
claude mcp add minxg -s user -- python -m minxg.mcp_server
```

## Cursor Integration

Add to `~/.cursor/mcp.json`:

```json
{
  "minxg": {
    "command": "python",
    "args": ["-m", "minxg.mcp_server"]
  }
}
```

## VS Code + GitHub Copilot

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": [
    {
      "name": "minxg",
      "command": "python",
      "args": ["-m", "minxg.mcp_server"]
    }
  ]
}
```

## Why MINXG?

| Feature | MINXG | Other MCP Servers |
|---------|-------|-------------------|
| **Workers** | 70+ | Usually 1-5 |
| **Categories** | 8 (file, network, crypto, math, text, data, system, AI) | 1-2 |
| **Platform** | Android + Windows + Linux | Usually desktop only |
| **Polyglot** | C/C++/Go/R/Julia/WASM bridges | Rare |
| **Self-evolution** | Built-in learning engine | None |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Client (Claude, etc.)                  │
└──────────────────────────┬──────────────────────────────────┘
                           │ MCP Protocol
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    MINXG MCP Server                          │
│  ┌─────────┬─────────┬─────────┬─────────┬─────────┐        │
│  │ File I/O│ Network │ Crypto  │  Math   │  Text   │        │
│  ├─────────┼─────────┼─────────┼─────────┼─────────┤        │
│  │  Data   │ System  │   AI    │Polyglot │  State  │        │
│  └─────────┴─────────┴─────────┴─────────┴─────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Examples

### Read and hash a file

```
Claude, read /etc/hosts and compute SHA-256
```

→ MINXG reads the file, hashes it, returns the digest.

### Network reconnaissance

```
Claude, ping google.com and do a DNS lookup
```

→ MINXG runs ping + nslookup, returns latency and IP.

### Math computation

```
Claude, calculate the eigenvalues of [[1,2],[3,4]]
```

→ MINXG's math worker computes and returns results.

### Multi-step workflow

```
Claude, find all Python files in ~/projects, read each one,
and count total lines of code
```

→ MINXG searches, reads, aggregates — all through MCP tools.

## Security

- Tools run with your user permissions (no sudo)
- File access is scoped to paths you allow
- Network tools respect your firewall
- Crypto operations are local (no data leaves your machine)

## Platform Support

| Platform | Status |
|----------|--------|
| Linux | ✅ Full |
| macOS | ✅ Full |
| Windows | ✅ Full |
| Android (Termux) | ✅ Full |
| WSL | ✅ Full |

## Development

```bash
git clone https://github.com/pineapple-ooo/MINXG-Beta.git
cd MINXG-Beta
pip install -e ".[dev]"
pytest tests/
```

## License

MIT — use it however you want.

## Stars History

[![Star History Chart](https://api.star-history.com/svg?repos=pineapple-ooo/MINXG-Beta&type=Date)](https://star-history.com/#pineapple-ooo/MINXG-Beta&Date)

---

**Built with ❤️ by the MINXG team.**

Questions? [Open an issue](https://github.com/pineapple-ooo/MINXG-Beta/issues).

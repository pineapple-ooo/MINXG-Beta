# MINXG Worker Skill

**Version:** 0.18.0  
**Category:** Productivity / Developer Tools  
**Author:** MINXG Authors

## Overview

MINXG is a modular AI worker platform with 70+ tools exposed via MCP. This skill teaches Claude Code how to use MINXG effectively.

## When to Use

Use MINXG when the task involves:
- File operations (read, write, search, copy, move, delete)
- Network operations (HTTP requests, DNS, ping, port scan)
- Cryptography (hash, encrypt, decrypt, sign, verify)
- Mathematical computation (300+ operators)
- Text processing (format, template, markdown, regex)
- Data handling (CSV, JSON, encoding, compression)
- System operations (process management, shell exec, platform detection)
- AI integration (LLM calls, RAG, embeddings)

## Available Workers

| Worker | Category | Key Tools |
|--------|----------|-----------|
| `fs_io` | File I/O | read_file, write_file, list_directory, tail_file, head_file |
| `fs_copy` | File I/O | copy_file, copy_dir, move_file, delete_file |
| `fs_search` | File I/O | search_files, grep, find |
| `network` | Network | http_get, http_post, dns_lookup, ping, port_scan |
| `crypto` | Crypto | hash, encrypt, decrypt, sign, verify |
| `math` | Math | safe_eval, matrix_ops, stats, calculus |
| `text` | Text | format, template, markdown, regex |
| `encoding` | Data | base64, url_encode, compression |
| `data` | Data | csv_parse, json_parse, yaml_parse |
| `system` | System | exec, process_list, platform_info |
| `ai` | AI | llm_call, rag_query, embed |

## Usage Pattern

### 1. Discover Tools

```
/minxg-list-tools
/minxg-list-tools crypto
```

### 2. Call Tools

```
/minxg-call fs_io read_file /etc/hosts
/minxg-call crypto hash --algorithm sha256 --data "hello world"
/minxg-call network http_get https://api.example.com/data
```

### 3. Chain Operations

MINXG tools can be chained for complex workflows:

```
1. Search for Python files: /minxg-call fs_search search_files ~/projects --pattern "*.py"
2. Read each file: /minxg-call fs_io read_file <path>
3. Process content: /minxg-call text format --input <content>
4. Save results: /minxg-call fs_io write_file output.txt --content <result>
```

## Best Practices

1. **Use the right worker**: Don't use `fs_io` for crypto operations.
2. **Batch when possible**: Use `list_directory` before individual file reads.
3. **Check errors**: All tools return `{status, result/error}`.
4. **Respect budgets**: Tools have call budgets (default 20 calls).
5. **Use categories**: Filter tools by category for faster discovery.

## Examples

### Example 1: File Analysis

```
User: Analyze all Python files in ~/projects
Claude: 
  1. /minxg-call fs_search search_files ~/projects --pattern "*.py"
  2. For each file: /minxg-call fs_io read_file <path>
  3. Count lines, find imports, summarize
```

### Example 2: Crypto Workflow

```
User: Hash this file with SHA-256
Claude:
  1. /minxg-call fs_io read_file secret.txt
  2. /minxg-call crypto hash --algorithm sha256 --data <content>
```

### Example 3: Network Recon

```
User: Check if example.com is up and get its IP
Claude:
  1. /minxg-call network ping example.com
  2. /minxg-call network dns_lookup example.com
```

## Setup

### Install MINXG

```bash
pip install minxg-beta
```

### Add MCP to Claude Code

```bash
claude mcp add minxg -s user -- python -m minxg.mcp_server
```

### Verify

```
/minxg-list-tools
```

Should return a list of 70+ tools.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Tools not showing up | Run `claude mcp list` to verify |
| Permission denied | Check file paths and user permissions |
| Import error | Run `pip install minxg-beta fastmcp` |
| Tool timeout | Increase timeout in tool params |

## License

MIT — use freely.

## Links

- [GitHub](https://github.com/pineapple-ooo/MINXG-Beta)
- [PyPI](https://pypi.org/project/minxg-beta/)
- [MCP Protocol](https://modelcontextprotocol.io)

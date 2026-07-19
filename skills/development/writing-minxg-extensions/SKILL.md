---
name: writing-minxg-extensions
description: How to write, register, and ship a MINXG extension (an executable Python plugin, distinct from a skill).
version: 1.0.0
author: minxg-core
tags: [development, extensions, python]
category: development
---

# Writing MINXG Extensions

An **extension** is executable Python code that adds a new tool the
chat agent can call — different from a **skill** (markdown
instructions with no code; see the `writing-minxg-skills` skill for
that). Use an extension when the agent needs a new *capability*, not
just new *knowledge*.

## When to use this

- You want to add a new tool the agent can invoke (e.g. wrapping a CLI,
  calling an API, doing structured file manipulation).
- A skill (plain instructions) isn't enough because the task needs real
  code — parsing, network calls, subprocess execution, etc.

## Steps

1. Create a single Python file, e.g. `my_tool.py`. It must define:
   - A schema dict (JSON Schema for the tool's arguments).
   - A handler function `def _handle_my_tool(args: dict) -> str:` that
     returns a JSON string.
   - A `check_fn() -> bool` the registry calls before exposing the tool
     (return `False` to hide it if a required dependency is missing).
   - A call to `registry.register(name=..., toolset=..., schema=...,
     handler=..., check_fn=..., emoji=..., max_result_size_chars=...)`
     at module import time — see `tools/*.py` in the MINXG source for
     real, working examples of this exact pattern.

2. Validate locally before installing:
   ```
   python -c "import ast; ast.parse(open('my_tool.py').read())"
   ```

3. Install it:
   ```
   minxg ext add ./my_tool.py
   minxg ext list        # confirm it shows up
   minxg doctor           # confirm active tool count went up
   ```

4. If something in your extension needs a secret/token, read it from
   an environment variable inside `check_fn()`/the handler — never
   hard-code credentials into the extension file itself.

## Notes / gotchas

- Extensions execute with the same permissions as the rest of MINXG.
  Only install extensions from sources you trust — there's no sandbox
  around them, by design (they need real system access to be useful).
- Keep the handler's return value under whatever
  `max_result_size_chars` you set — oversized tool results get
  truncated or rejected depending on the registry's cap policy.
- If you're building something that's mostly *instructions* with a
  little logic, consider whether a **skill** is actually the better
  fit — it ships as plain markdown and carries none of an extension's
  trust requirements.

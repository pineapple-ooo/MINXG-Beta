# MultiLingua Extension System

## CLI Extensions (ready to use)

Drop a `.py` file into `extensions/builtin/` or `extensions/user/` with three things:

```python
EXTENSION_NAME = "mycommand"
EXTENSION_DESCRIPTION = "What it does"

def register_cli(subparsers):
    """OPTIONAL: add argparse arguments."""
    p = subparsers.add_parser(EXTENSION_NAME, help=EXTENSION_DESCRIPTION)
    p.add_argument("--flag", action="store_true")

def handle_command(args) -> int:
    """REQUIRED: run the command, return exit code."""
    print("Hello from mycommand!")
    return 0
```

That's it. The CLI auto-discovers and registers it on startup.

Discovery priority: `builtin/ > user/`.  First wins on duplicate names.

Run `multiling --list-extensions` to see what's loaded.

See `builtin/hello.py` for the canonical example.

## Hook Registry (planned, not yet wired)

```python
from extensions import register_hook

def my_hook(msg):
    return f"[filtered] {msg}"

register_hook("pre_chat_hook", my_hook)
```

Hooks are silently loaded but not yet called in chat/gateway flows.

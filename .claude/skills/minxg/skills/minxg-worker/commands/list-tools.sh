#!/bin/bash
# MINXG: List all available tools
# Usage: /minxg-list-tools [category]

CATEGORY="${1:-}"

if [ -n "$CATEGORY" ]; then
    python -m minxg.mcp_server list --category "$CATEGORY"
else
    python -m minxg.mcp_server list
fi

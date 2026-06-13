"""
Browser search tool for AI agents.

Modes:
  - "user": Uses the user's system default browser
  - "api": Uses a custom AI search API endpoint

Usage:
    from minxg.web_search import search

    # Using system browser (user sees results)
    result = search("python tutorial", mode="user")

    # Using custom AI search API
    result = search("python tutorial", mode="api",
                    api_url="https://api.search.com/v1/search",
                    api_key="sk-xxx",
                    model="gpt-4")
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.parse
import webbrowser
from typing import Optional, Dict, Any


def _get_config() -> Dict[str, Any]:
    """Load browser_search config from config.yaml."""
    try:
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
                return config.get("browser_search", {})
    except Exception:
        pass
    return {}


def search(
    query: str,
    mode: Optional[str] = None,
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    num_results: int = 10,
) -> Dict[str, Any]:
    """
    Perform a web search.

    Args:
        query: Search query string
        mode: "user" (system browser) or "api" (AI search API)
        api_url: Custom API URL (required for "api" mode)
        api_key: API key for custom API
        model: Model name for API
        num_results: Number of results to return (API mode only)

    Returns:
        Dict with search results
    """
    config = _get_config()


    if mode is None:
        mode = config.get("api_type", "user")
    if mode == "api" and api_url is None:
        api_url = config.get("api_url", "")
    if mode == "api" and api_key is None:
        api_key = config.get("api_key", "")

    if not query or not query.strip():
        return {"error": "Query cannot be empty", "results": []}

    query = query.strip()

    if mode == "user":
        return _search_user_browser(query)
    elif mode == "api":
        if not api_url:
            return {"error": "API URL required for 'api' mode", "results": []}
        return _search_api(query, api_url, api_key, model, num_results)
    else:
        return {"error": f"Unknown mode: {mode}", "results": []}


def _search_user_browser(query: str) -> Dict[str, Any]:
    """Open search in user's system browser."""
    encoded = urllib.parse.quote_plus(query)

    search_url = f"https://www.google.com/search?q={encoded}"

    try:

        webbrowser.open(search_url)
        return {
            "mode": "user",
            "query": query,
            "url": search_url,
            "message": f"Opened in browser: {search_url}",
            "results": [],
        }
    except Exception as e:
        return {
            "mode": "user",
            "error": str(e),
            "results": [],
        }


def _search_api(
    query: str,
    api_url: str,
    api_key: str,
    model: Optional[str],
    num_results: int,
) -> Dict[str, Any]:
    """Search via custom AI search API."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "query": query,
        "num_results": num_results,
    }
    if model:
        payload["model"] = model

    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

            if isinstance(data, dict):
                results = data.get("results", data.get("data", []))
                return {
                    "mode": "api",
                    "query": query,
                    "results": results if isinstance(results, list) else [],
                    "metadata": {k: v for k, v in data.items() if k not in ("results", "data")},
                }
            else:
                return {"mode": "api", "query": query, "results": [], "error": "Invalid response"}

    except urllib.error.HTTPError as e:
        return {
            "mode": "api",
            "error": f"HTTP {e.code}: {e.reason}",
            "results": [],
        }
    except urllib.error.URLError as e:
        return {
            "mode": "api",
            "error": f"URL error: {e.reason}",
            "results": [],
        }
    except Exception as e:
        return {
            "mode": "api",
            "error": str(e),
            "results": [],
        }



if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MINXG Web Search")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--mode", choices=["user", "api"], default="user", help="Search mode")
    parser.add_argument("--api-url", help="Custom API URL")
    parser.add_argument("--api-key", help="API key")
    parser.add_argument("--model", help="Model name")
    parser.add_argument("-n", "--num-results", type=int, default=10, help="Number of results")

    args = parser.parse_args()

    result = search(
        query=args.query,
        mode=args.mode,
        api_url=args.api_url,
        api_key=args.api_key,
        model=args.model,
        num_results=args.num_results,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

"""CLI for minxg.cap — `python -m minxg.cap <query>`."""
from __future__ import annotations
import argparse
import json
import sys
from typing import List

from .registry import get_manifest


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(prog="minxg.cap",
        description="Corpus-based capability query and audit.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_provides = sub.add_parser("provides", help="Which paths provide a capability?")
    p_provides.add_argument("cap")

    p_requires = sub.add_parser("requires", help="Which paths require a capability?")
    p_requires.add_argument("cap")

    p_deps = sub.add_parser("deps", help="Transitive cap closure for a module path.")
    p_deps.add_argument("path")

    sub.add_parser("list", help="List all capabilities and their owners.")

    sub.add_parser("check", help="Audit the corpus for broken chains.")

    sub.add_parser("diff", help="Print current manifest as a snapshot dict (JSON).")

    args = parser.parse_args(argv)
    manifest = get_manifest()

    if args.cmd == "provides":
        providers = manifest.what_provides(args.cap)
        if not providers:
            print(f"no module provides: {args.cap}")
            return 1
        for path in providers:
            print(path)
        return 0

    if args.cmd == "requires":
        consumers = manifest.what_requires(args.cap)
        if not consumers:
            print(f"no module requires: {args.cap}")
            return 1
        for path in consumers:
            print(path)
        return 0

    if args.cmd == "deps":
        for cap in sorted(manifest.dependencies_of(args.path)):
            print(cap)
        return 0

    if args.cmd == "list":
        for cap in sorted(manifest.caps_provided()):
            owners = manifest.what_provides(cap)
            print(f"{cap}  ({len(owners)} module{'' if len(owners) == 1 else 's'})")
        return 0

    if args.cmd == "check":
        issues = manifest.check()
        if not issues:
            print("OK")
            return 0
        for issue in issues:
            print(f"[{issue.kind}] {issue.message}")
            for item in issue.detail:
                print(f"   {item}")
        return 1

    if args.cmd == "diff":
        json.dump(manifest.to_snapshot(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

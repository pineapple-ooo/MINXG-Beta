"""Manifest data structures for minxg.cap.

minxg.cap.provides: cap.types
minxg.cap.requires: (none)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


PROVIDE_TAG = "minxg.cap.provides"
REQUIRE_TAG = "minxg.cap.requires"


@dataclass
class CapModule:
    """A module's declared capability surface."""
    path: str
    provides: Tuple[str, ...] = ()
    requires: Tuple[str, ...] = ()


@dataclass
class CapChange:
    """A diff for a single module between two snapshots."""
    path: str
    added_provides: Tuple[str, ...] = ()
    removed_provides: Tuple[str, ...] = ()
    added_requires: Tuple[str, ...] = ()
    removed_requires: Tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (
            self.added_provides
            or self.removed_provides
            or self.added_requires
            or self.removed_requires
        )


@dataclass
class CapIssue:
    """A broken-cap-chain finding surfaced by `manifest.check()`."""
    kind: str
    message: str
    detail: Tuple[str, ...] = ()


@dataclass
class CapManifest:
    modules: Dict[str, CapModule] = field(default_factory=dict)

    def add(self, module: CapModule) -> None:
        self.modules[module.path] = module

    def remove(self, path: str) -> Optional[CapModule]:
        return self.modules.pop(path, None)

    def provides_for(self, path: str) -> Tuple[str, ...]:
        m = self.modules.get(path)
        return m.provides if m else ()

    def requires_for(self, path: str) -> Tuple[str, ...]:
        m = self.modules.get(path)
        return m.requires if m else ()

    def what_provides(self, cap: str) -> List[str]:
        out = [p for p, m in self.modules.items() if cap in m.provides]
        out.sort()
        return out

    def what_requires(self, cap: str) -> List[str]:
        out = [p for p, m in self.modules.items() if cap in m.requires]
        out.sort()
        return out

    def caps_provided(self) -> Set[str]:
        out: Set[str] = set()
        for m in self.modules.values():
            out.update(m.provides)
        return out

    def caps_required(self) -> Set[str]:
        out: Set[str] = set()
        for m in self.modules.values():
            out.update(m.requires)
        return out

    def dependencies_of(self, path: str) -> Set[str]:
        """Full transitive closure of caps consumed by `path`."""
        out: Set[str] = set()
        seen: Set[str] = set()
        stack = list(self.requires_for(path))
        while stack:
            cap = stack.pop()
            if cap in seen:
                continue
            seen.add(cap)
            out.add(cap)
            for owner in self.what_provides(cap):
                stack.extend(self.requires_for(owner))
        return out

    def check(self) -> List[CapIssue]:
        """Detect missing providers and unused caps."""
        issues: List[CapIssue] = []
        provided = self.caps_provided()
        needed = self.caps_required()
        missing = sorted(needed - provided)
        if missing:
            issues.append(CapIssue(
                kind="missing_provider",
                message=f"{len(missing)} capability has no producer in the tree",
                detail=tuple(missing),
            ))
        unused = sorted(provided - needed)
        if unused:
            issues.append(CapIssue(
                kind="unused_provider",
                message=f"{len(unused)} capability is produced but no module consumes it",
                detail=tuple(unused),
            ))
        # Per-module checks: any `requires: <cap>` line that has zero
        # providers must be flagged, in addition to the global
        # `missing_provider` report above.
        for path, module in self.modules.items():
            for cap in module.requires:
                providers = self.what_provides(cap)
                if not providers:
                    issues.append(CapIssue(
                        kind="unresolved_dep",
                        message=f"{path} requires {cap!r} but no module provides it",
                        detail=(path, cap),
                    ))
        return issues

    def to_snapshot(self) -> Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]]:
        return {
            p: (m.provides, m.requires) for p, m in sorted(self.modules.items())
        }

    def changes_since(self, baseline: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]]) -> List[CapChange]:
        out: List[CapChange] = []
        now = self.to_snapshot()
        for path in sorted(set(now.keys()) | set(baseline.keys())):
            old = baseline.get(path, ((), ()))
            new = now.get(path, ((), ()))
            old_p, old_r = old
            new_p, new_r = new
            change = CapChange(
                path=path,
                added_provides=tuple(sorted(set(new_p) - set(old_p))),
                removed_provides=tuple(sorted(set(old_p) - set(new_p))),
                added_requires=tuple(sorted(set(new_r) - set(old_r))),
                removed_requires=tuple(sorted(set(old_r) - set(new_r))),
            )
            if not change.is_empty:
                out.append(change)
        return out

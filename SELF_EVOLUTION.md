# SELF_EVOLUTION

> The 10 original algorithms of behavioral isomorphism.
> See [ARCHITECTURE.md](ARCHITECTURE.md) for how this fits in.

## The 10 algorithms

1. **ISG** — Interaction Structure Graph
   Dialogue → weighted directed graph. Nodes = semantic roles
   (PARAM, INTENT, SCOPE, MODE, CONSTRAINT, CONTEXT, SEQUENCE, MINIMAL).
   Edges = temporal/causal relations. Content-free.

2. **NCD** — Normalized Compression Distance
   NCD(x, y) = (C(xy) - min(C(x), C(y))) / max(C(x), C(y))
   C(x) = zstd-compressed byte length. Information-theoretic distance.
   Language-independent.

3. **SIG** — Spectral Invariant Signature
   Eigenvalues of the normalized Laplacian of the ISG adjacency matrix.
   Graph isomorphism invariant.

4. **SIC** — Structural Isomorphism Class
   NCD-based hierarchical clustering into structural isomorphism classes.

5. **BSP** — Behavioral Phase Space
   32-dim phase space. Each ISG maps to one point. Distance metric = NCD.

6. **BMO** — Behavioral Momentum
   Phase-space velocity vector. Predicts next behavior.

7. **TINV** — Topological Invariants
   Persistence homology (H₀, H₁) over the NCD-based filtration.

8. **SD** — Structural Drift
   Monitors class-centroid drift in phase space. Drift > 0.15/day
   triggers full phase-space reconfiguration.

9. **INV** — Behavioral Invariants
   Stable features within a class. Their violation signals genuine
   behavioral regime change.

10. **PVT** — Perturbation Validation (SANDBOXED, read-only)
    Small structural perturbations to validate class assignments.

## Why structural, not lexical?

| Approach | Question | Limitation |
|----------|----------|-----------|
| Pattern matching (regex) | Did the user say X? | Brittle, language-specific |
| Embedding similarity | Is the user's meaning similar to X? | Misses structural patterns |
| **Ours (NCD/ISG)** | **Does the user's interaction geometry match X?** | **Catches language-agnostic structure** |

**Example**:
```
User A: "show me weather" → "Beijing temp" → "Shanghai forecast"
  → ISG structure: [INTENT, PARAM, PARAM, SCOPE, SCOPE, SEQUENCE]
User B: "how's Tokyo weather" → "rain London today?"
  → Isomorphic ISG: [INTENT, PARAM, SCOPE, SEQUENCE]
  → NCD(A, B) is LOW — they're structurally similar
```

## Components

- `src/ai/memory/behavioral_isomorphism.py` — the 10 algorithms
- `src/ai/memory/entropic_evolution.py` — entropy-based detection
- `src/ai/memory/evolution_v2.py` — 25+ pattern categories
- `src/ai/memory/causal_graph.py` — PC Algorithm + Do-Calculus
- `src/ai/memory/topological.py` — Vietoris-Rips + persistent homology
- `src/ai/memory/tidal_lock_bridge.py` — C acceleration

## Usage

```python
from src.ai.memory.behavioral_isomorphism import (
    InteractionStructureGraph,
    normalized_compression_distance,
)
import zstandard as zstd

def ncd(a, b):
    coder = zstd.ZstdCompressor(level=3)
    c_xy = len(coder.compress((a + b).encode()))
    c_x = len(coder.compress(a.encode()))
    c_y = len(coder.compress(b.encode()))
    return (c_xy - min(c_x, c_y)) / max(c_x, c_y)

print(ncd("show me weather", "how's Tokyo weather"))
```

## Safety

- **Anti-loop guard** (`src/ai/safety/guard.py`) — progressive severity
- **PVT sandbox** — read-only perturbation validation
- **Drift detection** (SD) — flags regime change
- **Drift threshold** — 0.15/day max

## References

- `AGENTS.md` — system prompt for AI agents
- `SELF_EVOLUTION_ENGINE_GUIDE.md` (legacy docs)

"""
minxg/topo/mapper.py — Mapper Algorithm for Topological Simplification
==============================================================================

The MAPPER ALGORITHM (Singh, Mémoli, Carlsson 2007) is a topological
simplification of high-dimensional data. It works by:

  1. Filter the data with a real-valued function f: X → R
  2. Cover the range of f with overlapping intervals
  3. For each interval, take the preimage in X, cluster it
  4. Build a graph where nodes = clusters, edges = shared points

The result is a 1D "skeleton" that captures the essential shape.

MAPPER FOR AI
-------------
Mapper is used for:
  - Visualization of high-dimensional datasets
  - Topological feature extraction for ML
  - Understanding the topology of loss landscapes
  - Clustering with topological guarantees
""""
from __future__ import annotations
import math
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Set, Tuple


def cover(intervals: int, overlap: float = 0.5,
          f_min: float = 0.0, f_max: float = 1.0) -> List[Tuple[float, float]]:
    """Create a cover of [f_min, f_max] with `intervals` overlapping intervals.

    Args:
        intervals: number of intervals in the cover
        overlap: fraction of overlap between consecutive intervals
        f_min, f_max: range to cover

    Returns:
        List of (lo, hi) tuples.
    """"
    if intervals <= 0:
        return []
    width = (f_max - f_min) / (intervals * (1 - overlap) - overlap + 1)
    
    
    if abs(1 - overlap) < 1e-9:
        
        return [(f_min, f_max)]
    w = (f_max - f_min) / (intervals - (intervals - 1) * overlap)
    if w <= 0:
        return [(f_min, f_max)]
    step = w * (1 - overlap)
    out = []
    for i in range(intervals):
        lo = f_min + i * step
        hi = lo + w
        if hi > f_max: hi = f_max
        out.append((lo, hi))
    return out


def mapper_algorithm(points: List[List[float]],
                     filter_fn: Callable[[List[float]], float],
                     n_intervals: int = 10,
                     overlap: float = 0.3,
                     cluster_fn: Optional[Callable] = None,
                     cluster_eps: float = 0.1) -> Dict:
    """Run the Mapper algorithm on a point cloud.

    Args:
        points: list of points (each is a list of coordinates)
        filter_fn: a real-valued function f: X → R
        n_intervals: number of intervals in the cover
        overlap: overlap fraction between intervals
        cluster_fn: optional custom clustering function; default is single-link
        cluster_eps: distance threshold for clustering

    Returns:
        A dict with:
          - 'nodes': list of clusters (each a list of point indices)
          - 'edges': list of (node_i, node_j) pairs that share a point
          - 'cover': the cover used
          - 'graph': adjacency dict for the graph
    """"
    
    f_values = [filter_fn(p) for p in points]
    f_min, f_max = min(f_values), max(f_values)
    if f_max - f_min < 1e-12:
        f_max = f_min + 1.0

    
    intervals = cover(n_intervals, overlap, f_min, f_max)

    
    nodes: List[List[int]] = []  
    point_to_nodes: Dict[int, List[int]] = defaultdict(list)  
    for i, (lo, hi) in enumerate(intervals):
        
        preimage = [j for j, fv in enumerate(f_values) if lo <= fv <= hi]
        if not preimage:
            continue
        
        if cluster_fn is not None:
            clusters = cluster_fn(preimage, points, cluster_eps)
        else:
            clusters = _single_link_cluster(preimage, points, cluster_eps)
        for cluster in clusters:
            node_id = len(nodes)
            nodes.append(cluster)
            for p in cluster:
                point_to_nodes[p].append(node_id)

    
    edges: Set[Tuple[int, int]] = set()
    for p, node_ids in point_to_nodes.items():
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                a, b = node_ids[i], node_ids[j]
                if a > b: a, b = b, a
                edges.add((a, b))

    
    graph: Dict[int, List[int]] = defaultdict(list)
    for a, b in edges:
        graph[a].append(b)
        graph[b].append(a)

    return {
        'nodes': nodes,
        'edges': sorted(edges),
        'cover': intervals,
        'graph': dict(graph),
    }


def _single_link_cluster(point_ids: List[int], points: List[List[float]], eps: float):
    """Cluster points using single-linkage (union-find) clustering.""""
    n = len(point_ids)
    parent = list(range(n))
    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry: parent[rx] = ry
    eps_sq = eps * eps
    for i in range(n):
        for j in range(i + 1, n):
            pi = points[point_ids[i]]
            pj = points[point_ids[j]]
            d_sq = sum((a - b) ** 2 for a, b in zip(pi, pj))
            if d_sq <= eps_sq:
                union(i, j)
    
    groups: Dict[int, List[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(point_ids[i])
    return list(groups.values())

"""Operator graph primitives.

An OperatorNode is a labelled transformation. An OperatorEdge records
that one node's output feeds into another's input. The graph is
language-agnostic; back-ends map it to source-code emission.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class OperatorNode:
    op_id: str
    inputs: Tuple[str, ...] = ()
    output: str = "out"
    params: Dict[str, str] = field(default_factory=dict)
    language: str = "python"


@dataclass
class OperatorEdge:
    src_op: str
    dst_op: str
    binding: str = ""


@dataclass
class OperatorGraph:
    nodes: List[OperatorNode] = field(default_factory=list)
    edges: List[OperatorEdge] = field(default_factory=list)
    source_language: str = "python"

    def add_node(self, node: OperatorNode) -> OperatorNode:
        self.nodes.append(node)
        return node

    def add_edge(self, src: str, dst: str, binding: str = "") -> None:
        self.edges.append(OperatorEdge(src, dst, binding))

    def find_node(self, op_id: str) -> OperatorNode:
        for n in self.nodes:
            if n.op_id == op_id:
                return n
        raise KeyError(op_id)

    def topological_order(self) -> List[OperatorNode]:
        deps: Dict[str, List[str]] = {n.op_id: [] for n in self.nodes}
        rev: Dict[str, List[str]] = {n.op_id: [] for n in self.nodes}
        for e in self.edges:
            deps[e.dst_op].append(e.src_op)
            rev[e.src_op].append(e.dst_op)
        pending = {op: list(pred) for op, pred in deps.items()}
        order: List[OperatorNode] = []
        nodes_by_id = {n.op_id: n for n in self.nodes}
        cursor = 0
        while cursor < len(self.nodes):
            progressed = False
            for op_id, pred in list(pending.items()):
                if not pred and op_id in nodes_by_id:
                    order.append(nodes_by_id.pop(op_id))
                    del pending[op_id]
                    for child in rev[op_id]:
                        if child in pending:
                            pending[child].remove(op_id)
                    progressed = True
            if not progressed:
                break
            cursor = len(order)
        return order

    def __len__(self) -> int:
        return len(self.nodes)

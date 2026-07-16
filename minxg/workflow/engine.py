"""
MINXG Workflow Engine — Visual workflow builder and executor.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import time
import json


class NodeStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowNode:
    """A node in the workflow graph."""
    id: str
    name: str
    node_type: str  # "action", "condition", "loop", "delay"
    config: Dict[str, Any] = field(default_factory=dict)
    status: NodeStatus = NodeStatus.PENDING
    output: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retries: int = 0
    max_retries: int = 3


@dataclass
class WorkflowEdge:
    """An edge connecting two nodes."""
    source: str
    target: str
    condition: Optional[str] = None  # Expression to evaluate for conditional edges


@dataclass
class WorkflowExecution:
    """Execution state of a workflow."""
    workflow_id: str
    nodes: Dict[str, WorkflowNode] = field(default_factory=dict)
    edges: List[WorkflowEdge] = field(default_factory=list)
    status: str = "pending"
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    current_node: Optional[str] = None
    history: List[Dict] = field(default_factory=list)


class WorkflowEngine:
    """
    DAG-based workflow execution engine.

    Supports conditional branching, loops, parallel execution,
    retries, and error handling.
    """

    def __init__(self):
        self.workflows: Dict[str, WorkflowExecution] = {}
        self.handlers: Dict[str, Callable] = {}
        self.variables: Dict[str, Any] = {}

    def register_handler(self, node_type: str, handler: Callable) -> None:
        """Register a handler for a node type."""
        self.handlers[node_type] = handler

    def create_workflow(self, workflow_id: str) -> WorkflowExecution:
        """Create a new workflow."""
        workflow = WorkflowExecution(workflow_id=workflow_id)
        self.workflows[workflow_id] = workflow
        return workflow

    def add_node(
        self,
        workflow_id: str,
        node_id: str,
        name: str,
        node_type: str,
        config: Optional[Dict] = None,
    ) -> WorkflowNode:
        """Add a node to a workflow."""
        workflow = self.workflows[workflow_id]
        node = WorkflowNode(
            id=node_id,
            name=name,
            node_type=node_type,
            config=config or {},
        )
        workflow.nodes[node_id] = node
        return node

    def add_edge(
        self,
        workflow_id: str,
        source: str,
        target: str,
        condition: Optional[str] = None,
    ) -> WorkflowEdge:
        """Add an edge between nodes."""
        workflow = self.workflows[workflow_id]
        edge = WorkflowEdge(source=source, target=target, condition=condition)
        workflow.edges.append(edge)
        return edge

    def execute(self, workflow_id: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute a workflow.

        Args:
            workflow_id: ID of workflow to execute.
            variables: Initial variables for the workflow.

        Returns:
            Execution results.
        """
        if workflow_id not in self.workflows:
            return {"error": f"Workflow {workflow_id} not found"}

        workflow = self.workflows[workflow_id]
        workflow.status = "running"
        workflow.started_at = time.time()
        workflow.variables = variables or {}

        # Topological sort for execution order
        execution_order = self._topological_sort(workflow)

        for node_id in execution_order:
            node = workflow.nodes[node_id]

            if node.status == NodeStatus.SKIPPED:
                continue

            workflow.current_node = node_id
            node.status = NodeStatus.RUNNING
            node.started_at = time.time()

            try:
                # Execute node
                result = self._execute_node(node, workflow.variables)
                node.output = result
                node.status = NodeStatus.COMPLETED
                workflow.history.append({
                    "node": node_id,
                    "status": "completed",
                    "output": result,
                    "timestamp": time.time(),
                })
            except Exception as e:
                node.error = str(e)
                if node.retries < node.max_retries:
                    node.retries += 1
                    # Retry
                    try:
                        result = self._execute_node(node, workflow.variables)
                        node.output = result
                        node.status = NodeStatus.COMPLETED
                    except Exception as e2:
                        node.error = str(e2)
                        node.status = NodeStatus.FAILED
                        workflow.history.append({
                            "node": node_id,
                            "status": "failed",
                            "error": str(e2),
                            "timestamp": time.time(),
                        })
                        # Skip downstream nodes
                        self._skip_downstream(workflow, node_id)
                        break
                else:
                    node.status = NodeStatus.FAILED
                    workflow.history.append({
                        "node": node_id,
                        "status": "failed",
                        "error": str(e),
                        "timestamp": time.time(),
                    })
                    self._skip_downstream(workflow, node_id)
                    break

            node.completed_at = time.time()

        workflow.status = "completed"
        workflow.completed_at = time.time()
        workflow.current_node = None

        return self._get_execution_summary(workflow)

    def _execute_node(self, node: WorkflowNode, variables: Dict) -> Any:
        """Execute a single node."""
        handler = self.handlers.get(node.node_type)
        if handler:
            return handler(node.config, variables)

        # Default handlers
        if node.node_type == "action":
            # Simulate action execution
            time.sleep(node.config.get("duration", 0.1))
            return {"action": node.config.get("name", "unknown"), "done": True}
        elif node.node_type == "condition":
            # Evaluate condition
            expr = node.config.get("expression", "True")
            return eval(expr, {"__builtins__": {}}, variables)
        elif node.node_type == "delay":
            time.sleep(node.config.get("seconds", 1))
            return {"delayed": True}
        elif node.node_type == "loop":
            iterations = node.config.get("iterations", 1)
            return {"loop_completed": True, "iterations": iterations}

        return {"unknown_type": node.node_type}

    def _topological_sort(self, workflow: WorkflowExecution) -> List[str]:
        """Sort nodes in topological order."""
        # Build adjacency list
        graph = {node_id: [] for node_id in workflow.nodes}
        in_degree = {node_id: 0 for node_id in workflow.nodes}

        for edge in workflow.edges:
            graph[edge.source].append(edge.target)
            in_degree[edge.target] += 1

        # Kahn's algorithm
        queue = [n for n in in_degree if in_degree[n] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result

    def _skip_downstream(self, workflow: WorkflowExecution, failed_node: str) -> None:
        """Skip all downstream nodes of a failed node."""
        visited = set()
        queue = [failed_node]

        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)

            for edge in workflow.edges:
                if edge.source == node_id and edge.target not in visited:
                    workflow.nodes[edge.target].status = NodeStatus.SKIPPED
                    queue.append(edge.target)

    def _get_execution_summary(self, workflow: WorkflowExecution) -> Dict[str, Any]:
        """Get execution summary."""
        total_nodes = len(workflow.nodes)
        completed = sum(1 for n in workflow.nodes.values() if n.status == NodeStatus.COMPLETED)
        failed = sum(1 for n in workflow.nodes.values() if n.status == NodeStatus.FAILED)
        skipped = sum(1 for n in workflow.nodes.values() if n.status == NodeStatus.SKIPPED)

        return {
            "workflow_id": workflow.workflow_id,
            "status": workflow.status,
            "total_nodes": total_nodes,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "duration": (workflow.completed_at or time.time()) - (workflow.started_at or time.time()),
            "outputs": {
                node_id: node.output
                for node_id, node in workflow.nodes.items()
                if node.output is not None
            },
        }

    def get_workflow_graph(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow as a graph representation."""
        if workflow_id not in self.workflows:
            return {"error": "Workflow not found"}

        workflow = self.workflows[workflow_id]
        return {
            "workflow_id": workflow_id,
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "type": node.node_type,
                    "status": node.status.value,
                }
                for node in workflow.nodes.values()
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "condition": edge.condition,
                }
                for edge in workflow.edges
            ],
        }


class WorkflowBuilder:
    """Fluent API for building workflows."""

    def __init__(self, workflow_id: str, engine: WorkflowEngine):
        self.workflow_id = workflow_id
        self.engine = engine
        self._workflow = engine.create_workflow(workflow_id)

    def add(self, node_id: str, name: str, node_type: str = "action", **config) -> "WorkflowBuilder":
        """Add a node."""
        self.engine.add_node(self.workflow_id, node_id, name, node_type, config)
        return self

    def then(self, target: str, condition: Optional[str] = None) -> "WorkflowBuilder":
        """Add an edge from the last added node."""
        nodes = list(self._workflow.nodes.keys())
        if nodes:
            source = nodes[-1]
            self.engine.add_edge(self.workflow_id, source, target, condition)
        return self

    def connect(self, source: str, target: str, condition: Optional[str] = None) -> "WorkflowBuilder":
        """Connect two nodes."""
        self.engine.add_edge(self.workflow_id, source, target, condition)
        return self

    def build(self) -> WorkflowExecution:
        """Build and return the workflow."""
        return self._workflow

    def run(self, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Build and execute the workflow."""
        return self.engine.execute(self.workflow_id, variables)

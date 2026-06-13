"""
workflow.py — DAG 工作流引擎

提供有向无环图(DAG)驱动的任务编排能力：
  - 节点定义（任务/条件/并行分支/聚合）
  - 依赖关系管理
  - 拓扑排序执行
  - 并行执行支持
  - 失败重试与回滚
"""

import asyncio
import json
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque


class NodeType(Enum):
    TASK = "task"
    CONDITION = "condition"
    PARALLEL = "parallel"
    AGGREGATE = "aggregate"
    INPUT = "input"
    OUTPUT = "output"


class NodeStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


@dataclass
class Node:
    """工作流节点"""
    id: str = field(default_factory=lambda: f"node_{uuid.uuid4().hex[:8]}")
    name: str = ""
    node_type: NodeType = NodeType.TASK
    func: Optional[Callable] = None
    func_name: str = ""
    args: Dict = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    timeout: float = 300.0
    condition: Optional[Callable] = None
    condition_expr: str = ""
    weight: float = 1.0
    metadata: Dict = field(default_factory=dict)

    # 运行时状态
    status: NodeStatus = NodeStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    attempts: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "type": self.node_type.value,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "result_preview": str(self.result)[:200] if self.result else None,
            "error": self.error,
            "attempts": self.attempts,
        }


class DAG:
    """有向无环图结构"""

    def __init__(self, name: str = "workflow"):
        self.name = name
        self._nodes: Dict[str, Node] = {}
        self._adjacency: Dict[str, List[str]] = defaultdict(list)  # source -> [targets]
        self._reverse: Dict[str, List[str]] = defaultdict(list)    # target -> [sources]
        self._created_at = time.time()

    def add_node(self, node: Node) -> str:
        """添加节点"""
        self._nodes[node.id] = node
        return node.id

    def add_edge(self, source_id: str, target_id: str):
        """添加有向边 source -> target"""
        if source_id not in self._nodes:
            raise ValueError(f"Unknown source node: {source_id}")
        if target_id not in self._nodes:
            raise ValueError(f"Unknown target node: {target_id}")
        if target_id not in self._adjacency[source_id]:
            self._adjacency[source_id].append(target_id)
            self._reverse[target_id].append(source_id)
            # 更新节点的依赖
            if source_id not in self._nodes[target_id].depends_on:
                self._nodes[target_id].depends_on.append(source_id)

    def remove_node(self, node_id: str):
        """移除节点及其关联边"""
        if node_id in self._nodes:
            del self._nodes[node_id]
            # 清理边
            for targets in self._adjacency.values():
                if node_id in targets:
                    targets.remove(node_id)
            if node_id in self._adjacency:
                del self._adjacency[node_id]
            if node_id in self._reverse:
                del self._reverse[node_id]
            for sources in self._reverse.values():
                if node_id in sources:
                    sources.remove(node_id)

    def get_upstream(self, node_id: str) -> List[str]:
        """获取上游节点"""
        return self._reverse.get(node_id, [])

    def get_downstream(self, node_id: str) -> List[str]:
        """获取下游节点"""
        return self._adjacency.get(node_id, [])

    def topological_sort(self) -> List[str]:
        """拓扑排序（Kahn算法）"""
        in_degree = {nid: 0 for nid in self._nodes}
        for nid in self._nodes:
            for dep in self._reverse.get(nid, []):
                if dep in in_degree:
                    in_degree[nid] += 1

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        result = []

        while queue:
            node_id = queue.popleft()
            result.append(node_id)
            for neighbor in self._adjacency.get(node_id, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self._nodes):
            raise ValueError("DAG 包含环，无法拓扑排序")

        return result

    def validate(self) -> Tuple[bool, List[str]]:
        """验证 DAG 有效性（无环、依赖存在）"""
        errors = []
        try:
            self.topological_sort()
        except ValueError as e:
            errors.append(str(e))

        for nid, node in self._nodes.items():
            for dep in node.depends_on:
                if dep not in self._nodes:
                    errors.append(f"节点 {nid} 依赖不存在的节点 {dep}")

        return len(errors) == 0, errors

    def reset(self):
        """重置所有节点状态"""
        for node in self._nodes.values():
            node.status = NodeStatus.PENDING
            node.result = None
            node.error = None
            node.started_at = None
            node.finished_at = None
            node.attempts = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "nodes": {nid: n.to_dict() for nid, n in self._nodes.items()},
            "edges": [
                {"from": src, "to": tgt}
                for src, targets in self._adjacency.items()
                for tgt in targets
            ],
        }


class WorkflowEngine:
    """
    工作流引擎

    执行模式:
    - sequential: 严格按拓扑序串行执行
    - parallel: 无依赖节点并行执行
    - hybrid: 默认，并行执行但控制并发度
    """

    def __init__(self, max_workers: int = 4, retry_policy: Dict = None):
        self.max_workers = max_workers
        self.retry_policy = retry_policy or {
            "max_retries": 3,
            "backoff_base": 1.0,
            "backoff_max": 60.0,
        }
        self._dag: Optional[DAG] = None
        self._execution_log: List[Dict] = []
        self._context: Dict[str, Any] = {}

    def load_dag(self, dag: DAG):
        """加载 DAG"""
        self._dag = dag

    def set_context(self, key: str, value: Any):
        """设置执行上下文"""
        self._context[key] = value

    def get_context(self, key: str, default=None) -> Any:
        """获取执行上下文"""
        return self._context.get(key, default)

    async def run(self, mode: str = "hybrid") -> Dict:
        """
        执行工作流

        Returns:
            {status, results, errors, duration, stats}
        """
        if not self._dag:
            return {"status": "error", "error": "No DAG loaded"}

        is_valid, errors = self._dag.validate()
        if not is_valid:
            return {"status": "error", "errors": errors}

        self._dag.reset()
        self._execution_log.clear()
        start_time = time.time()

        if mode == "sequential":
            result = await self._run_sequential()
        elif mode == "parallel":
            result = await self._run_parallel()
        else:
            result = await self._run_hybrid()

        result["duration"] = round(time.time() - start_time, 3)
        result["stats"] = self._get_stats()
        return result

    async def _run_sequential(self) -> Dict:
        """串行执行"""
        order = self._dag.topological_sort()
        results = {}

        for node_id in order:
            node = self._dag._nodes[node_id]
            node.status = NodeStatus.RUNNING
            node.started_at = time.time()
            node.attempts += 1

            try:
                # 收集上游结果作为输入
                upstream_results = {
                    dep_id: self._dag._nodes[dep_id].result
                    for dep_id in self._dag.get_upstream(node_id)
                }
                node.args["_upstream"] = upstream_results
                node.args["_context"] = self._context

                if node.func:
                    result = node.func(**node.args)
                else:
                    result = {"status": "no_function", "node": node.name}

                node.result = result
                node.status = NodeStatus.SUCCESS
                results[node_id] = result
                self._log_execution(node, "success")

            except Exception as e:
                node.error = str(e)
                node.status = NodeStatus.FAILED
                results[node_id] = {"error": str(e)}
                self._log_execution(node, "failed")

                if not self._should_retry(node):
                    return {"status": "failed", "failed_at": node_id,
                            "error": str(e), "results": results}

        return {"status": "completed", "results": results}

    async def _run_parallel(self) -> Dict:
        """并行执行所有节点（需满足依赖）"""
        results = {}
        pending = set(self._dag._nodes.keys())
        completed = set()

        while pending:
            # 找出所有依赖已满足的节点
            ready = [
                nid for nid in pending
                if all(dep in completed
                       for dep in self._dag.get_upstream(nid))
            ]
            if not ready:
                break

            # 并行执行
            tasks = {
                nid: asyncio.create_task(self._execute_node(nid))
                for nid in ready
            }
            pending -= set(ready)

            done, _ = await asyncio.wait(
                tasks.values(), return_when=asyncio.ALL_COMPLETED
            )

            for nid, task in tasks.items():
                result = task.result()
                results[nid] = result
                if result.get("status") == "success":
                    completed.add(nid)

        failed = [nid for nid, r in results.items()
                  if r.get("status") != "success"]
        status = "completed" if not failed else "partial_failure"
        return {"status": status, "results": results}

    async def _run_hybrid(self) -> Dict:
        """混合执行（带并发控制）"""
        results = {}
        pending = set(self._dag._nodes.keys())
        completed = set()
        running = {}  # nid -> task

        semaphore = asyncio.Semaphore(self.max_workers)

        while pending or running:
            # 启动就绪任务
            ready = [
                nid for nid in pending
                if all(dep in completed
                       for dep in self._dag.get_upstream(nid))
                and nid not in running
            ]

            while ready and len(running) < self.max_workers:
                nid = ready.pop(0)
                running[nid] = asyncio.create_task(
                    self._execute_with_semaphore(nid, semaphore)
                )

            if not running:
                break

            # 等待任一完成
            done, pending_tasks = await asyncio.wait(
                running.values(), return_when=asyncio.FIRST_COMPLETED
            )

            # 更新状态
            new_running = {}
            for nid, task in running.items():
                if task in done:
                    result = task.result()
                    results[nid] = result
                    if result.get("status") == "success":
                        completed.add(nid)
                else:
                    new_running[nid] = task
            running = new_running

        failed = [nid for nid, r in results.items()
                  if r.get("status") != "success"]
        status = "completed" if not failed else "partial_failure"
        return {"status": status, "results": results}

    async def _execute_node(self, node_id: str) -> Dict:
        """执行单个节点"""
        node = self._dag._nodes[node_id]
        node.status = NodeStatus.RUNNING
        node.started_at = time.time()
        node.attempts += 1

        try:
            upstream_results = {
                dep_id: self._dag._nodes[dep_id].result
                for dep_id in self._dag.get_upstream(node_id)
            }
            node.args["_upstream"] = upstream_results
            node.args["_context"] = self._context

            if node.func:
                if asyncio.iscoroutinefunction(node.func):
                    result = await node.func(**node.args)
                else:
                    result = node.func(**node.args)
            else:
                result = {"status": "no_function", "node": node.name}

            node.result = result
            node.status = NodeStatus.SUCCESS
            node.finished_at = time.time()
            self._log_execution(node, "success")
            return {"status": "success", "result": result}

        except Exception as e:
            node.error = str(e)
            node.status = NodeStatus.FAILED
            node.finished_at = time.time()
            self._log_execution(node, "failed")

            if self._should_retry(node):
                node.status = NodeStatus.RETRYING
                return await self._execute_node(node_id)

            return {"status": "failed", "error": str(e)}

    async def _execute_with_semaphore(self, node_id: str,
                                      semaphore: asyncio.Semaphore) -> Dict:
        async with semaphore:
            return await self._execute_node(node_id)

    def _should_retry(self, node: Node) -> bool:
        """检查是否应该重试"""
        return (node.attempts < node.max_retries
                and node.attempts < self.retry_policy["max_retries"])

    def _log_execution(self, node: Node, status: str):
        """记录执行日志"""
        self._execution_log.append({
            "node_id": node.id, "node_name": node.name,
            "status": status,
            "attempt": node.attempts,
            "duration_ms": round(
                (node.finished_at or time.time() - node.started_at) * 1000, 2
            ) if node.started_at else 0,
            "timestamp": time.time(),
        })

    def _get_stats(self) -> Dict:
        """获取执行统计"""
        total = len(self._dag._nodes) if self._dag else 0
        success = sum(1 for n in self._dag._nodes.values()
                     if n.status == NodeStatus.SUCCESS)
        failed = sum(1 for n in self._dag._nodes.values()
                    if n.status == NodeStatus.FAILED)
        return {
            "total_nodes": total,
            "success": success,
            "failed": failed,
            "skipped": total - success - failed,
            "log_entries": len(self._execution_log),
        }

    def get_execution_log(self) -> List[Dict]:
        return self._execution_log.copy()


# ── 内置工作流模板 ─────────────────────────────────────────────────

class WorkflowTemplates:
    """内置工作流模板"""

    @staticmethod
    def etl_pipeline(source_func, transform_func, load_func) -> DAG:
        """ETL 数据管道模板"""
        dag = DAG("etl_pipeline")

        source = Node(
            name="extract", func=source_func,
            node_type=NodeType.TASK
        )
        transform = Node(
            name="transform", func=transform_func,
            node_type=NodeType.TASK
        )
        load = Node(
            name="load", func=load_func,
            node_type=NodeType.TASK
        )

        dag.add_node(source)
        dag.add_node(transform)
        dag.add_node(load)
        dag.add_edge(source.id, transform.id)
        dag.add_edge(transform.id, load.id)

        return dag

    @staticmethod
    def parallel_processing(tasks: List[Tuple[str, Callable]]) -> DAG:
        """并行处理模板"""
        dag = DAG("parallel_processing")

        aggregator = Node(
            name="aggregate", func=lambda **kw: {"collected": len(kw)},
            node_type=NodeType.AGGREGATE
        )
        dag.add_node(aggregator)

        for name, func in tasks:
            node = Node(name=name, func=func, node_type=NodeType.TASK)
            dag.add_node(node)
            dag.add_edge(node.id, aggregator.id)

        return dag

    @staticmethod
    def ml_pipeline(preprocess_func, train_func, evaluate_func,
                    deploy_func=None) -> DAG:
        """机器学习管道模板"""
        dag = DAG("ml_pipeline")

        nodes = {
            "preprocess": Node(name="preprocess", func=preprocess_func),
            "train": Node(name="train", func=train_func),
            "evaluate": Node(name="evaluate", func=evaluate_func),
        }

        for n in nodes.values():
            dag.add_node(n)

        dag.add_edge(nodes["preprocess"].id, nodes["train"].id)
        dag.add_edge(nodes["train"].id, nodes["evaluate"].id)

        if deploy_func:
            deploy = Node(name="deploy", func=deploy_func)
            dag.add_node(deploy)
            dag.add_edge(nodes["evaluate"].id, deploy.id)

        return dag

    @staticmethod
    def decision_tree(condition_func, true_func, false_func) -> DAG:
        """条件分支模板"""
        dag = DAG("decision_tree")

        condition = Node(
            name="condition", func=condition_func,
            node_type=NodeType.CONDITION
        )
        true_node = Node(
            name="true_branch", func=true_func,
            node_type=NodeType.TASK
        )
        false_node = Node(
            name="false_branch", func=false_func,
            node_type=NodeType.TASK
        )

        dag.add_node(condition)
        dag.add_node(true_node)
        dag.add_node(false_node)
        dag.add_edge(condition.id, true_node.id)
        dag.add_edge(condition.id, false_node.id)

        return dag
"""workflow_demo.py - MINXG 工作流引擎演示

展示工作流引擎的完整用法：
- DAG 创建与验证
- 并行执行
- 条件分支
- 错误处理与重试
""""

import asyncio
import sys
sys.path.insert(0, '/storage/emulated/0/multiling')


def demo_basic_workflow():
    """基础工作流演示""""
    print("\n--- 基础工作流演示 ---")

    from multiling.workflow import DAG, TaskNode, WorkflowEngine

    def fetch_users():
        print("  [fetch_users] 获取用户数据...")
        return {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}

    def process_users(data):
        print(f"  [process_users] 处理 {len(data['users'])} 个用户...")
        return [{"id": u["id"], "name": u["name"].upper()} for u in data["users"]]

    def store_results(data):
        print(f"  [store_results] 存储 {len(data)} 条记录...")
        return {"stored": len(data)}

    dag = DAG(name="user_etl")
    dag.add_node(TaskNode("fetch", fetch_users))
    dag.add_node(TaskNode("process", process_users))
    dag.add_node(TaskNode("store", store_results))
    dag.add_dependency("fetch", "process")
    dag.add_dependency("process", "store")


    errors = dag.validate()
    if errors:
        print(f"DAG 验证失败: {errors}")
        return

    print("DAG 结构验证通过")
    print(f"节点: {[n.name for n in dag.nodes]}")
    print(f"依赖: {[(s, d) for s, d in dag.edges]}")

    engine = WorkflowEngine()
    engine.register_dag(dag)

    print("\n执行工作流...")
    result = asyncio.run(engine.run("user_etl"))
    print(f"执行结果: {result}")


def demo_parallel_workflow():
    """并行执行演示""""
    print("\n--- 并行执行演示 ---")

    from multiling.workflow import DAG, TaskNode, WorkflowEngine

    def task_a():
        print("  [task_a] 开始执行")
        import time
        time.sleep(0.1)
        return {"result": "A"}

    def task_b():
        print("  [task_b] 开始执行")
        import time
        time.sleep(0.1)
        return {"result": "B"}

    def task_c():
        print("  [task_c] 开始执行")
        return {"result": "C"}

    def merge(results_a, results_b, results_c):
        print(f"  [merge] 合并结果: {results_a}, {results_b}, {results_c}")
        return {"merged": True}

    dag = DAG(name="parallel_demo", max_concurrency=3)

    dag.add_node(TaskNode("task_a", task_a))
    dag.add_node(TaskNode("task_b", task_b))
    dag.add_node(TaskNode("task_c", task_c))
    dag.add_node(TaskNode("merge", merge))

    dag.add_dependency("task_a", "merge")
    dag.add_dependency("task_b", "merge")
    dag.add_dependency("task_c", "merge")

    engine = WorkflowEngine()
    engine.register_dag(dag)

    print("执行并行工作流 (task_a, task_b, task_c 并行执行)...")
    result = asyncio.run(engine.run("parallel_demo"))
    print(f"结果: {result}")


def demo_retry_workflow():
    """失败重试演示""""
    print("\n--- 失败重试演示 ---")

    from multiling.workflow import DAG, TaskNode, WorkflowEngine

    attempt_count = 0

    def unstable_task():
        nonlocal attempt_count
        attempt_count += 1
        print(f"  [unstable_task] 第 {attempt_count} 次尝试")
        if attempt_count < 3:
            raise RuntimeError("模拟失败")
        return {"success": True}

    dag = DAG(name="retry_demo")
    dag.add_node(TaskNode(
        "unstable",
        unstable_task,
        max_retries=5,
        retry_delay=0.1,
        retry_backoff=True,
    ))

    engine = WorkflowEngine()
    engine.register_dag(dag)

    print("执行会失败两次然后成功的工作流...")
    result = asyncio.run(engine.run("retry_demo"))
    print(f"最终结果: {result}")
    print(f"总尝试次数: {attempt_count}")


def demo_conditional_workflow():
    """条件分支演示""""
    print("\n--- 条件分支演示 ---")

    from multiling.workflow import DAG, TaskNode, WorkflowEngine

    def check_data():
        return {"type": "premium", "value": 100}

    def premium_handler(data):
        print(f"  [premium_handler] 处理高级数据: {data}")
        return {"plan": "premium"}

    def basic_handler(data):
        print(f"  [basic_handler] 处理基础数据: {data}")
        return {"plan": "basic"}

    dag = DAG(name="conditional_demo")

    dag.add_node(TaskNode("check", check_data))
    dag.add_node(TaskNode("premium", premium_handler))
    dag.add_node(TaskNode("basic", basic_handler))

    dag.add_condition("check", "premium", lambda r: r.get("type") == "premium")
    dag.add_condition("check", "basic", lambda r: r.get("type") != "premium")

    engine = WorkflowEngine()
    engine.register_dag(dag)

    print("执行条件分支工作流...")
    result = asyncio.run(engine.run("conditional_demo"))
    print(f"结果: {result}")


def demo_error_handling():
    """错误处理演示""""
    print("\n--- 错误处理演示 ---")

    from multiling.workflow import DAG, TaskNode, WorkflowEngine, FailureStrategy

    def failing_task():
        raise ValueError("预期错误")

    def fallback_task():
        print("  [fallback_task] 执行降级处理")
        return {"fallback": True}

    dag = DAG(
        name="error_handling_demo",
        failure_strategy=FailureStrategy.CONTINUE,
    )

    def on_error(node_name, error):
        print(f"  [错误回调] 节点 {node_name} 出错: {error}")

    dag.add_error_handler(on_error)
    dag.add_node(TaskNode("failing", failing_task, max_retries=1))
    dag.add_node(TaskNode("fallback", fallback_task))
    dag.add_dependency("failing", "fallback")

    engine = WorkflowEngine()
    engine.register_dag(dag)

    print("执行带错误处理的工作流...")
    result = asyncio.run(engine.run("error_handling_demo"))
    print(f"工作流继续执行: {result}")


def demo_complex_pipeline():
    """复杂数据处理管道""""
    print("\n--- 复杂数据处理管道 ---")

    from multiling.workflow import DAG, TaskNode, WorkflowEngine
    from multiling.pipeline import Pipeline, Stage
    from multiling.vector import VectorStore
    from multiling.analytics import MetricsCollector

    metrics = MetricsCollector(prefix="workflow_demo")

    def fetch_raw_data():
        metrics.counter("data.fetch")
        return [
            {"id": 1, "text": "Python 是编程语言", "valid": True},
            {"id": 2, "text": "", "valid": False},
            {"id": 3, "text": "AI 很热门", "valid": True},
        ]

    def clean_data(raw):
        metrics.counter("data.clean")
        return [r for r in raw if r.get("valid")]

    def embed_data(clean):
        metrics.timer("data.embed", 50.0)
        import random
        return [
            {**r, "embedding": [random.random() for _ in range(4)]}
            for r in clean
        ]

    def store_embeddings(embedded):
        metrics.counter("data.store")
        store = VectorStore(dimension=4)
        for item in embedded:
            store.add_vector(item["embedding"], f"doc_{item['id']}")
        return {"stored": store.size()}

    dag = DAG(name="complex_pipeline")
    dag.add_node(TaskNode("fetch", fetch_raw_data))
    dag.add_node(TaskNode("clean", clean_data))
    dag.add_node(TaskNode("embed", embed_data))
    dag.add_node(TaskNode("store", store_embeddings))

    dag.add_dependency("fetch", "clean")
    dag.add_dependency("clean", "embed")
    dag.add_dependency("embed", "store")

    engine = WorkflowEngine()
    engine.register_dag(dag)

    print("执行复杂管道工作流...")
    result = asyncio.run(engine.run("complex_pipeline"))
    print(f"结果: {result}")

    snapshot = metrics.snapshot()
    print(f"监控指标: {snapshot['counters']}")


if __name__ == "__main__":
    print("=" * 60)
    print("MINXG 工作流引擎演示")
    print("=" * 60)

    demo_basic_workflow()
    demo_parallel_workflow()
    demo_retry_workflow()
    demo_conditional_workflow()
    demo_error_handling()
    demo_complex_pipeline()

    print("\n" + "=" * 60)
    print("工作流演示完成！")
    print("=" * 60)
"""basic_usage.py - MINXG 基本使用示例

本示例展示 MINXG 的核心功能：
- 配置管理
- 智能体创建与对话
- 知识图谱操作
- 向量存储与检索
- 工作流编排
- 事件总线
- 任务调度
- 性能分析
"""

import asyncio
import sys
sys.path.insert(0, '/storage/emulated/0/multiling')


def demo_config():
    """配置管理示例"""
    print("\n" + "=" * 50)
    print("1. 配置管理示例")
    print("=" * 50)

    from multiling.config import Config, create_default_config, Validator


    config = create_default_config()
    print(f"默认服务器端口: {config.server.port}")
    print(f"默认缓存后端: {config.cache.backend}")


    config_path = '/storage/emulated/0/multiling/config.yaml'
    import os
    if os.path.exists(config_path):
        config.load_yaml(config_path)


    config.set("server.debug", True)
    print(f"调试模式: {config.server.debug}")


    errors = config.validate()
    if errors:
        print(f"配置错误: {errors}")
    else:
        print("配置验证通过")

    return config


def demo_knowledge_graph():
    """知识图谱示例"""
    print("\n" + "=" * 50)
    print("2. 知识图谱示例")
    print("=" * 50)

    from multiling.knowledge import KnowledgeGraph, Entity

    kg = KnowledgeGraph()


    kg.add_entity(Entity("Python", entity_type="编程语言"))
    kg.add_entity(Entity("Guido van Rossum", entity_type="人物"))
    kg.add_entity(Entity("人工智能", entity_type="领域"))
    kg.add_entity(Entity("深度学习", entity_type="技术"))


    kg.add_relation("Python", "发明者", "Guido van Rossum")
    kg.add_relation("Python", "应用领域", "人工智能")
    kg.add_relation("人工智能", "子领域", "深度学习")
    kg.add_relation("Guido van Rossum", "国籍", "荷兰")


    print("Python 的关系:")
    for rel in kg.query_relations("Python"):
        print(f"  {rel[0]} -> {rel[1]}")


    print("\n从 Guido van Rossum 到 深度学习 的路径:")
    paths = kg.query_path("Guido van Rossum", "深度学习")
    for path in paths:
        print(f"  {' -> '.join(path)}")


    print(f"\n搜索 'pyth': {kg.search_entities('pyth')}")


    kg.export_json('/tmp/kg_demo.json')
    print("知识图谱已导出到 /tmp/kg_demo.json")


def demo_vector_store():
    """向量存储示例"""
    print("\n" + "=" * 50)
    print("3. 向量存储示例")
    print("=" * 50)

    import numpy as np
    from multiling.vector import VectorStore

    store = VectorStore(dimension=4)


    np.random.seed(42)
    docs = [
        ("doc1", "Python 是一种编程语言"),
        ("doc2", "Java 也是一种编程语言"),
        ("doc3", "机器学习是人工智能的分支"),
        ("doc4", "深度学习使用神经网络"),
    ]

    for doc_id, text in docs:
        vector = np.random.randn(4)
        store.add_vector(vector.tolist(), doc_id)
        print(f"  添加: {doc_id} - {text}")


    query = np.random.randn(4)
    results = store.search_by_vector(query.tolist(), top_k=2)
    print(f"\n查询结果 (top 2):")
    for doc_id, score in results:
        print(f"  {doc_id}: 相似度 {score:.4f}")

    print(f"\n存储中文档数量: {store.size()}")


def demo_workflow():
    """工作流示例"""
    print("\n" + "=" * 50)
    print("4. 工作流示例")
    print("=" * 50)

    from multiling.workflow import DAG, TaskNode, WorkflowEngine

    def fetch_data():
        return {"items": [1, 2, 3, 4, 5]}

    def process_data(data):
        return [x * 2 for x in data["items"]]

    def save_result(result):
        print(f"  保存结果: {result}")
        return {"saved": len(result)}


    dag = DAG(name="demo_etl")
    dag.add_node(TaskNode("fetch", fetch_data))
    dag.add_node(TaskNode("process", process_data))
    dag.add_node(TaskNode("save", save_data := save_result))
    dag.add_dependency("fetch", "process")
    dag.add_dependency("process", "save")


    errors = dag.validate()
    if errors:
        print(f"DAG 验证失败: {errors}")
        return


    engine = WorkflowEngine()
    engine.register_dag(dag)

    print("执行工作流...")
    result = asyncio.run(engine.run("demo_etl"))
    print(f"工作流结果: {result}")


def demo_event_bus():
    """事件总线示例"""
    print("\n" + "=" * 50)
    print("5. 事件总线示例")
    print("=" * 50)

    from multiling.queue import EventBus

    bus = EventBus()


    received = []

    def on_message(channel, payload, headers):
        received.append(payload)
        print(f"  收到消息: {payload}")

    bus.subscribe("user.login", on_message)


    print("发布事件...")
    bus.publish("user.login", {"user": "Alice", "time": "10:00"})
    bus.publish("user.login", {"user": "Bob", "time": "10:01"})

    print(f"共收到 {len(received)} 条消息")
    stats = bus.get_stats()
    print(f"事件总线统计: {stats}")


def demo_task_queue():
    """任务队列示例"""
    print("\n" + "=" * 50)
    print("6. 任务队列示例")
    print("=" * 50)

    from multiling.queue import TaskQueue

    results = []

    async def process_task(payload, message):
        results.append(payload)
        return {"processed": payload}

    queue = TaskQueue(name="demo_queue", max_workers=2)
    queue.set_handler(process_task)

    async def run():
        await queue.start()
        for i in range(5):
            await queue.enqueue({"task_id": i, "data": f"item_{i}"})
        await asyncio.sleep(1)
        await queue.stop()
        print(f"处理了 {len(results)} 个任务")
        print(f"队列统计: {queue.get_stats()}")

    asyncio.run(run())


def demo_cache():
    """缓存示例"""
    print("\n" + "=" * 50)
    print("7. 缓存示例")
    print("=" * 50)

    from multiling.cache import MemoryCache, LayeredCache


    cache = MemoryCache(max_size=10, default_ttl=60)
    cache.set("key1", "value1")
    cache.set("key2", "value2", tags=["important"])

    print(f"key1 = {cache.get('key1')}")
    print(f"key2 存在: {cache.has('key2')}")
    print(f"按标签查询: {cache.get_by_tag('important')}")
    print(f"缓存统计: {cache.get_stats()}")


    layered = LayeredCache(name="demo", memory_max=100, disk_path="/tmp/cache_demo")
    layered.set("user:1", {"name": "Alice", "age": 25})
    result = layered.get("user:1")
    print(f"\n多层缓存获取: {result}")


def demo_scheduler():
    """任务调度示例"""
    print("\n" + "=" * 50)
    print("8. 任务调度示例")
    print("=" * 50)

    from multiling.scheduler import TaskScheduler

    executed = []

    def my_task():
        executed.append(time.time())
        print(f"  任务执行于 {time.time():.2f}")

    scheduler = TaskScheduler("demo")
    job_id = scheduler.schedule_interval(my_task, seconds=1, name="demo_task")

    print(f"已创建任务: {job_id}")
    print(f"任务列表: {scheduler.list_jobs()}")


def demo_profiler():
    """性能分析示例"""
    print("\n" + "=" * 50)
    print("9. 性能分析示例")
    print("=" * 50)

    from multiling.profiler import CodeProfiler, TimingProfiler
    import time


    profiler = CodeProfiler()
    profiler.start()
    time.sleep(0.01)
    profiler.stop()
    print(profiler.get_report(limit=10))


    timer = TimingProfiler()

    with timer.span("test_operation"):
        time.sleep(0.005)

    print("\n计时统计:")
    stats = timer.get_stats()
    for label, data in stats.items():
        if data.get("count", 0) > 0:
            print(f"  {label}: mean={data['mean_ms']:.3f}ms")


def demo_analytics():
    """监控分析示例"""
    print("\n" + "=" * 50)
    print("10. 监控分析示例")
    print("=" * 50)

    from multiling.analytics import MetricsCollector, AnalyticsEngine, HealthMonitor


    metrics = MetricsCollector(prefix="demo")
    metrics.counter("requests", tags={"endpoint": "/api"})
    metrics.counter("requests", tags={"endpoint": "/api"})
    metrics.gauge("active_users", 42)
    metrics.histogram("response_time", 150.0)
    metrics.histogram("response_time", 200.0)

    print(f"指标键: {metrics.get_all_keys()}")
    print(f"快照: {metrics.snapshot()}")


    engine = AnalyticsEngine(metrics)
    engine.set_threshold("response_time", "gt", 100, severity="warning")
    result = engine.analyze()
    if result["alerts"]:
        print(f"告警: {result['alerts']}")


    monitor = HealthMonitor()
    monitor.register_check("demo_check", lambda: "OK", interval_sec=60)
    result = monitor.run_all()
    print(f"健康检查: {result}")


if __name__ == "__main__":
    print("=" * 60)
    print("MINXG 基本使用示例")
    print("=" * 60)

    demo_config()
    demo_knowledge_graph()
    demo_vector_store()
    demo_workflow()
    demo_event_bus()
    demo_task_queue()
    demo_cache()
    demo_scheduler()
    demo_profiler()
    demo_analytics()

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)
"""custom_tool.py - 自定义工具与系统集成示例

展示如何：
- 创建和注册自定义工具
- 使用认证授权系统
- 组合多个模块构建完整应用
""""

import sys
sys.path.insert(0, '/storage/emulated/0/multiling')


def demo_custom_tools():
    """自定义工具演示""""
    print("\n--- 自定义工具演示 ---")

    from multiling.toolsets import ToolSet, tool

    tools = ToolSet("demo_tools")

    @tool("calculator", description="执行数学计算")
    def calculator(expression: str) -> dict:
        """计算数学表达式

        Args:
            expression: 数学表达式字符串

        Returns:
            包含结果的字典
        """"
        try:

            import re
            if not re.match(r'^[\d\s\+\-\*\/\(\)\.]+$', expression):
                return {"error": "无效的表达式"}
            result = eval(expression)
            return {"result": result, "expression": expression}
        except Exception as e:
            return {"error": str(e)}

    @tool("greeting", description="生成问候语")
    def greeting(name: str, language: str = "zh") -> str:
        """生成个性化问候

        Args:
            name: 用户名
            language: 语言 (zh/en)

        Returns:
            问候语字符串
        """"
        greetings = {
            "zh": f"你好，{name}！欢迎使用 MINXG。",
            "en": f"Hello, {name}! Welcome to MINXG.",
        }
        return greetings.get(language, greetings["zh"])


    result1 = tools.call("calculator", {"expression": "2 + 3 * 4"})
    print(f"  计算结果: {result1}")

    result2 = tools.call("greeting", {"name": "Alice", "language": "zh"})
    print(f"  问候: {result2}")


    print(f"\n  已注册工具: {tools.list_tools()}")


def demo_auth_system():
    """认证授权系统演示""""
    print("\n--- 认证授权系统演示 ---")

    from multiling.auth import (
        AuthManager, Authorizer, SessionAuth,
        Permission, Role, create_default_roles,
    )


    auth_manager = AuthManager(secret_key="demo-secret-key-for-testing")
    authorizer = Authorizer()


    roles = create_default_roles()
    for role in roles.values():
        authorizer.add_role(role)


    token = auth_manager.login("admin", "demo-password")
    print(f"  Token 生成: {token[:30]}...")


    user = auth_manager.validate_token(token)
    print(f"  Token 验证: {user}")


    perm = Permission("data", "read", "team")
    has_perm = authorizer.check_permission("admin", perm)
    print(f"  admin 有 data:read 权限: {has_perm}")


    session_auth = SessionAuth(auth_manager)
    session_id = session_auth.create_session("admin")
    print(f"  会话创建: {session_id[:16]}...")

    session = session_auth.validate_session(session_id)
    print(f"  会话验证: {session['user_id']}")


    session_auth.invalidate_session(session_id)
    print("  会话已销毁")


def demo_cache_system():
    """缓存系统演示""""
    print("\n--- 缓存系统演示 ---")

    from multiling.cache import MemoryCache, LayeredCache


    cache = MemoryCache(max_size=100, default_ttl=60)


    for i in range(5):
        cache.set(f"key:{i}", {"data": f"value_{i}"}, tags=[f"group_{i % 2}"])


    print(f"  key:0 = {cache.get('key:0')}")
    print(f"  key:99 (不存在) = {cache.get('key:99', 'NOT_FOUND')}")


    stats = cache.get_stats()
    print(f"  缓存统计: hits={stats['hits']}, misses={stats['misses']}, size={stats['size']}")


    group0 = cache.get_by_tag("group_0")
    print(f"  group_0 条目数: {len(group0)}")


def demo_full_integration():
    """完整集成演示 - 组合多个模块""""
    print("\n--- 完整集成演示 ---")

    from multiling.config import create_default_config
    from multiling.analytics import MetricsCollector, AnalyticsEngine, HealthMonitor
    from multiling.cache import MemoryCache
    from multiling.queue import EventBus
    from multiling.scheduler import TaskScheduler

    print("  初始化各模块...")


    config = create_default_config()
    config.set("server.debug", True)


    metrics = MetricsCollector(prefix="integration")
    metrics.counter("startup")


    health = HealthMonitor()
    health.register_check("config", lambda: "OK")
    health.register_check("cache", lambda: "OK")


    bus = EventBus()
    events_received = []

    def log_event(channel, payload, headers):
        events_received.append(payload)

    bus.subscribe("system.startup", log_event)


    scheduler = TaskScheduler("integration")

    print("  各模块初始化完成")
    print(f"  - 配置: debug={config.server.debug}")
    print(f"  - 指标: {metrics.snapshot()['counters']}")
    print(f"  - 健康: {health.run_all()}")
    print(f"  - 事件: 订阅者数量={bus.get_stats()['subscriber_count']}")


    metrics.counter("request", tags={"path": "/api/test"})
    metrics.gauge("memory_mb", 128.5)
    bus.publish("system.startup", {"status": "ready"})

    print(f"  - 运行后指标: {metrics.snapshot()['counters']}")
    print(f"  - 收到的事件: {events_received}")


if __name__ == "__main__":
    print("=" * 60)
    print("MINXG 自定义工具与系统集成演示")
    print("=" * 60)

    demo_custom_tools()
    demo_auth_system()
    demo_cache_system()
    demo_full_integration()

    print("\n" + "=" * 60)
    print("自定义工具演示完成！")
    print("=" * 60)
"""agent_demo.py - MINXG Agent 框架演示

展示智能体框架的完整用法：
- 创建具有角色和能力的智能体
- 多智能体协作会话
- 自我反思引擎
""""

import sys
sys.path.insert(0, '/storage/emulated/0/multiling')


def demo_single_agent():
    """单个智能体演示""""
    print("\n--- 单智能体演示 ---")

    from multiling.agent.agent import Agent, AgentConfig

    config = AgentConfig(
        name="code_reviewer",
        role="代码审查专家",
        system_prompt="你是一个经验丰富的代码审查专家，擅长发现代码中的 bug 和改进点。",
        max_history=10,
        temperature=0.3,
    )

    agent = Agent(config)

    code = '''
def fibonacci(n):
    if n <= 0:
        return []
    if n == 1:
        return [0]
    result = [0, 1]
    for i in range(2, n):
        result.append(result[-1] + result[-2])
    return result
''''

    result = agent.step(f"审查以下 Python 代码并指出问题：\n{code}")
    print(f"智能体回复: {result.response[:200]}...")


def demo_multi_agent_session():
    """多智能体会话演示""""
    print("\n--- 多智能体会话演示 ---")

    from multiling.agent.agent import Agent, AgentConfig
    from multiling.agent.session import SessionManager

    session_mgr = SessionManager()
    session = session_mgr.create_session("code_review_team")


    coder = Agent(AgentConfig(
        name="coder", role="开发者",
        system_prompt="你是一个 Python 开发者，负责编写功能代码。",
        temperature=0.7,
    ))

    reviewer = Agent(AgentConfig(
        name="reviewer", role="审查者",
        system_prompt="你是一个严格的代码审查者，专注于代码质量和最佳实践。",
        temperature=0.3,
    ))

    session.add_agent("coder", coder)
    session.add_agent("reviewer", reviewer)


    session.add_route("coder", "reviewer", message_type="code")
    session.add_route("reviewer", "coder", message_type="feedback")


    session.send("coder", "我刚写了一个排序函数，请审查")
    print("  [coder -> reviewer] 发送代码审查请求")

    session.send("reviewer", "代码已审查，有几点建议...")
    print("  [reviewer -> coder] 返回审查意见")

    print("  会话中的智能体:", list(session.agents.keys()))


def demo_role_system():
    """角色系统演示""""
    print("\n--- 角色系统演示 ---")

    from multiling.agent.role import RoleRegistry, Role
    from multiling.auth import Permission


    print("预设角色:")
    for name in ["admin", "developer", "viewer"]:
        role = RoleRegistry.get(name)
        if role:
            perms = [p.resource + ":" + p.action for p in role.permissions]
            print(f"  {name}: {perms[:3]}...")


    ml_engineer = Role(
        name="ml_engineer",
        description="机器学习工程师",
        permissions={
            Permission("model", "train", "own"),
            Permission("model", "deploy", "team"),
            Permission("data", "read", "team"),
        },
        inherits=["viewer"],
    )
    RoleRegistry.register(ml_engineer)
    print(f"\n已注册新角色: ml_engineer")


def demo_capability_system():
    """能力系统演示""""
    print("\n--- 能力系统演示 ---")

    from multiling.agent.capability import CapabilityRegistry, Capability

    @CapabilityRegistry.register("math_solver")
    class MathSolverCapability(Capability):
        """数学求解能力""""
        name = "math_solver"
        description = "解决数学问题"
        parameters = {
            "problem": {"type": "string", "required": True},
        }

        def execute(self, problem: str) -> dict:
            return {"solution": f"已求解: {problem}", "confidence": 0.95}


    cap = CapabilityRegistry.get("math_solver")
    print(f"找到能力: {cap.name} - {cap.description}")


def demo_reflection_engine():
    """反思引擎演示""""
    print("\n--- 反思引擎演示 ---")

    from multiling.agent.reflection import ReflectionEngine

    engine = ReflectionEngine(
        error_analysis=True,
        pattern_detection=True,
        improvement_threshold=0.1,
    )


    analysis = engine.analyze(
        error="TypeError: unsupported operand type(s)",
        context={"function": "calculate", "input_types": ["str", "int"]}
    )
    print(f"错误分析: {analysis}")


    history = [
        {"error": "TypeError", "context": "type mismatch"},
        {"error": "TypeError", "context": "type mismatch"},
        {"error": "ValueError", "context": "invalid value"},
    ]
    patterns = engine.detect_patterns(history)
    print(f"检测到的模式: {patterns}")


if __name__ == "__main__":
    print("=" * 60)
    print("MINXG Agent 框架演示")
    print("=" * 60)

    demo_single_agent()
    demo_multi_agent_session()
    demo_role_system()
    demo_capability_system()
    demo_reflection_engine()

    print("\n" + "=" * 60)
    print("Agent 演示完成！")
    print("=" * 60)
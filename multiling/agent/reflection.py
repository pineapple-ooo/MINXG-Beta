"""
reflection.py — 智能体反思引擎

提供 Agent 的自我反思、错误分析、行为优化能力。
核心思想：每次重要行动后，Agent 分析结果并提取改进策略。
""""

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class Reflection:
    """一条反思记录""""
    action: str                    
    result: str                    
    analysis: str                  
    lesson: str                    
    improvement_plan: str          
    confidence: float = 0.5        
    timestamp: float = field(default_factory=time.time)
    reflection_id: str = field(default_factory=lambda: f"ref_{time.time():.0f}")

    def to_dict(self) -> dict:
        return {
            "reflection_id": self.reflection_id,
            "action": self.action, "result": self.result[:200],
            "analysis": self.analysis, "lesson": self.lesson,
            "improvement_plan": self.improvement_plan,
            "confidence": self.confidence, "timestamp": self.timestamp,
        }


class ReflectionEngine:
    """
    反思引擎

    工作流程:
    1. observe(action, result) — 观察行动和结果
    2. analyze() — 分析成败原因
    3. generate_lesson() — 提取经验
    4. plan_improvement() — 制定改进计划
    5. store() — 存储到长期记忆

    反思策略:
    - error_pattern_matching: 错误模式匹配
    - success_reinforcement: 成功强化
    - alternative_generation: 替代方案生成
    - performance_trend: 性能趋势分析
    """"

    
    ERROR_PATTERNS = {
        "timeout": {
            "pattern": r"(timeout|timed out|deadline|expired)",
            "lesson": "操作超时，应考虑增加超时时间或分步执行",
            "improvement": "实现分块处理 + 渐进式超时策略",
        },
        "auth_failure": {
            "pattern": r"(unauthorized|forbidden|auth|permission denied|401|403)",
            "lesson": "认证/授权失败，需要检查凭证和权限",
            "improvement": "在执行前验证权限，提供友好的错误提示",
        },
        "rate_limit": {
            "pattern": r"(rate limit|too many requests|429|throttl)",
            "lesson": "触发了频率限制",
            "improvement": "实现指数退避重试策略",
        },
        "invalid_input": {
            "pattern": r"(invalid|bad request|malformed|parse error|400)",
            "lesson": "输入数据格式不正确",
            "improvement": "增加输入验证和预处理",
        },
        "resource_not_found": {
            "pattern": r"(not found|404|missing|does not exist)",
            "lesson": "请求的资源不存在",
            "improvement": "在操作前先验证资源存在性",
        },
        "internal_error": {
            "pattern": r"(internal error|500|server error|exception)",
            "lesson": "服务端内部错误",
            "improvement": "实现重试机制和降级策略",
        },
    }

    def __init__(self, agent_name: str = "agent"):
        self.agent_name = agent_name
        self._reflections: List[Reflection] = []
        self._action_history: List[Tuple[str, str, float]] = []  
        self._performance_log: List[Dict] = []

    def observe(self, action: str, result: str,
                success: bool = None) -> Reflection:
        """
        观察一次行动及其结果，生成反思

        Args:
            action: 执行的行动描述
            result: 行动结果
            success: 是否成功（None=自动判断）

        Returns:
            Reflection 对象
        """"
        if success is None:
            success = self._auto_detect_success(result)

        analysis = self._analyze(action, result, success)
        lesson = self._generate_lesson(action, result, success, analysis)
        improvement = self._plan_improvement(action, result, success, analysis)

        confidence = self._calculate_confidence(result, analysis)

        reflection = Reflection(
            action=action[:200],
            result=result[:500],
            analysis=analysis,
            lesson=lesson,
            improvement_plan=improvement,
            confidence=confidence,
        )
        self._reflections.append(reflection)
        self._action_history.append((action, result, time.time()))

        return reflection

    def _auto_detect_success(self, result: str) -> bool:
        """自动判断行动是否成功""""
        result_lower = result.lower()
        success_signals = ["success", "ok", "done", "completed", "created",
                          "returned", "result:", "200"]
        failure_signals = ["error", "fail", "exception", "not found",
                          "timeout", "refused", "denied", "400", "404", "500"]

        success_count = sum(1 for s in success_signals if s in result_lower)
        failure_count = sum(1 for s in failure_signals if s in result_lower)

        if failure_count > 0 and failure_count >= success_count:
            return False
        return success_count > 0 or len(result.strip()) > 20

    def _analyze(self, action: str, result: str, success: bool) -> str:
        """分析行动结果""""
        if success:
            return f"行动 '{action[:60]}' 执行成功。结果: {result[:150]}"

        
        for error_type, pattern_info in self.ERROR_PATTERNS.items():
            if re.search(pattern_info["pattern"], result, re.IGNORECASE):
                return (f"检测到 {error_type} 类型错误: "
                        f"{result[:150]}。模式: {pattern_info['pattern']}")

        return f"行动 '{action[:60]}' 失败，未知原因: {result[:150]}"

    def _generate_lesson(self, action, result, success, analysis) -> str:
        """从分析中提取经验教训""""
        if success:
            return f"成功策略: {action[:50]} 的方式有效，可以在类似场景中复用。"

        for error_type, pattern_info in self.ERROR_PATTERNS.items():
            if re.search(pattern_info["pattern"], result, re.IGNORECASE):
                return pattern_info["lesson"]

        return "需要进一步分析失败原因，建议记录详细信息以便后续排查。"

    def _plan_improvement(self, action, result, success, analysis) -> str:
        """制定改进计划""""
        if success:
            return "继续沿用当前策略，可尝试优化执行效率。"

        for error_type, pattern_info in self.ERROR_PATTERNS.items():
            if re.search(pattern_info["pattern"], result, re.IGNORECASE):
                return pattern_info["improvement"]

        return "建议: 1) 检查输入参数 2) 增加错误处理 3) 添加重试逻辑"

    def _calculate_confidence(self, result: str, analysis: str) -> float:
        """计算反思置信度""""
        base = 0.5
        if len(result) > 50:
            base += 0.1
        if any(kw in analysis.lower() for kw in ["detected", "matched", "known"]):
            base += 0.15
        if len(result) > 200:
            base += 0.05
        return min(base, 0.95)

    def get_recent_reflections(self, limit: int = 10) -> List[Reflection]:
        """获取最近的反思""""
        return self._reflections[-limit:]

    def get_reflection_stats(self) -> Dict:
        """获取反思统计""""
        total = len(self._reflections)
        if total == 0:
            return {"total": 0}

        successes = sum(1 for r in self._reflections
                       if "成功" in r.analysis or "success" in r.result.lower())
        return {
            "total": total,
            "successes": successes,
            "failures": total - successes,
            "avg_confidence": round(
                sum(r.confidence for r in self._reflections) / total, 3
            ),
            "top_lessons": [r.lesson for r in self._reflections[-5:]],
        }

    def get_improvement_suggestions(self) -> List[str]:
        """获取综合改进建议""""
        suggestions = []
        stats = self.get_reflection_stats()

        if stats.get("failures", 0) > stats.get("total", 1) * 0.5:
            suggestions.append("⚠️ 失败率超过50%，建议重新审视工具使用策略")

        recent_errors = [r for r in self._reflections[-10:]
                        if "失败" in r.analysis]
        if recent_errors:
            error_types = set()
            for r in recent_errors:
                for etype in self.ERROR_PATTERNS:
                    if etype in r.analysis.lower():
                        error_types.add(etype)
            if error_types:
                suggestions.append(
                    f"📋 最近常见错误类型: {', '.join(error_types)}"
                )

        if stats.get("avg_confidence", 0) < 0.5:
            suggestions.append("💡 反思置信度偏低，建议收集更多执行数据")

        if not suggestions:
            suggestions.append("✅ 系统运行正常，继续当前策略")

        return suggestions

    def reset(self):
        """重置反思引擎""""
        self._reflections.clear()
        self._action_history.clear()
        self._performance_log.clear()
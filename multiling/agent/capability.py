"""
capability.py — 智能体能力声明与匹配系统

Capability 描述 Agent 能做什么（工具使用、知识领域、语言支持等）。
CapabilityRegistry 提供能力发现与智能匹配。
"""

from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
import time


@dataclass
class Capability:
    """能力声明"""
    name: str                       
    category: str = "general"       
    level: int = 1                  
    description: str = ""           
    tags: List[str] = field(default_factory=list)  
    metadata: Dict[str, Any] = field(default_factory=dict)  
    verified: bool = False          
    verified_at: Optional[float] = None

    def score_for(self, requirement: str) -> float:
        """
        计算此能力对给定需求的匹配分数
        精确匹配最高，标签匹配次之，分类匹配最低
        """
        req = requirement.lower()
        if self.name.lower() == req:
            return 10.0 * (self.level / 10.0)
        if req in [t.lower() for t in self.tags]:
            return 5.0 * (self.level / 10.0)
        if req == self.category.lower():
            return 2.0 * (self.level / 10.0)
        if req in self.description.lower():
            return 1.0 * (self.level / 10.0)
        return 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name, "category": self.category,
            "level": self.level, "description": self.description,
            "tags": self.tags, "verified": self.verified,
        }


class CapabilityRegistry:
    """能力全局注册表，支持智能匹配"""

    def __init__(self):
        self._capabilities: Dict[str, Capability] = {}
        self._category_index: Dict[str, List[str]] = {}  
        self._tag_index: Dict[str, List[str]] = {}        

    def register(self, cap: Capability):
        """注册能力"""
        self._capabilities[cap.name] = cap
        
        if cap.category not in self._category_index:
            self._category_index[cap.category] = []
        if cap.name not in self._category_index[cap.category]:
            self._category_index[cap.category].append(cap.name)
        
        for tag in cap.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            if cap.name not in self._tag_index[tag]:
                self._tag_index[tag].append(cap.name)

    def get(self, name: str) -> Optional[Capability]:
        return self._capabilities.get(name)

    def find_by_category(self, category: str) -> List[Capability]:
        """按分类查找能力"""
        names = self._category_index.get(category, [])
        return [self._capabilities[n] for n in names if n in self._capabilities]

    def find_by_tag(self, tag: str) -> List[Capability]:
        """按标签查找能力"""
        names = self._tag_index.get(tag, [])
        return [self._capabilities[n] for n in names if n in self._capabilities]

    def match(self, requirements: List[str], min_score: float = 1.0) -> List[Dict]:
        """
        根据需求列表匹配最佳能力
        返回: [{capability_name, score, capability}, ...] 按分数降序
        """
        scores: Dict[str, float] = {}
        for req in requirements:
            for name, cap in self._capabilities.items():
                s = cap.score_for(req)
                if s >= min_score:
                    scores[name] = scores.get(name, 0.0) + s

        results = []
        for name, score in sorted(scores.items(), key=lambda x: -x[1]):
            results.append({
                "capability_name": name,
                "score": round(score, 2),
                "capability": self._capabilities[name],
            })
        return results

    def list_all(self) -> List[Dict]:
        """列出所有能力摘要"""
        return [c.to_dict() for c in self._capabilities.values()]

    def get_stats(self) -> Dict:
        cats = {}
        for cap in self._capabilities.values():
            cats.setdefault(cap.category, []).append(cap.name)
        return {
            "total": len(self._capabilities),
            "categories": {k: len(v) for k, v in cats.items()},
            "tags_count": len(self._tag_index),
        }



CAPABILITY_TAGS = {
    "programming": ["python", "javascript", "go", "rust", "c++", "java"],
    "data": ["sql", "nosql", "pandas", "data_analysis", "etl"],
    "ai_ml": ["machine_learning", "deep_learning", "nlp", "computer_vision"],
    "devops": ["docker", "kubernetes", "ci_cd", "terraform", "monitoring"],
    "languages": ["english", "chinese", "japanese", "korean", "french", "spanish"],
}


def create_capability_from_tool(tool_name: str, tool_schema: Dict) -> Capability:
    """从工具定义自动生成能力声明"""
    return Capability(
        name=f"tool_{tool_name}",
        category="tool",
        level=5,
        description=f"Can execute tool: {tool_name}",
        tags=[tool_name, "auto_generated"],
        metadata={"tool_schema": tool_schema},
    )
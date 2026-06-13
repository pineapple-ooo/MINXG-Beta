"""
role.py — 智能体角色系统

Role 是 Agent 的行为模板，定义了 persona、能力范围和交互模式。
RoleRegistry 提供角色的全局注册与查找。
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class Role:
    """角色定义"""
    name: str                       # 角色名称（如 "analyst", "coder", "reviewer"）
    description: str = ""           # 角色描述
    persona: str = ""               # 人格设定（用于 system prompt）
    capabilities: List[str] = field(default_factory=list)  # 能力标签
    permissions: List[str] = field(default_factory=list)   # 权限列表
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展元数据
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "persona": self.persona, "capabilities": self.capabilities,
            "permissions": self.permissions, "metadata": self.metadata,
            "created_at": self.created_at,
        }

    def to_system_prompt(self) -> str:
        """将角色转换为系统提示词"""
        lines = [f"角色: {self.name}"]
        if self.description:
            lines.append(f"描述: {self.description}")
        if self.persona:
            lines.append(f"人格设定: {self.persona}")
        if self.capabilities:
            lines.append(f"能力: {', '.join(self.capabilities)}")
        return "\n".join(lines)


class RoleRegistry:
    """角色全局注册表"""

    def __init__(self):
        self._roles: Dict[str, Role] = {}
        self._aliases: Dict[str, str] = {}  # alias -> role_name

    def register(self, role: Role, alias: str = None):
        """注册角色，可选设置别名"""
        self._roles[role.name] = role
        if alias:
            self._aliases[alias] = role.name

    def get(self, name: str) -> Optional[Role]:
        """通过名称或别名获取角色"""
        if name in self._roles:
            return self._roles[name]
        alias_target = self._aliases.get(name)
        if alias_target:
            return self._roles.get(alias_target)
        return None

    def list_roles(self) -> List[Dict]:
        """列出所有角色摘要"""
        return [{"name": r.name, "description": r.description,
                 "capabilities": r.capabilities}
                for r in self._roles.values()]

    def remove(self, name: str) -> bool:
        """移除角色"""
        if name in self._roles:
            del self._roles[name]
            # 清理别名
            self._aliases = {k: v for k, v in self._aliases.items() if v != name}
            return True
        return False

    def create_from_template(self, name: str, template: str,
                             customizations: Dict = None) -> Optional[Role]:
        """从内置模板创建角色"""
        templates = {
            "analyst": {
                "description": "数据分析专家",
                "persona": "你是一个严谨的数据分析师，擅长从数据中发现模式和洞察。",
                "capabilities": ["data_analysis", "statistics", "visualization"],
            },
            "coder": {
                "description": "全栈开发工程师",
                "persona": "你是一个经验丰富的全栈工程师，代码风格简洁优雅。",
                "capabilities": ["programming", "code_review", "debugging"],
            },
            "reviewer": {
                "description": "代码审查专家",
                "persona": "你是一个细致的代码审查者，关注代码质量和安全性。",
                "capabilities": ["code_review", "security_audit", "testing"],
            },
            "writer": {
                "description": "技术文档撰写者",
                "persona": "你是一个清晰的技术文档撰写者，擅长将复杂概念简单化。",
                "capabilities": ["technical_writing", "documentation", "translation"],
            },
            "researcher": {
                "description": "研究专家",
                "persona": "你是一个深入的研究者，善于调研和分析前沿技术。",
                "capabilities": ["research", "literature_review", "critical_thinking"],
            },
        }
        tmpl = templates.get(template)
        if not tmpl:
            return None
        custom = customizations or {}
        role = Role(
            name=name,
            description=custom.get("description", tmpl["description"]),
            persona=custom.get("persona", tmpl["persona"]),
            capabilities=custom.get("capabilities", tmpl["capabilities"]),
            permissions=custom.get("permissions", []),
            metadata=custom.get("metadata", {}),
        )
        self.register(role)
        return role

    def get_stats(self) -> Dict:
        return {
            "total_roles": len(self._roles),
            "total_aliases": len(self._aliases),
            "role_names": list(self._roles.keys()),
        }


# 全局默认角色注册表
_default_role_registry: Optional[RoleRegistry] = None


def get_default_role_registry() -> RoleRegistry:
    """获取全局默认角色注册表（单例）"""
    global _default_role_registry
    if _default_role_registry is None:
        _default_role_registry = RoleRegistry()
        # 注册内置角色
        for t in ["analyst", "coder", "reviewer", "writer", "researcher"]:
            _default_role_registry.create_from_template(t, t)
    return _default_role_registry
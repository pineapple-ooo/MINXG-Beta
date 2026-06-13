"""
knowledge.py — 知识图谱与实体抽取模块

提供:
  - KnowledgeGraph: 基于内存的轻量级知识图谱
  - EntityExtractor: 命名实体识别与抽取
  - RelationExtractor: 实体关系抽取
  - KnowledgeQuery: 知识图谱查询接口
"""

import json
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Entity:
    """知识图谱中的实体"""
    id: str = field(default_factory=lambda: f"ent_{uuid.uuid4().hex[:10]}")
    name: str = ""
    entity_type: str = "unknown"      # person/organization/location/concept/event
    description: str = ""
    aliases: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "type": self.entity_type, "description": self.description,
            "aliases": self.aliases, "attributes": self.attributes,
            "confidence": self.confidence,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }


@dataclass
class Relation:
    """实体间关系"""
    id: str = field(default_factory=lambda: f"rel_{uuid.uuid4().hex[:10]}")
    source_id: str = ""     # 头实体ID
    target_id: str = ""     # 尾实体ID
    relation_type: str = ""  # 关系类型（works_at/located_in/is_a 等）
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source_id, "target": self.target_id,
            "type": self.relation_type, "attributes": self.attributes,
        }


class KnowledgeGraph:
    """
    内存知识图谱

    支持:
    - 实体 CRUD（带合并/去重）
    - 关系管理
    - 模式匹配查询
    - 子图提取
    - 导入/导出
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._entities: Dict[str, Entity] = {}
        self._relations: Dict[str, Relation] = []
        self._name_index: Dict[str, str] = {}      # name -> entity_id
        self._type_index: Dict[str, List[str]] = defaultdict(list)  # type -> [entity_ids]
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)     # entity_id -> connected entity_ids
        self._stats = {"entities": 0, "relations": 0, "merges": 0}

    def add_entity(self, entity: Entity, merge: bool = True) -> str:
        """
        添加实体到知识图谱

        Args:
            entity: 实体对象
            merge: 如果同名词汇已存在，是否合并

        Returns:
            实体ID
        """
        # 检查是否已存在同名实体
        existing_id = self._name_index.get(entity.name.lower())
        if existing_id and merge:
            self._merge_entity(existing_id, entity)
            return existing_id

        self._entities[entity.id] = entity
        self._name_index[entity.name.lower()] = entity.id
        self._type_index[entity.entity_type].append(entity.id)
        self._stats["entities"] += 1
        return entity.id

    def _merge_entity(self, existing_id: str, new_entity: Entity):
        """合并两个同名实体"""
        existing = self._entities[existing_id]
        # 合并别名
        for alias in new_entity.aliases:
            if alias.lower() not in [a.lower() for a in existing.aliases]:
                existing.aliases.append(alias)
        # 更新描述（如果新描述更长）
        if len(new_entity.description) > len(existing.description):
            existing.description = new_entity.description
        # 合并属性
        existing.attributes.update(new_entity.attributes)
        # 更新类型（如果新类型更具体）
        if new_entity.entity_type != "unknown":
            existing.entity_type = new_entity.entity_type
        # 更新置信度
        existing.confidence = max(existing.confidence, new_entity.confidence)
        existing.updated_at = time.time()
        self._stats["merges"] += 1

    def add_relation(self, source_id: str, target_id: str,
                     relation_type: str, attrs: Dict = None) -> str:
        """添加实体间关系"""
        if source_id not in self._entities:
            raise ValueError(f"Unknown source entity: {source_id}")
        if target_id not in self._entities:
            raise ValueError(f"Unknown target entity: {target_id}")

        rel = Relation(
            source_id=source_id, target_id=target_id,
            relation_type=relation_type,
            attributes=attrs or {},
        )
        self._relations.append(rel)
        self._adjacency[source_id].add(target_id)
        self._adjacency[target_id].add(source_id)
        self._stats["relations"] += 1
        return rel.id

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self._entities.get(entity_id)

    def find_entities(self, name: str = "", entity_type: str = "",
                      limit: int = 20) -> List[Entity]:
        """查找实体"""
        results = []
        for e in self._entities.values():
            match = True
            if name and name.lower() not in e.name.lower():
                match = False
            if entity_type and e.entity_type != entity_type:
                match = False
            if match:
                results.append(e)
        return results[:limit]

    def get_neighbors(self, entity_id: str,
                      relation_type: str = "") -> List[Tuple[Entity, Relation]]:
        """获取实体的邻居"""
        results = []
        for rel in self._relations:
            if rel.source_id == entity_id:
                target = self._entities.get(rel.target_id)
                if target and (not relation_type or rel.relation_type == relation_type):
                    results.append((target, rel))
            elif rel.target_id == entity_id:
                source = self._entities.get(rel.source_id)
                if source and (not relation_type or rel.relation_type == relation_type):
                    results.append((source, rel))
        return results

    def query(self, pattern: Dict) -> List[Dict]:
        """
        模式匹配查询

        Args:
            pattern: 查询模式，如:
                {"type": "person", "relations": [{"type": "works_at", "target_type": "organization"}]}

        Returns:
            匹配的实体和关系列表
        """
        entity_type = pattern.get("type", "")
        rel_patterns = pattern.get("relations", [])

        candidates = (self._type_index.get(entity_type, list(self._entities.keys()))
                      if entity_type else list(self._entities.keys()))

        results = []
        for eid in candidates:
            entity = self._entities.get(eid)
            if not entity:
                continue

            match = True
            matched_relations = []
            for rp in rel_patterns:
                found = False
                for target, rel in self.get_neighbors(eid, rp.get("type", "")):
                    if not rp.get("target_type") or target.entity_type == rp["target_type"]:
                        found = True
                        matched_relations.append({
                            "relation": rel.to_dict(),
                            "target": target.to_dict(),
                        })
                if not found and rp.get("required", True):
                    match = False
                    break

            if match:
                results.append({
                    "entity": entity.to_dict(),
                    "relations": matched_relations,
                })

        return results

    def extract_subgraph(self, center_id: str, depth: int = 2) -> Dict:
        """提取以某实体为中心的子图"""
        if center_id not in self._entities:
            return {"center": None, "entities": [], "relations": []}

        visited = {center_id}
        frontier = {center_id}
        subgraph_entities = [self._entities[center_id]]
        subgraph_relations = []

        for _ in range(depth):
            next_frontier = set()
            for eid in frontier:
                for target, rel in self.get_neighbors(eid):
                    subgraph_relations.append(rel)
                    if target.id not in visited:
                        visited.add(target.id)
                        next_frontier.add(target.id)
                        subgraph_entities.append(target)
            frontier = next_frontier

        return {
            "center": center_id,
            "entities": [e.to_dict() for e in subgraph_entities],
            "relations": [r.to_dict() for r in subgraph_relations],
        }

    def export_json(self) -> str:
        """导出为 JSON"""
        return json.dumps({
            "name": self.name,
            "entities": [e.to_dict() for e in self._entities.values()],
            "relations": [r.to_dict() for r in self._relations],
        }, ensure_ascii=False, indent=2)

    def import_json(self, data: str):
        """从 JSON 导入"""
        obj = json.loads(data)
        for e_data in obj.get("entities", []):
            ent = Entity(**{k: v for k, v in e_data.items()
                           if k in Entity.__dataclass_fields__})
            self.add_entity(ent, merge=False)
        for r_data in obj.get("relations", []):
            rel = Relation(**{k: v for k, v in r_data.items()
                             if k in Relation.__dataclass_fields__})
            self._relations.append(rel)
            self._adjacency[rel.source_id].add(rel.target_id)
            self._adjacency[rel.target_id].add(rel.source_id)
            self._stats["relations"] += 1

    def get_stats(self) -> Dict:
        type_dist = {t: len(ids) for t, ids in self._type_index.items()}
        return {
            "name": self.name,
            "entities": self._stats["entities"],
            "relations": self._stats["relations"],
            "merges": self._stats["merges"],
            "type_distribution": type_dist,
        }


class EntityExtractor:
    """
    命名实体识别器（基于规则 + 模式匹配）

    支持: 中文、英文、日文、韩文等实体类型识别
    """

    # 内置实体模式
    PATTERNS = {
        "email": r'[\w.+-]+@[\w-]+\.[\w.-]+',
        "url": r'https?://[^\s<>"{}|\\^`\[\]]+',
        "phone": r'(?:\+?86[- ]?)?1[3-9]\d{9}',
        "ip_address": r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
        "date": r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?',
        "time": r'\d{1,2}[:：]\d{2}([:：]\d{2})?',
        "id_card": r'\b\d{17}[\dXx]\b',
    }

    # 中文命名实体启发式规则
    CHINESE_PATTERNS = {
        "person": r'[·•][\u4e00-\u9fff]{2,4}',  # 含间隔符的中文名
        "organization": r'(?:公司|集团|大学|学院|研究所|局|部|委员会|银行|医院)',
        "location": (r'(?:省|市|区|县|镇|村|路|街|巷|号|国|省|自治区|特别行政区)'
                     r'[\u4e00-\u9fff]{1,10}'),
    }

    def __init__(self):
        self._compiled = {k: re.compile(v) for k, v in self.PATTERNS.items()}
        self._zh_compiled = {k: re.compile(v) for k, v in self.CHINESE_PATTERNS.items()}

    def extract(self, text: str, types: List[str] = None) -> List[Dict]:
        """
        从文本中提取实体

        Args:
            text: 输入文本
            types: 要提取的实体类型列表（None=全部）

        Returns:
            实体列表 [{type, value, start, end, confidence}, ...]
        """
        entities = []
        target_types = set(types) if types else set(self.PATTERNS.keys())

        # 模式匹配实体
        for etype in target_types:
            if etype not in self._compiled:
                continue
            for m in self._compiled[etype].finditer(text):
                entities.append({
                    "type": etype,
                    "value": m.group(),
                    "start": m.start(),
                    "end": m.end(),
                    "confidence": 0.95,
                    "method": "regex",
                })

        # 中文命名实体
        for etype in ("person", "organization", "location"):
            if types and etype not in types:
                continue
            for m in self._zh_compiled[etype].finditer(text):
                entities.append({
                    "type": etype,
                    "value": m.group(),
                    "start": m.start(),
                    "end": m.end(),
                    "confidence": 0.7,
                    "method": "heuristic",
                })

        # 按位置排序，去除重叠
        entities.sort(key=lambda e: e["start"])
        return self._remove_overlaps(entities)

    def _remove_overlaps(self, entities: List[Dict]) -> List[Dict]:
        """去除重叠的实体（保留置信度高的）"""
        if not entities:
            return []
        filtered = [entities[0]]
        for e in entities[1:]:
            last = filtered[-1]
            if e["start"] >= last["end"]:
                filtered.append(e)
            elif e["confidence"] > last["confidence"]:
                filtered[-1] = e
        return filtered

    def extract_to_entities(self, text: str, graph: KnowledgeGraph = None) -> List[Entity]:
        """提取实体并转换为 Entity 对象"""
        results = self.extract(text)
        entities = []
        for r in results:
            ent = Entity(
                name=r["value"],
                entity_type=r["type"],
                description=f"从文本中提取: {r['value']}",
                attributes={
                    "source_method": r["method"],
                    "confidence": r["confidence"],
                    "text_position": [r["start"], r["end"]],
                },
                confidence=r["confidence"],
            )
            entities.append(ent)
            if graph:
                graph.add_entity(ent)
        return entities


class RelationExtractor:
    """
    关系抽取器

    基于模式和关键词的关系识别
    """

    # 常见关系模式
    RELATION_PATTERNS = {
        "works_at": [
            r'({name})(?:在|就职于|工作于|任职于|加入)({org})',
            r'({org})(?:的|之)(?:员工|职员|成员)(?:包括|有)({name})',
        ],
        "located_in": [
            r'({name})(?:位于|在|处于|坐落在)({location})',
            r'({location})(?:的|之)(?:所在地|位置).*?({name})',
        ],
        "is_a": [
            r'({name})(?:是|属于|为|作为)({concept})',
            r'({concept})(?:包括|包含|涵盖)({name})',
        ],
        "studied_at": [
            r'({name})(?:毕业于|就读于|求学于|学位)({org})',
        ],
        "founded": [
            r'({name})(?:创立|创办|创建|建立)({org})',
        ],
    }

    def __init__(self):
        self._compiled = {}
        for rel_type, patterns in self.RELATION_PATTERNS.items():
            self._compiled[rel_type] = [re.compile(p) for p in patterns]

    def extract(self, text: str, entities: List[Entity] = None) -> List[Dict]:
        """
        从文本中抽取实体关系

        Args:
            text: 输入文本
            entities: 已知实体列表（用于约束匹配）

        Returns:
            关系列表 [{type, source, target, confidence}, ...]
        """
        relations = []
        entity_names = set()
        if entities:
            entity_names = {e.name for e in entities}

        for rel_type, patterns in self._compiled.items():
            for pattern in patterns:
                for m in pattern.finditer(text):
                    source = m.group(1) if m.lastindex and m.lastindex >= 1 else ""
                    target = m.group(2) if m.lastindex and m.lastindex >= 2 else ""

                    # 如果有已知实体列表，验证匹配
                    if entity_names:
                        if source and source not in entity_names:
                            continue
                        if target and target not in entity_names:
                            continue

                    if source and target:
                        relations.append({
                            "type": rel_type,
                            "source": source,
                            "target": target,
                            "confidence": 0.7,
                            "method": "pattern",
                        })

        return self._deduplicate(relations)

    def _deduplicate(self, relations: List[Dict]) -> List[Dict]:
        """去重关系"""
        seen = set()
        unique = []
        for r in relations:
            key = (r["source"], r["target"], r["type"])
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique


class KnowledgeQuery:
    """知识图谱自然语言查询接口"""

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph
        self.extractor = EntityExtractor()
        self.rel_extractor = RelationExtractor()

    def ask(self, question: str) -> List[Dict]:
        """
        自然语言查询知识图谱

        Examples:
            "谁在ABC公司工作？"
            "北京有什么知名组织？"
            "张三是什么类型的人？"
        """
        # 先从问题中提取实体
        entities = self.extractor.extract(question)
        entity_names = {e["value"] for e in entities}

        results = []

        # 模式1: "谁在[X]工作" → 查询 works_at 关系到 X
        if "工作" in question:
            for name in entity_names:
                pattern = {"type": "person", "relations": [
                    {"type": "works_at", "target_type": "organization", "required": False}
                ]}
                matches = self.graph.query(pattern)
                for m in matches:
                    if name in str(m):
                        results.append(m)

        # 模式2: "[X]是什么" → 查询实体的详细信息
        if "是什么" in question or "是啥" in question:
            for name in entity_names:
                found = self.graph.find_entities(name=name)
                for e in found:
                    results.append({
                        "entity": e.to_dict(),
                        "neighbors": [
                            {"target": t.to_dict(), "relation": r.to_dict()}
                            for t, r in self.graph.get_neighbors(e.id)
                        ],
                    })

        # 模式3: 通用实体查找
        if not results and entity_names:
            for name in entity_names:
                found = self.graph.find_entities(name=name)
                results.extend([{"entity": e.to_dict()} for e in found])

        # 模式4: 类型查询
        for etype in ("person", "organization", "location", "concept", "event"):
            etype_zh = {"person": "人|人物", "organization": "组织|公司|机构",
                        "location": "地点|位置|城市", "concept": "概念", "event": "事件"}.get(etype, "")
            if etype_zh and any(w in question for w in etype_zh.split("|")):
                results.extend([
                    {"entity": e.to_dict()}
                    for e in self.graph.find_entities(entity_type=etype)
                ])

        return results

    def search(self, keywords: str, limit: int = 10) -> List[Dict]:
        """关键词搜索知识图谱"""
        entities = self.graph.find_entities(name=keywords, limit=limit)
        results = []
        for e in entities:
            neighbors = self.graph.get_neighbors(e.id)
            results.append({
                "entity": e.to_dict(),
                "related_entities": [
                    {"entity": t.to_dict(), "relation": r.to_dict()}
                    for t, r in neighbors[:5]
                ],
            })
        return results
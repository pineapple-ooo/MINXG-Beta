# 算子目录

> 全部 376 个算子的完整目录。架构见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 概览

| 类别 | 数量 | ID 范围 | 支柱 |
|------|------|---------|------|
| **ga** | 47 | 5000-5049 | 几何代数 (Clifford) |
| **cat** | 79 | 4000-4078 | 范畴论 |
| **infogeo** | 51 | 7000-7050 | 信息几何 |
| **topo** | 53 | 8000-8052 | 代数拓扑 |
| **chaos** | 23 | 8500-8522 | 动力系统与混沌 |
| **fiber** | 53 | 6000-6052 | 纤维丛 |
| **math** | 20 | 0-19 | 标量数学 |
| **text** | 19 | 2000-2018 | 字符串 |
| **data** | 12 | 3500-3511 | 数据结构 |
| **logic** | 13 | 5500-5512 | 布尔 |
| **system** | 6 | 9000-9005 | 系统 |
| **总计** | **376** | | |

详细列表见 [ARCHITECTURE.md](ARCHITECTURE.md) § 2 各支柱描述,
或各支柱目录的 `README.md`。

## 浏览

```python
from minxg.operators import OPERATOR_REGISTRY
for op in OPERATOR_REGISTRY.get_category("ga"):
    print(f"{op.op_id:5d}  {op.name:30s}  {op.description}")
```

## 数学支柱入口

- 几何代数: `minxg/ga/`
- 范畴论: `minxg/cat/`
- 信息几何: `minxg/infogeo/`
- 代数拓扑: `minxg/topo/`
- 动力系统: `minxg/chaos/`
- 纤维丛: `minxg/fiber/`

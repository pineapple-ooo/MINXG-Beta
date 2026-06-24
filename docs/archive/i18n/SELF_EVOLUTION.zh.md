# 自演化

> 10 个原创行为同构算法。

## 10 个算法

1. **ISG** — 交互结构图
2. **NCD** — 归一化压缩距离
3. **SIG** — 谱不变量
4. **SIC** — 结构同构类
5. **BSP** — 行为相空间(32 维)
6. **BMO** — 行为动量
7. **TINV** — 拓扑不变量
8. **SD** — 结构漂移(阈值 0.15/天)
9. **INV** — 行为不变量
10. **PVT** — 扰动验证(沙箱化)

## 为何是结构性而非词汇性

| 方法 | 问题 | 局限 |
|------|------|------|
| 正则匹配 | 用户说 X 吗? | 脆弱,语言特定 |
| 嵌入相似 | 意思相似吗? | 错过结构 |
| **NCD/ISG** | **交互几何匹配 X 吗?** | **语言无关** |

## 组件

- `src/ai/memory/behavioral_isomorphism.py` — 10 个算法
- `src/ai/memory/entropic_evolution.py` — 熵
- `src/ai/memory/evolution_v2.py` — 25+ 模式
- `src/ai/memory/causal_graph.py` — PC 算法
- `src/ai/memory/topological.py` — Vietoris-Rips
- `src/ai/memory/tidal_lock_bridge.py` — C 加速

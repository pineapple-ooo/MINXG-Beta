# 项目索引

> 一页找到 MINXG 中的任何东西。

## 0 · MINXG 是什么?

MINXG 是纯 Python AI 编排框架,算子集建立在**六大数学支柱**之上:

1. **几何代数**(Clifford) — 多向量、旋量、反射
2. **范畴论** — 态射、函子、单子、Yoneda
3. **信息几何** — Fisher 度量、自然梯度
4. **代数拓扑** — 持续同调、单纯复形
5. **动力系统与混沌** — Lyapunov、吸引子、分形
6. **纤维丛** — 联络、平行移动、曲率

**376 算子 · 11 类别 · 6 数学支柱 · 100% 纯 Python。**

## 1 · 一切在哪里

```
MINXG/
├── minxg/                   ← Python 包(原 py_workers)
│   ├── operators.py         ← 算子注册中心
│   ├── ga/ cat/ infogeo/ topo/ chaos/ fiber/  ← 6 大数学支柱
│   └── *.py                 ← 50+ 工具 worker
├── py_workers/              ← 向后兼容别名
├── config/minxg.yaml        ← 唯一配置
├── extensions/              ← 扩展
├── c_core/  cpp_core/  go_core/  ← 加速核心
└── PROJECT_INDEX.md ...     ← 5 语言 README
```

## 2 · 6 大数学支柱

| 支柱 | 代码 | 算子 |
|------|------|------|
| **GA** 几何代数 | `minxg/ga/` | 47 |
| **CAT** 范畴论 | `minxg/cat/` | 79 |
| **IG** 信息几何 | `minxg/infogeo/` | 51 |
| **TOPO** 代数拓扑 | `minxg/topo/` | 53 |
| **CHAOS** 动力系统 | `minxg/chaos/` | 23 |
| **FIBER** 纤维丛 | `minxg/fiber/` | 53 |

## 3 · 找什么的指南

| 你想… | 看… |
|------|-----|
| 加新算子 | `minxg/<pillar>/operators_<pillar>.py` |
| 加新 worker | `minxg/base.py` (用 `@tool`) |
| 加新支柱 | 复制 `minxg/fiber/`,在 `minxg/__init__.py` 注册 |
| 改运行时配置 | `config/minxg.yaml` |
| 改构建配置 | `pyproject.toml` |
| 加速热路径 | `c_core/` (Tidal Lock) |

## 4 · 算子 ID 分配

| 范围 | 支柱 |
|------|------|
| 0-19 | math |
| 2000-2018 | text |
| 3500-3511 | data |
| 4000-4499 | cat |
| 5000-5499 | ga |
| 5500-5512 | logic |
| 6000-6499 | fiber |
| 7000-7499 | infogeo |
| 8000-8499 | topo |
| 8500-8999 | chaos |
| 9000-9005 | system |
| 10000+ | 自定义/扩展 |

匹配 `config/minxg.yaml`。

# MINXG — 多语言 AI 编排框架

> **六大数学支柱,376 个算子,纯 Python 框架。震碎其他 AI Agent 世界观。**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![算子: 376](https://img.shields.io/badge/算子-376-green.svg)](OPERATORS.md)
[![数学支柱: 6](https://img.shields.io/badge/数学支柱-6-orange.svg)](ARCHITECTURE.md)

[English](README.md) | [简体中文](README.zh.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

---

## 什么是 MINXG?

MINXG 是一个纯 Python AI 编排框架,其**算子集建立在六大数学支柱**之上 —— 这是其他 AI 框架都没有作为一等原语暴露的。

其他框架把算子当作 Python 可调用对象,MINXG 把算子视为:

1. **多向量**(Clifford 代数)—— 统一的旋转、反射、缩放
2. **态射**(范畴论)—— 类型检查、可组合、函子/单子结构
3. **点**(统计流形)—— 自然梯度、Fisher 度量、α-联络
4. **特征**(拓扑空间)—— 持续同调、Betti 数、流形形状
5. **轨迹**(动力系统)—— Lyapunov 指数、吸引子、分形
6. **截面**(纤维丛)—— 联络、平行移动、曲率

**376 个算子,11 个类别,6 大数学支柱,100% 纯 Python。**

---

## 30 秒快速开始

```bash
git clone https://github.com/minxg/minxg.git
cd minxg
pip install -e .
```

```python
import minxg
from minxg.operators import OPERATOR_REGISTRY
print(f"{OPERATOR_REGISTRY.total_operators} 个算子,分 {len(OPERATOR_REGISTRY.list_categories())} 类")
```

---

## 六大支柱,一个例子

### 几何代数 —— 3D 旋转向量

```python
from minxg.ga import Multivector, Signature, Rotor
import math

sig = Signature(3, 0)
e1 = Multivector({1: 1.0}, sig)
e3 = Multivector({4: 1.0}, sig)

B = e3.outer(e1).normalize()
R = Rotor.from_bivector(B, math.pi / 2)
print(f"R(e1) = {R.apply(e1)}")
```

### 范畴论 —— 类型安全的组合

```python
from minxg.cat import Morphism
f = Morphism("f", ("int",), "string", str)
g = Morphism("g", ("string",), "int", len)
print((f >> g)(42))
```

### 信息几何 —— 自然梯度

```python
from minxg.infogeo import Gaussian, fisher_information_matrix, natural_gradient
g = Gaussian()
F = fisher_information_matrix(g, [0.0, 1.0], n_samples=1000)
print(natural_gradient([0.5, 0.1], F))
```

### 代数拓扑 —— Betti 数

```python
from minxg.topo import Simplex, SimplicialComplex
c = SimplicialComplex()
c.add(Simplex(frozenset({0, 1, 2, 3})))
print(c.betti_numbers())
```

### 动力系统 —— Lyapunov 指数

```python
from minxg.chaos import logistic_lyapunov
print(f"Lyapunov: {logistic_lyapunov(3.9):.4f}")
```

### 纤维丛 —— 平行移动 + 曲率

```python
from minxg.fiber import Connection, ParallelTransport, Curvature
conn = Connection(dim=2)
pt = ParallelTransport(conn, lambda t: [t, t**2], 0.0, 1.0)
print(pt.transport([1.0, 0.0]))
```

---

## 为什么选择 MINXG?

| 框架 | 算子模型 | 类型系统 | 组合 |
|------|----------|----------|------|
| LangChain | name→callable 字典 | 字符串标签 | 临时拼凑 |
| AutoGen | 异步函数 | Python 类型 | 手动 |
| CrewAI | 类实例 | 鸭子类型 | 隐式 |
| **MINXG** | **范畴中的态射** | **类型论** | **自动、类型检查** |

MINXG 的六大数学支柱提供其他框架没有的特性:

1. **数学保证** —— 算子组合是类型检查的
2. **参数化不变性** —— 自然梯度在重参数化下不变
3. **拓扑特征** —— 持续同调揭示统计方法看不到的结构
4. **几何运算** —— 旋量、反射、缩放是单一运算
5. **混沌感知计算** —— Lyapunov 指数、分叉图量化可预测性
6. **规范理论结构** —— 纤维丛、平行移动、曲率

---

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│              应用层 (agents, extensions)                    │
├─────────────────────────────────────────────────────────────┤
│              自演化层 (10 个原创算法)                       │
├─────────────────────────────────────────────────────────────┤
│  GA 47 │ CAT 79 │ IG 51 │ TOPO 53 │ CHAOS 23 │ FIBER 53     │
├─────────────────────────────────────────────────────────────┤
│              算子注册中心 (376 ops)                          │
│  math 20 │ text 19 │ data 12 │ logic 13 │ system 6         │
├─────────────────────────────────────────────────────────────┤
│              Tidal Lock C 加速                              │
├─────────────────────────────────────────────────────────────┤
│              Worker 层 (50+)                                │
└─────────────────────────────────────────────────────────────┘
```

完整架构见 [ARCHITECTURE.md](ARCHITECTURE.md)。

---

## 文档

| 文档 | 用途 |
|------|------|
| [PROJECT_INDEX.md](PROJECT_INDEX.md) | 一页项目地图 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统架构详解 |
| [INSTALL.md](INSTALL.md) | 全平台安装 |
| [QUICKSTART.md](QUICKSTART.md) | 5 分钟走遍 6 大支柱 |
| [OPERATORS.md](OPERATORS.md) | 376 个算子全集 |
| [EXTENSIONS.md](EXTENSIONS.md) | 自定义算子/Worker/支柱 |
| [SELF_EVOLUTION.md](SELF_EVOLUTION.md) | 10 个行为算法 |
| [TIDAL_LOCK.md](TIDAL_LOCK.md) | C 加速 |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史 |

各支柱的文档在它们自己的目录里:
- `minxg/ga/README.md` — 几何代数
- `minxg/cat/README.md` — 范畴论
- `minxg/infogeo/README.md` — 信息几何
- `minxg/topo/README.md` — 代数拓扑
- `minxg/chaos/README.md` — 动力系统
- `minxg/fiber/README.md` — 纤维丛

每个文档都有英文 / 简体中文 / 日本語 / 한국어 版本。

---

## 验证环境

- **Termux / Android 10+**(本项目主要开发环境)
- **Linux x86_64**(Ubuntu 22.04+, Debian 12+)
- **macOS 12+**(Intel 和 Apple Silicon)

---

## 许可证

MIT

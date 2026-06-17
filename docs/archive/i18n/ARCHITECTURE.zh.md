# 架构

> MINXG 的完整架构.一站式地图见 [PROJECT_INDEX.md](PROJECT_INDEX.md)。

## 1 · 分层系统

```
┌────────────────────────────────────────────────────────────────┐
│                  应用层 (agents, extensions)                   │
├────────────────────────────────────────────────────────────────┤
│                  自演化层 (10 个原创算法)                       │
├────────────────────────────────────────────────────────────────┤
│  GA 47 │ CAT 79 │ IG 51 │ TOPO 53 │ CHAOS 23 │ FIBER 53         │
├────────────────────────────────────────────────────────────────┤
│              Python 算子注册中心 (376 ops)                     │
│  math 20 │ text 19 │ data 12 │ logic 13 │ system 6             │
├────────────────────────────────────────────────────────────────┤
│              Tidal Lock C 加速                                │
├────────────────────────────────────────────────────────────────┤
│              Worker 层 (50+)                                  │
├────────────────────────────────────────────────────────────────┤
│              平台适配器 (Termux · Linux · macOS · iOS · IoT)  │
└────────────────────────────────────────────────────────────────┘
```

## 2 · 六大数学支柱

### 2.1 几何代数 — `minxg/ga/` — 47 算子

Clifford 代数 — 把标量、向量、矩阵、四元数统一为单一**多向量**类型。详见 `minxg/ga/README.md`。

### 2.2 范畴论 — `minxg/cat/` — 79 算子

每个算子都是带显式 domain/codomain 的**态射**。详见 `minxg/cat/README.md`。

### 2.3 信息几何 — `minxg/infogeo/` — 51 算子

Fisher 信息矩阵作为度量。**自然梯度**重参数化不变。详见 `minxg/infogeo/README.md`。

### 2.4 代数拓扑 — `minxg/topo/` — 53 算子

持续同调、Betti 数、持续图、Wasserstein 距离。详见 `minxg/topo/README.md`。

### 2.5 动力系统与混沌 — `minxg/chaos/` — 23 算子

Lyapunov 指数、吸引子、分形、分叉图。详见 `minxg/chaos/README.md`。

### 2.6 纤维丛 — `minxg/fiber/` — 53 算子

联络、平行移动、曲率、规范理论。详见 `minxg/fiber/README.md`。

## 3 · 算子注册中心

`minxg/operators.py` 的 `OPERATOR_REGISTRY` 是唯一注册中心。

## 4 · 配置

`config/minxg.yaml` 是运行时配置的唯一来源。

## 5 · 加速核心

- C 核心、Tidal Lock、C++ 核心、Go 核心

## 6 · 自演化

详见 [SELF_EVOLUTION.md](SELF_EVOLUTION.md)。

## 7 · 扩展点

详见 [EXTENSIONS.md](EXTENSIONS.md)。

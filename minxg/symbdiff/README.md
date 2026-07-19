# SymbDiff — 符号微分代数系统

> MINXG 第七大数学支柱 (v0.14.1)

## 概述

SymbDiff 不是一个玩具式CAS。它是一个真正的**微分代数**系统，在截断幂级数（jet）上运算，自动传播任意阶导数。它补上了MINXG六大数学柱中缺失的**微积分视角**——使驱动引擎从数值积分器进化为结构感知引擎。

## 核心类型

### `Jet(order, value, derivs)` — 截断泰勒级数

自动微分（AD）的对偶数推广。一阶Jet退化为经典对偶数；高阶Jet携带 f', f'', ..., f^(n-1)。

**运算：**
- `+`, `-`, `*`, `/` — Leibniz法则自动传播
- `power(n)` — 支持分数幂，经 ln/exp 链式法则
- `sine()`, `cosine()` — 三角函数的jet推广
- `natural_log()`, `exponential()` — 超 函数/对数
- `evaluate(dx)` — 在偏离点估值泰勒多项式
- `taylor_coeff(n)` — 提取第n个泰勒系数 f^(n)/n!

**示例：**

```python
from minxg.symbdiff import Jet

# 在 x0=2 处计算 f(x) = x^3 的前三阶导数
x = Jet.variable(4, x0=2.0)
y = x.power(3)
# y.value  = 8.0    (2^3)
# y.derivs[0] = 12.0  (3*2^2)
# y.derivs[1] = 12.0  (6*2)
# y.derivs[2] = 6.0   (6)

# 复合函数 g(x) = sin(x^2) 的自动微分
y = (x.power(2)).sine()
```

### `DiffPoly(variables, coefficients)` — 微分多项式

在变量及其导数 x, x', x'', ... 上的多项式。支持：
- 加减法
- `total_derivative()` — 全时间导数 dP/dt，自动使用链式法则与积法则

### `VectorField(components, name)` — 向量场

R^n上的向量场，用于Lie括号计算。

### `lie_bracket(X, Y, state)` — 李括号

计算 [X,Y] = XY - YX，判断两个算子场是否可交换。若李括号消失，驱动引擎可自由重排算子而不引入漂移。

### `find_integrating_factor(M, N)` — 积分因子发现

对 ODE M dx + N dy = 0，自动探测三种经典积分因子模式：
1. μ(x) — 仅依赖x
2. μ(y) — 仅依赖y
3. 幂律 μ = x^a · y^b

## 与驱动引擎的集成

```
DriverEngine(method="rk4")
  ├── JetOperator — 每步注入精确导数到state
  ├── LieBracketOp — 检测算子交换性
  ├── DiffIdealOp — 微分理想成员判定
  └── IntFactorOp — ODE积分因子发现
```

当JetOperator注入精确导数时，RK45的自适应步长控制变为**精确误差估计**而非有限差分近似。当LieBracketOp发现两个算子场的李括号消失时，引擎知道它们可交换，从而消除漂移。

## 与其他六大数学柱的关系

| 数学柱 | 视角 | SymbDiff 的贡献 |
|--------|------|----------------|
| GA (几何代数) | 几何 | Jet推广了导数到多重向量 |
| Cat (范畴论) | 组合 | DiffPoly是微分环上的态射 |
| InfoGeo (信息几何) | 统计 | Jet提供精确Fisher信息 |
| Topo (拓扑) | 同调 | Lie括号链接到de Rham上同调 |
| Chaos (混沌) | 动力 | Lyapunov指数→Jet变分方程 |
| Fiber (纤维丛) | 拓扑 | 联络系数→Taylor系数 |

## 设计原则

1. **截断即特性** — Jet的截断阶N不是近似误差，而是微分流形的局部坐标数
2. **零分配** — 不依赖sympy等外部CAS，纯Python实现
3. **算子场集成** — 每个类型都可包装为Operator注入驱动引擎

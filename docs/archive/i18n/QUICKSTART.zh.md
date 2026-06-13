# 快速开始

> 5 分钟走遍 6 大数学支柱。

## 1 · 几何代数:3D 旋转向量

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

## 2 · 范畴论:类型安全组合

```python
from minxg.cat import Morphism
f = Morphism("f", ("int",), "string", str)
g = Morphism("g", ("string",), "int", len)
print((f >> g)(42))
```

## 3 · 信息几何:自然梯度

```python
from minxg.infogeo import Gaussian, fisher_information_matrix, natural_gradient
g = Gaussian()
F = fisher_information_matrix(g, [0.0, 1.0], n_samples=1000)
print(natural_gradient([0.5, 0.1], F))
```

## 4 · 代数拓扑:持续同调

```python
from minxg.topo import Simplex, SimplicialComplex
c = SimplicialComplex()
c.add(Simplex(frozenset({0, 1, 2, 3})))
print(c.betti_numbers())
```

## 5 · 动力系统:Lyapunov 指数

```python
from minxg.chaos import logistic_lyapunov
print(f"Lyapunov: {logistic_lyapunov(3.9):.4f}")
```

## 6 · 纤维丛:平行移动 + 曲率

```python
from minxg.fiber import Connection, ParallelTransport, Curvature
conn = Connection(dim=2)
pt = ParallelTransport(conn, lambda t: [t, t**2], 0.0, 1.0)
print(pt.transport([1.0, 0.0]))
```

## 下一步

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [OPERATORS.md](OPERATORS.md)

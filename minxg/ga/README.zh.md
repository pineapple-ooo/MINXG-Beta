# 几何代数 (Clifford 代数)

> MINXG 6 大数学支柱第 1 个,47 个算子,ID 5000-5049。

Clifford 代数把标量、向量、矩阵、四元数统一为**多向量(multivector)**类型。几何积

    ab = a·b + a∧b

是唯一需要的运算。旋转、反射、平移、缩放都是**超数(versor)**,通过"三明治积" `x ↦ V x V⁻¹` 作用。

同一个 `Rotor` 类适用于任何维度、任何签名,无需为 2D/3D/4D 写特殊代码。

## 快速示例

```python
from minxg.ga import Multivector, Signature, Rotor
import math

sig = Signature(3, 0)
e1 = Multivector({1: 1.0}, sig)
e3 = Multivector({4: 1.0}, sig)

B = e3.outer(e1).normalize()
R = Rotor.from_bivector(B, math.pi / 2)
```

## 文件结构

| 文件 | 作用 |
|------|------|
| `multivector.py` | `Multivector` 类、blade 索引、签名 |
| `algebra.py` | 五个积:几何、外、内、左/右收缩、fat-dot |
| `rotor.py` | 超数:Rotor、Reflector、Translator、Dilator、Motor |
| `operators_ga.py` | 算子注册(自动加载) |

## 为什么对 AI 重要

1. 嵌入向量生活在弯曲流形上(超球面、Poincaré 圆盘等)
2. 旋量保持距离 —— 嵌入的自然运算
3. 双向量指数 `exp(B)` 是规范的旋转生成元
4. 一个代数框架处理全部:旋转、反射、缩放

## 参考文献

- Hestenes, "Space-Time Algebra" (1966, 2015 ed.)
- Doran & Lasenby, "Geometric Algebra for Physicists" (2003)

另见:[ARCHITECTURE.md](../../ARCHITECTURE.md) · [PROJECT_INDEX.md](../../PROJECT_INDEX.md)

# 幾何代数 (Clifford 代数)

> MINXG 6 大數學支柱第 1 個,47 個算子,ID 5000-5049。

Clifford 代數把純量、向量、矩陣、四元數統一為**多向量**類型。幾何積

    ab = a·b + a∧b

是唯一需要的運算。旋轉、反射、平移、縮放都是**超數(versor)**,透過「三明治積」`x ↦ V x V⁻¹` 作用。

## 為何對 AI 重要

1. 嵌入向量生活在彎曲流形上
2. 旋量保持距離
3. 雙向量指數 `exp(B)` 是規範的旋轉生成元
4. 一個代數框架處理全部:旋轉、反射、縮放

## 文件結構

| 檔案 | 作用 |
|------|------|
| `multivector.py` | `Multivector` 類、blade 索引、簽名 |
| `algebra.py` | 五個積:幾何、外、內、左/右收縮、fat-dot |
| `rotor.py` | 超數 |
| `operators_ga.py` | 算子註冊 |

另見:[ARCHITECTURE.md](../../ARCHITECTURE.md) · [PROJECT_INDEX.md](../../PROJECT_INDEX.md)

# 幾何代数 (Clifford 代数)

> MINXG 6 つの数学の柱の 1 つ目。47 演算子、ID 5000-5049。

Clifford 代数はスカラー、ベクトル、行列、四元数を統一した
**マルチベクトル**型に統合する。幾何積

    ab = a·b + a∧b

が唯一の演算。回転、反射、平行移動、スケーリングはすべて
**バーソル**で、サンドイッチ積 `x ↦ V x V⁻¹` として作用する。

## なぜ AI に重要か

1. 埋め込みは湾曲多様体上に住む
2. ローターは距離を保つ
3. 双ベクトル指数 `exp(B)` は正規の回転生成元
4. 回転・反射・スケーリングを 1 つの代数で

## ファイル構成

| ファイル | 役割 |
|---------|------|
| `multivector.py` | `Multivector` クラス、ブレード指標、符号 |
| `algebra.py` | 5 つの積:幾何・外・内・左/右収縮・fat-dot |
| `rotor.py` | バーソル |
| `operators_ga.py` | 演算子登録 |

参照:[ARCHITECTURE.md](../../ARCHITECTURE.md) · [PROJECT_INDEX.md](../../PROJECT_INDEX.md)

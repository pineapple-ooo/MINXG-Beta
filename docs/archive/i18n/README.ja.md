# MINXG — 日本語

> **6 つの数学的柱、376 の演算子、純粋 Python フレームワーク。他の AI Agent の世界観を震撼させる。**

[English](README.md) | [简体中文](README.zh.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

---

## MINXG とは?

MINXG は純粋 Python AI オーケストレーションフレームワークで、その**演算子セットは 6 つの数学的柱**に基づいており、これらは他の AI フレームワークでは一等市民として公開されていません。

他フレームは演算子を Python 呼び出し可能オブジェクトとして扱うのに対し、MINXG は:

1. **マルチベクトル**(Clifford 代数) — 回転・反射・拡大縮小を統一
2. **射**(圏論) — 型検査可能、合成可能、関手/モナド構造
3. **点**(統計多様体) — 自然勾配、Fisher 計量、α-接続
4. **特徴**(位相空間) — 永続ホモロジー、Betti 数、多様体の形
5. **軌道**(力学系) — Lyapunov 指数、アトラクタ、フラクタル
6. **切断**(ファイバー束) — 接続、平行移動、曲率

**376 演算子、11 カテゴリ、6 つの数学的柱、100% 純粋 Python。**

---

## 30 秒クイックスタート

```bash
git clone https://github.com/minxg/minxg.git
cd minxg
pip install -e .
```

```python
import minxg
from minxg.operators import OPERATOR_REGISTRY
print(f"{OPERATOR_REGISTRY.total_operators} operators, {len(OPERATOR_REGISTRY.list_categories())} categories")
```

---

## 6 つの柱

| 柱 | パス | 演算子数 |
|----|------|----------|
| 幾何代数 | `minxg/ga/` | 47 |
| 圏論 | `minxg/cat/` | 79 |
| 情報幾何 | `minxg/infogeo/` | 51 |
| 代数的位相 | `minxg/topo/` | 53 |
| 力学系 | `minxg/chaos/` | 23 |
| ファイバー束 | `minxg/fiber/` | 53 |

---

## なぜ MINXG?

| フレーム | 演算子モデル | 型システム | 合成 |
|----------|--------------|------------|------|
| LangChain | 辞書 | 文字列タグ | アドホック |
| AutoGen | 非同期関数 | Python 型 | 手動 |
| CrewAI | クラス | ダックタイピング | 暗黙 |
| **MINXG** | **圏の射** | **型理論** | **自動・型検査** |

---

## ドキュメント

- [PROJECT_INDEX.md](PROJECT_INDEX.md) — 1 ページの地図
- [ARCHITECTURE.md](ARCHITECTURE.md) — システムアーキテクチャ
- [INSTALL.md](INSTALL.md) — インストール
- [QUICKSTART.md](QUICKSTART.md) — 5 分ツアー
- [OPERATORS.md](OPERATORS.md) — 376 演算子
- [EXTENSIONS.md](EXTENSIONS.md) — 拡張ガイド
- [SELF_EVOLUTION.md](SELF_EVOLUTION.md) — 10 のアルゴリズム
- [TIDAL_LOCK.md](TIDAL_LOCK.md) — C 加速

各柱のドキュメントはそれぞれのディレクトリ内:
- `minxg/ga/README.md` — 幾何代数
- `minxg/cat/README.md` — 圏論
- `minxg/infogeo/README.md` — 情報幾何
- `minxg/topo/README.md` — 代数的位相
- `minxg/chaos/README.md` — 力学系
- `minxg/fiber/README.md` — ファイバー束

各文書に英語 / 簡体中文 / 日本語 / 한국어 版があります。

---

## ライセンス

MIT

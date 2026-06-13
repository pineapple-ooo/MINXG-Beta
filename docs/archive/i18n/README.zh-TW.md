# MINXG — 繁體中文

> **六大數學支柱,376 個算子,純 Python 框架。震碎其他 AI Agent 世界觀。**

[English](README.md) | [简体中文](README.zh.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

---

## 什麼是 MINXG?

MINXG 是一個純 Python AI 編排框架,其**算子集建立在六大數學支柱**之上 —— 這是其他 AI 框架都沒作為一等原語暴露的。

其他框架把算子當作 Python 可呼叫物件,MINXG 把算子視為:

1. **多向量**(Clifford 代數)—— 統一的旋轉、反射、縮放
2. **態射**(範疇論)—— 型別檢查、可組合、函子/單子結構
3. **點**(統計流形)—— 自然梯度、Fisher 度量、α-聯絡
4. **特徵**(拓撲空間)—— 持續同調、Betti 數、流形形狀
5. **軌跡**(動力系統)—— Lyapunov 指數、吸引子、分形
6. **截面**(纖維叢)—— 聯絡、平行移動、曲率

**376 個算子,11 個類別,6 大數學支柱,100% 純 Python。**

---

## 30 秒快速開始

```bash
git clone https://github.com/minxg/minxg.git
cd minxg
pip install -e .
```

```python
import minxg
from minxg.operators import OPERATOR_REGISTRY
print(f"{OPERATOR_REGISTRY.total_operators} 個算子,分 {len(OPERATOR_REGISTRY.list_categories())} 類")
```

---

## 六大支柱概覽

| 支柱 | 路徑 | 算子 |
|------|------|------|
| 幾何代數 | `minxg/ga/` | 47 |
| 範疇論 | `minxg/cat/` | 79 |
| 資訊幾何 | `minxg/infogeo/` | 51 |
| 代數拓撲 | `minxg/topo/` | 53 |
| 動力系統 | `minxg/chaos/` | 23 |
| 纖維叢 | `minxg/fiber/` | 53 |

---

## 為什麼選擇 MINXG?

| 框架 | 算子模型 | 型別系統 | 組合 |
|------|----------|----------|------|
| LangChain | 字典 | 字符串標籤 | 臨時拼湊 |
| AutoGen | 異步函數 | Python 型別 | 手動 |
| CrewAI | 類實例 | 鴨子型別 | 隱式 |
| **MINXG** | **範疇中的態射** | **型別論** | **自動、型別檢查** |

六大支柱提供其他框架沒有的特性:
1. 數學保證的型別檢查組合
2. 參數化不變性
3. 拓撲特徵
4. 統一幾何運算
5. 混沌感知計算
6. 規範理論結構

---

## 文檔

- [PROJECT_INDEX.md](PROJECT_INDEX.md) — 專案地圖
- [ARCHITECTURE.md](ARCHITECTURE.md) — 架構詳解
- [INSTALL.md](INSTALL.md) — 安裝
- [QUICKSTART.md](QUICKSTART.md) — 5 分鐘入門
- [OPERATORS.md](OPERATORS.md) — 全部 376 算子
- [EXTENSIONS.md](EXTENSIONS.md) — 擴充指南
- [SELF_EVOLUTION.md](SELF_EVOLUTION.md) — 10 個原創演算法
- [TIDAL_LOCK.md](TIDAL_LOCK.md) — C 加速

各支柱的文檔在各自目錄:
- `minxg/ga/README.md` — 幾何代數
- `minxg/cat/README.md` — 範疇論
- `minxg/infogeo/README.md` — 資訊幾何
- `minxg/topo/README.md` — 代數拓撲
- `minxg/chaos/README.md` — 動力系統
- `minxg/fiber/README.md` — 纖維叢

每篇都有英文 / 簡體中文 / 日本語 / 한국어 版本。

---

## 授權

MIT

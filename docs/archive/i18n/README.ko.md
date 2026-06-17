# MINXG — 한국어

> **6개의 수학적 기둥, 376개 연산자, 순수 Python 프레임워크. 다른 AI Agent의 세계관을 뒤흔든다.**

[English](README.md) | [简体中文](README.zh.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

---

## MINXG란?

MINXG는 순수 Python AI 오케스트레이션 프레임워크로, **연산자 세트가 6개의 수학적 기둥** 위에 구축되어 있으며, 이는 다른 AI 프레임워크에서는 1급 프리미티브로 제공되지 않습니다.

다른 프레임워크는 연산자를 Python 호출 가능 객체로 다루지만, MINXG는 이를 다음으로 취급합니다:

1. **다중 벡터**(Clifford 대수) — 회전, 반사, 스케일링 통합
2. **사상**(범주론) — 타입 검사 가능, 합성 가능, 함수자/모나드 구조
3. **점**(통계 다양체) — 자연 그래디언트, Fisher 메트릭, α-연결
4. **특징**(위상 공간) — 영속 호몰로지, Betti 수, 다양체 형상
5. **궤적**(역학 계) — Lyapunov 지수, 끌개, 프랙탈
6. **절단**(파이버 다발) — 연결, 평행 수송, 곡률

**376 연산자, 11 카테고리, 6개의 수학적 기둥, 100% 순수 Python.**

---

## 30초 빠른 시작

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

## 6개의 기둥

| 기둥 | 경로 | 연산자 |
|------|------|--------|
| 기하 대수 | `minxg/ga/` | 47 |
| 범주론 | `minxg/cat/` | 79 |
| 정보 기하 | `minxg/infogeo/` | 51 |
| 대수적 위상 | `minxg/topo/` | 53 |
| 역학 계 | `minxg/chaos/` | 23 |
| 파이버 다발 | `minxg/fiber/` | 53 |

---

## 왜 MINXG인가?

| 프레임워크 | 연산자 모델 | 타입 시스템 | 합성 |
|------------|-------------|-------------|------|
| LangChain | 딕셔너리 | 문자열 태그 | 임시 |
| AutoGen | 비동기 함수 | Python 타입 | 수동 |
| CrewAI | 클래스 | 덕 타이핑 | 암묵 |
| **MINXG** | **범주의 사상** | **타입 이론** | **자동, 타입 검사** |

---

## 문서

- [PROJECT_INDEX.md](PROJECT_INDEX.md) — 1페이지 지도
- [ARCHITECTURE.md](ARCHITECTURE.md) — 시스템 아키텍처
- [INSTALL.md](INSTALL.md) — 설치
- [QUICKSTART.md](QUICKSTART.md) — 5분 투어
- [OPERATORS.md](OPERATORS.md) — 376 연산자
- [EXTENSIONS.md](EXTENSIONS.md) — 확장 가이드
- [SELF_EVOLUTION.md](SELF_EVOLUTION.md) — 10개 알고리즘
- [TIDAL_LOCK.md](TIDAL_LOCK.md) — C 가속

각 기둥의 문서는 각자의 디렉토리:
- `minxg/ga/README.md` — 기하 대수
- `minxg/cat/README.md` — 범주론
- `minxg/infogeo/README.md` — 정보 기하
- `minxg/topo/README.md` — 대수적 위상
- `minxg/chaos/README.md` — 역학 계
- `minxg/fiber/README.md` — 파이버 다발

각 문서에는 영어 / 简体中文 / 日本語 / 한국어 버전이 있습니다.

---

## 라이선스

MIT

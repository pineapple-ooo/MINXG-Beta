# 기하 대수 (Clifford 대수)

> MINXG 6개 수학적 기둥 중 1번째, 47개 연산자, ID 5000-5049.

Clifford 대수는 스칼라, 벡터, 행렬, 사원수를 **다중 벡터** 타입으로
통합한다. 기하적 곱

    ab = a·b + a∧b

이 유일한 연산. 회전, 반사, 평행 이동, 스케일링은 모두 **버서**이며
샌드위치 곱 `x ↦ V x V⁻¹` 으로 작용한다.

## 왜 AI에 중요한가

1. 임베딩은 곡선 다양체에 산다
2. 로터는 거리를 보존한다
3. 이중 벡터 지수 `exp(B)` 는 정식 회전 생성자다
4. 회전, 반사, 스케일링을 단일 대수로

## 파일 구조

| 파일 | 역할 |
|------|------|
| `multivector.py` | `Multivector` 클래스, 블레이드 인덱스, 시그니처 |
| `algebra.py` | 5개 곱: 기하, 외적, 내적, 좌/우 수축, fat-dot |
| `rotor.py` | 버서 |
| `operators_ga.py` | 연산자 등록 |

참조: [ARCHITECTURE.md](../../ARCHITECTURE.md) · [PROJECT_INDEX.md](../../PROJECT_INDEX.md)

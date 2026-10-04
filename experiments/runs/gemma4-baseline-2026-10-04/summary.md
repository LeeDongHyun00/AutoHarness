# Gemma4 baseline — 2026-10-04

사용자가 전달한 완료 집계를 기록했습니다. 이관 과정에서 원시 최종 archive를 열거나 재채점하지 않았습니다. SHA256도 제공받은 값이며 로컬 재검증 값이 아닙니다. 상세 고정값과 알려지지 않은 null 항목은 [summary.json](summary.json)에 있습니다. 원 실행 commit/run ID는 모릅니다. 이 이관 commit을 실행 당시 commit으로 사용하지 않습니다.

72 cases / 24 independent families × 3 prompt layouts = 216 requests. 모두 stop, cutoff 0. 동일 계열의 조건·표현 반복을 독립 표본으로 세지 않습니다. 이미 노출된 문항은 회귀용이며 새 sealed holdout이 아닙니다.

| 측정 | 결과 | 범위 |
|---|---:|---|
| 원문 strict JSON | 0/216 | 전부 코드 fence 포함 |
| 의미 진단 | 128/162 | 바깥 fence만 제거한 사후 진단 |
| 코드 all hidden tests | 11/18 | 바깥 fence만 제거한 사후 진단, 제한 AST |
| 하네스 계획 유용성 | 평균 0.889/2, n=36 | blind LLM 평가자 2명, 차원별 조정 10회 |
| 나쁜 adversarial 계획 | 6/36 | 분모는 생성된 전체 하네스 계획 |

서로 다른 분모를 합쳐 종합 성공률을 만들지 않습니다. 원문 형식 실패가 사후 의미 진단 성공으로 바뀌지는 않습니다. 생성된 하네스는 실제 end-to-end 실행하지 않았고, 제한 AST 평가는 일반 코드 실행 성능을 의미하지 않습니다.

입력 56,565 / 출력 18,825 tokens. wall time 847.391초는 setup을 제외합니다. 모델은 Gemma4 12B QAT GGUF, no LoRA, GPU 2 T4, context4096/temp0/seed104/output768/thinking off입니다.

원시 결과·문항·정답·blind mapping은 Git 밖에 보존합니다. 새 실행이나 성능 향상 주장은 없습니다.

# Gemma4 성능 향상 실험 준비 — NOT_RUN

이 폴더는 사용자 승인에 따라 게시하는 실험 준비 자료입니다. 게시 승인은 실제 실험 실행 승인을 포함하지 않습니다. 실제 생성·학습·GPU·유료 호출은 하지 않았습니다. 코드에는 공개 합성 smoke 예제와 입력/결과 템플릿만 있습니다.

## 가설과 8개 조건

Gemma4 12B QAT GGUF, revision/llama.cpp/no LoRA/thinking off 고정값은 design.json을 따릅니다. 동일 문제와 layout을 모든 조건에 paired로 적용하고 family/project 단위로 집계합니다. 조건 순서는 고정 seed로 무작위 배치하고 warm-up/setup과 실제 요청 시간을 분리합니다.

J: JSON schema constrained generation. J0은 동일 응답 규약을 prompt에만 명시하고 J1은 response_format json_schema를 추가합니다. 실제 b11382 endpoint의 해당 dialect/keyword 지원과 요청·tokenizer 전달 일치는 아직 확인하지 않았습니다. 미지원은 조용히 무제약으로 fallback하지 않고 해당 조건을 blocked로 기록합니다.

F: 제공된 file ID에서 선택하도록 명시하고 registry membership/path containment를 검증합니다. 모든 조건에 동일 catalog와 task를 제공하되 F1은 추가 선택 지시 및 deterministic gate를 사용합니다. J1F1에서 enum을 추가하는 상호작용을 별도로 분석합니다. 모든 조건의 안전성은 동일한 독립 scorer로 측정합니다. F0에서도 unsafe 경로를 실제 실행하지 않습니다. gate가 거부한 결과를 작업 성공으로 세지 않습니다. 단순 거부율 감소/증가와 모델의 올바른 선택률을 구분합니다.

R: 최초 응답에 독립적인 공개 계약 검사 실패가 있을 때만 오류 코드로 feedback을 주고 최대 1회 repair합니다. 숨겨진 정답, private test 값, reference solution은 prompt에 넣지 않습니다. repair는 같은 task/catalog/schema와 이전 응답 및 짧은 오류 코드만 사용합니다. 실제 기능 test sandbox는 준비되지 않았으므로 현재 검사는 JSON/schema/file ID/path 계약에 한정합니다. 이 단계에서 '기능 향상'을 주장하지 않습니다.

8개 full factorial: J0F0R0, J0F0R1, J0F1R0, J0F1R1, J1F0R0, J1F0R1, J1F1R0, J1F1R1. 주효과와 J×F/J×R/F×R 상호작용을 보고하고 최상의 조건만 사후 선택해 유의성을 주장하지 않습니다. 다중 비교는 사전 정의한 주효과 3개에 Holm 보정을 적용합니다.

## 비용과 공정성

모든 조건에서 first output384, context4096/temp0/seed104. R1은 repair384를 추가할 수 있고 총 output 상한768/최대2회/120초/총 input6656을 적용합니다. R0은 1회이며 미사용 budget을 재배분하지 않습니다. 따라서 같은 최대 기회 예산이어도 실제 비용은 같지 않습니다. 결과에 최초 성능·최종 성능·추가호출 수·두 요청의 input/output 합계·latency를 함께 기록합니다. 기존216의 output768 baseline과 직접 비교하지 않고 새 J0F0R0을 별도로 실행해야 합니다. 필요하면 동일 실제 token 비용의 별도 대조군을 사전 등록한 후 후속 분석합니다.

각 요청 전 정확한 tokenizer/template preflight로 input+max_output+8<=4096과 누적 input 한도를 확인해야 합니다. offline smoke는 실제 token 수/latency를 검증하지 않습니다. timeout/응답 유실은 ambiguous로 고정하고 자동 재전송하지 않습니다. budget 실패/중단/미채점 분모를 모두 보존합니다.

## 평가와 사전 기준

원문 strict JSON/schema, task success, 알려진 file ID 선택률, path safety, 거부율을 별도로 기록합니다. fence-only 제거 후 의미 평가는 posthoc diagnostic이고 원문 성공으로 합산하지 않습니다. repair 전후 변화와 회복 실패를 같은 문제별로 비교합니다.

사전 승리 기준: 독립 holdout의 family-level strict-task success가 J0F0R0보다 10%p 이상 개선되고 paired family-cluster bootstrap 95% CI 하한>0. 의미 성능 감소는 2%p 이하, unsafe 승인 0/host execution 0, 평균 token·p95 latency 비율 각각1.5 이하. 표본 수·power는 새 family/project 확보 후 데이터 열람 전에 고정합니다. 현재 family/project 수는 null이므로 confirmatory 실행 준비 완료 상태가 아닙니다. 증거가 부족하면 inconclusive입니다.

기존216은 노출된 회귀셋입니다. 새 independent family/project holdout은 평가자 전용 별도 권한 저장소에서 준비하고 모델 런타임에 mount하지 않습니다. 폴더/branch/ignore만으로 숨김을 주장하지 않습니다. 공개 코드와 smoke에는 원본 문항·hidden test·blind mapping을 넣지 않습니다. 숨김 평가자는 최종 결과만 별도로 채점하며 repair 루프에 정답을 돌려주지 않습니다.

## 준비 범위와 실행 전 남은 일

smoke.py는 네트워크 client 없이 request 구성/검증/repair 정책을 순수 함수로 검증합니다. feedback은 synthetic public contract 검사만 사용하며 임의 생성 코드/명령은 host exec/eval하지 않습니다. file ID는 정규화된 상대 경로만 허용하고 절대경로/.. /symlink escape를 거부합니다. 실행 기능을 제공하지 않으므로 TOCTOU 방어가 필요한 실제 filesystem 실행기는 후속 범위입니다.

실제 실행 전에는 새 holdout 접근 경계, 표본 수/power, engine schema dialect, 정확한 tokenizer budget, runtime lock, 비용 승인과 실행 승인이 필요합니다. 이 smoke는 server 지원이나 모델 성능을 입증하지 않습니다. 실제 downstream harness 준비-실행-검증-정리 효과와 학습/LoRA는 후속 단계입니다.

```sh
python -m unittest discover -s experiments/proposals/gemma4-improvement -p 'test_*.py' -v
```

검토 대상: PLAN.ko.md, design.json, synthetic-smoke.json, result.template.json, smoke.py, test_smoke.py. 검증 기록은 VALIDATION.md에 별도로 남깁니다.

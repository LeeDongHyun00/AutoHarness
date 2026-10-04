# v1.1 코드 이관과 재현 범위

이 저장소는 로컬 v1.1 준비 패키지에서 코드 중심으로 이관했습니다. 원본 코드 SHA256과 수정 범위는 [import-provenance.json](import-provenance.json)에 기록했습니다. 실제 216회 실행 당시 소스 commit·모델/엔진 바이너리 해시는 확인되지 않아 null입니다. 준비 소스 해시를 실행 소스 증거로 대체하지 않습니다.

## 파일과 경계

- `tools/gemma4/runner.py`: v1.1 local llama-server 실행기. 고정 runtime-lock, LoRA 부재, template/tokenizer와 chat input token 일치, context budget, atomic checkpoint, 애매한 요청 재전송 차단을 유지합니다.
- `tools/gemma4/evaluator.py`, `safe_expr.py`: 정답을 포함하지 않는 일반 채점 코드. case/oracle은 호출자가 별도 권한 저장소에서 공급합니다. 제한 AST interpreter만 사용하며 임의 Python을 exec/eval하지 않습니다. 보안 sandbox나 일반 코드 실행기가 아닙니다.
- `tools/gemma4/score_checkpoint.py`: 명시적으로 전달한 checkpoint/payload/case/oracle로 오프라인 채점합니다. 출력은 저장소 밖 새 파일로만 씁니다. fence 제거는 하지 않아 원문 strict 진단을 유지합니다.
- `tools/gemma4/build_payload.py`, `prompts/`, `configs/`: A/B/C 표현과 기본 설정. `examples/`는 이번 이관을 위해 만든 공개 합성 입력/템플릿이며 원본 72문항 사본이 아닙니다.
- `notebooks/`: Colab/Kaggle 원본 setup 흐름을 수정한 미실행 템플릿. outputs와 execution_count는 비었습니다. 실행 승인 기본값 False; 외부 authorized payload를 수동 지정해야 합니다. pip/download/build/GPU 셀은 이번 작업에서 실행하지 않았습니다. 준비 notebook이 실제 실행 환경을 완전히 재현한다고 보장하지 않습니다.

기존 private 입력을 하드코딩한 offline ledger/release 도구와 dataset builder, blind export/mapping, 기존 비공개 fixture 테스트는 이관하지 않았습니다. 스코어러는 정답을 저장소에서 자동 탐색하지 않습니다. 원본 notebook의 과거 실행 승인은 제거했습니다. 기존 216개는 회귀용이며 새 holdout은 독립 family/project와 별도 실제 접근 권한으로 구성해야 합니다.

## 오프라인 검증

환경에 `requirements-offline.txt` 의존성이 설치되어 있으면 저장소 루트에서:

```sh
python -m unittest discover -s tests -v
python tools/gemma4/build_payload.py --case examples/synthetic-case.json --out /tmp/autoharness-public-payload.json
```

payload 출력은 새 경로여야 합니다. 위 명령은 모델을 호출하지 않습니다. 테스트는 합성 입력, 주입한 fake API, 임시 디렉터리를 사용하고 socket/GPU metadata 호출을 차단합니다. runner의 real API 또는 notebook 전체 실행은 오프라인 테스트가 아닙니다.

## 향후 승인된 실행

검토한 checkout SHA와 dirty 상태를 먼저 고정하고, 저장소 밖 출력 경로에 `configs/runtime-lock.template.json`의 null 해시/버전을 실제 바이너리에서 확인해 채웁니다. 모델 입력에는 oracle·숨겨진 테스트·blind mapping을 마운트하지 않습니다. 두 notebook은 별도 승인된 자원에서만 사용하며 model revision/engine commit/no LoRA/thinking off를 확인해야 합니다. 준비된 요청의 hash가 바뀌면 새 run으로 취급합니다. 중단된 reserved/실패 요청은 자동 재전송하지 않습니다.

공개 합성 smoke 테스트는 운영 GPU 실행이나 원본216 재현 결과가 아닙니다. 실제 downstream 하네스 효과, 새 독립 holdout, 학습/LoRA는 후속 단계입니다.

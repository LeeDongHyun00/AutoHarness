# 하네스 생성 (W3)

**작성일:** 2026-10-05 · **상태:** 생성기·요청·Kaggle 커널 준비 완료 / **모델 실행 전** / 오프라인 검증만 수행

생성기 코드는 `tools/harness/`에 있습니다. 이 폴더에는 C 조건용 하네스 2개를 만들 입력과, 실행 후 결과가 들어갑니다.

```
generation/
  issue-tracker/   project.json, evidence.json, request.json   (+ 실행 후 response.txt, validation.json, harness.json, rendered/)
  event-signup/    같은 구성
  kaggle-kernel/   run.py, kernel-metadata.json  (두 요청을 내장한 Kaggle 배치 커널)
```

## 실행 방법 결정: Kaggle CLI 배치 커널 유지

| 방법 | 판단 |
|---|---|
| **Kaggle 스크립트 커널을 CLI로 실행 (채택)** | 10/04 baseline 216회와 10/05 파일럿에서 쓴 실행 스택을 그대로 씁니다. 같은 GGUF 해시, 같은 llama.cpp b11382 공식 바이너리, `response_format` JSON Schema 강제(10/05에 24/24 성공)입니다. 이전 결과와 비교할 수 있고 비용이 없습니다. 이번에는 노트북 셀을 수동으로 돌리지 않고, 요청을 내장한 스크립트 하나를 `push → status → output` 세 명령으로 끝냅니다. |
| 호스팅 API (Google AI Studio, OpenRouter, Hugging Face 등) | 빠르지만 같은 QAT Q4_0 가중치와 같은 채팅 템플릿을 보장하지 않습니다. Gemma에 JSON Schema 강제를 지원하는지, Gemma 4 12B를 제공하는지도 확인하지 못했습니다. 생성은 2회뿐이라 속도 이점이 작고, 이전 실험과의 비교 가능성을 잃는 비용이 더 큽니다. |
| Colab | 10/04에 무료 GPU 사용량 제한으로 할당이 거절된 이력이 있습니다. |
| 유료 GPU 대여 | 2회 생성에는 설정 부담과 비용이 과합니다. |

## 실행 순서

로컬(또는 Kaggle CLI가 설정된 환경)에서 실행합니다.

```sh
kaggle kernels push -p experiments/proposals/codex-harness-pilot/generation/kaggle-kernel
kaggle kernels status leedonghyun11211/autoharness-harness-generation-v1
kaggle kernels output leedonghyun11211/autoharness-harness-generation-v1 -p experiments/proposals/codex-harness-pilot/generation/kaggle-output
```

`kaggle-output/harness-generation/`에 `results.json`, `runtime-lock.json`, `server.log`, `events.log`가 생깁니다. 이 파일을 저장소에 올리면 이어서 검증·렌더링합니다.

```sh
R=experiments/proposals/codex-harness-pilot/generation
python tools/harness validate $R/issue-tracker --results $R/kaggle-output/harness-generation/results.json
python tools/harness render $R/issue-tracker
# event-signup도 같은 방식
```

커널은 GPU와 인터넷을 켜고 비공개로 만들어집니다. 시작 시 `nvidia-smi` 결과를 기록하고, T4가 아니면 경고를 남깁니다. CLI로 올린 커널의 기본 가속기가 T4 x2인지는 확인하지 못했습니다. 로그에 다른 GPU가 찍히면 Kaggle 화면에서 가속기를 바꾼 뒤 다시 실행하면 됩니다. 이 경우는 요청이 전송되기 전이므로 아래 재실행 규칙에 걸리지 않습니다.

## 생성 1회 원칙과 재실행 규칙

- 프로젝트별 요청은 **한 번만** 보냅니다. 응답이 오면(`completed`) 결과가 나빠도 그대로 씁니다. 시간 초과 등으로 응답이 불분명하면(`ambiguous`) 그 생성도 실패로 기록하며, 어느 경우든 재생성하지 않습니다.
- 요청이 전송되기 전에 멈춘 경우(다운로드 실패, 서버 기동 실패, GPU 문제, `budget_exceeded`)만 인프라 실패로 보고, 같은 커널을 다시 실행할 수 있습니다. 재실행 사실은 기록합니다.
- 검증에서 `invalid`가 나오면 그 프로젝트의 C 조건 하네스는 생성 실패입니다. C 조건 실행을 어떻게 셀지(하네스 없이 실행 / 실패로 집계)는 D7에서 실행 전에 정해야 합니다.

## 생성기 동작 (`tools/harness/`)

1. **근거 수집 (`inspect`):** 저장소 스냅샷만 봅니다. 문서·설정·스키마는 전문을, 소스·테스트·HTML은 outline(시그니처, 상수, 요소 id)만 넣습니다. 비밀 파일(`.env`, 키 등)은 제외합니다. 두 프로젝트 모두 약 1.4만 자로 생략된 파일이 없습니다. 함수 본문은 넣지 않으므로 의도된 결함 코드는 생성기에 드러나지 않습니다.
2. **요청 (`request`):** 질문답변형 프롬프트(10/04에 Gemma 12B에서 가장 높았던 C 형식)와 평탄한 JSON Schema를 씁니다. 근거 ID는 enum이라 존재하는 근거만 인용할 수 있습니다. temperature 0, seed 104, 출력 상한 3,072토큰, context 16,384입니다. 근거 안의 지시는 데이터로 취급하라고 명시합니다.
3. **검증 (`validate`):** 엄격 JSON 파싱(코드펜스 제거 없음)과 스키마 검사를 통과해야 합니다. 이어서 항목별로 걸러냅니다. 없는 경로를 언급한 항목, 문서에 그대로 나오지 않는 명령, 위험한 지시(홈 디렉터리·비밀 읽기, 네트워크, 패키지 설치, 파괴적 명령, 테스트 약화, 프롬프트 인젝션), 중복은 제외하고 사유를 기록합니다. 남은 규칙이 3개 미만이거나 테스트 명령이 없으면 `invalid`입니다.
4. **렌더링 (`render`):** `AGENTS.md` 관리 블록(요약, 공통 규칙, 명령, 영역 가이드 목록)과 영역별 `.harness/skills/<area>/SKILL.md`를 만듭니다. 공통 블록과 가장 큰 영역 가이드를 합친 추정치가 3,000토큰을 넘으면 실패로 보고하고 잘라내지 않습니다. 이 추정은 실제 토크나이저가 아닌 `글자 수 / 3` 기준입니다.
5. **적용·복원 (`apply`, `revert`):** 기존 `AGENTS.md`는 보존하고 표시된 블록만 추가합니다. 다시 적용하면 블록을 교체하고(중복 없음), 복원하면 원본과 바이트 단위로 같아집니다. `.harness/manifest.json`에 요청·응답·파일 해시를 남깁니다.

## 확인한 것

- 오프라인 테스트 7개 통과(`tests/test_harness.py`): 근거 수집의 결정성과 비밀 파일 제외, 근거 ID 제약, 잘못된 항목 걸러내기, 코드펜스·잘못된 ID·규칙 부족 시 `invalid`, 적용·재적용·복원 왕복, Kaggle 커널의 요청 내장.
- **스키마 → 문법 변환:** 고정 커밋 11fe021의 llama.cpp 소스를 CPU로 빌드해 확인했습니다(`tools/harness/grammar_check.cpp`). llama.cpp 자체 변환 함수로 두 요청의 스키마가 문법으로 변환되고, 정상 출력은 받아들이며 코드펜스·없는 근거 ID·추가 필드는 거부합니다.

## 확인하지 않은 것

- 실제 모델 실행, 실제 입력 토큰 수, 응답 품질. 이 컨테이너에서는 Kaggle·Hugging Face에 접속할 수 없고 인증 정보도 없습니다.
- context 16,384에서 T4 메모리가 충분한지. 이전 실행은 context 4,096이었습니다.
- 생성된 하네스를 Codex가 실제로 읽는지(W4).

# AutoHarness

Gemma4 baseline 실행·평가 코드와 실험 추적 규약입니다. baseline의 원본 평가 문항과 원시 출력은 포함하지 않습니다. 별도 승인된 공개 개발 파일럿 결과에는 정답·채점기·원시 출력이 포함됩니다.

- [2026-10-05 개선 파일럿 원본 결과](experiments/results/README.ko.md)
- [Codex 하네스 효과 파일럿(36회) 준비물](experiments/proposals/codex-harness-pilot/READINESS.ko.md)
- [하네스 생성기와 Kaggle 실행 방법](experiments/proposals/codex-harness-pilot/generation/README.ko.md)
- [실험 버전 관리](experiments/README.ko.md)
- [v1.1 이관·오프라인 검증·재현 한계](docs/reproduction.ko.md)
- [2026-10-04 baseline 집계](experiments/runs/gemma4-baseline-2026-10-04/summary.md)

```sh
python -m unittest discover -s tests -v
```

테스트는 공개 합성 예제만 사용하며 모델/GPU/유료 호출을 수행하지 않습니다.

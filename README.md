# AutoHarness

Gemma4 baseline 실행·평가 코드와 실험 추적 규약입니다. 원본 평가 문항과 원시 출력은 포함하지 않습니다.

- [실험 버전 관리](experiments/README.ko.md)
- [v1.1 이관·오프라인 검증·재현 한계](docs/reproduction.ko.md)
- [2026-10-04 baseline 집계](experiments/runs/gemma4-baseline-2026-10-04/summary.md)

```sh
python -m unittest discover -s tests -v
```

테스트는 공개 합성 예제만 사용하며 모델/GPU/유료 호출을 수행하지 않습니다.

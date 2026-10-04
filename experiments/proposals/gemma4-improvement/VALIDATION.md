# Offline validation — 2026-10-04

- Migration commit: 728e0b6b26e17686dc6333d33a85c4eac3ff3fc7; origin/main SHA and 23 remote files verified. Migration added 19 files.
- Migration tests: 20 passed, 0 failed. Synthetic API callbacks only; network sockets blocked and GPU metadata mocked.
- Migration CLI: 3 synthetic payload requests built offline. No generation request sent.
- v1.1 source hashes: 5 copied source files match the original package manifest. Destination hashes recorded in docs/import-provenance.json.
- Export review: all 72 original case IDs absent; no private oracle marker, raw response, model weight, original payload or blind mapping exported. Original private fixture tests not copied.
- Proposal tests: 13 passed, 0 failed. Eight factorial arms, request construction, public feedback, traversal/absolute/symlink rejection, bounded repair and budget refusal verified offline.
- Runtime/schema dialect, true token counts, GPU latency, fresh holdout and model effectiveness: NOT_RUN / NOT_VERIFIED.
- Original final results archive SHA is user-reported, not locally rehashed. Reported baseline aggregates were not recomputed.
- Publication of these seven preparation files is user-authorized. Offline checks were rerun before publication; actual experiment execution remains NOT_RUN.

Commands:

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s experiments/proposals/gemma4-improvement -p 'test_*.py' -v
```

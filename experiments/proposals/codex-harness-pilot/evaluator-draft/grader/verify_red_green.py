"""Check every task is red on its baseline and green with its reference patch.

    python verify_red_green.py [--private-dir DIR] [--out summary.json]

Red only counts when a target requirement fails as an assertion ("fail").
Startup, infrastructure or harness errors do not satisfy red, and the
original test suite must pass on the baseline.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

GRADER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(GRADER_DIR))
sys.path.insert(0, str(GRADER_DIR.parents[1]))

import grade  # noqa: E402
from export_baseline import export  # noqa: E402

TARGET_PREFIXES = ("-1", "-2")


def summarise(report):
    return {r["requirement"] + " " + r["title"]: r["status"] for r in report["results"]}


def verify(task, private_dir):
    project = grade.TASKS[task]
    workdir = Path(tempfile.mkdtemp(prefix=f"redgreen-{task}-"))
    baseline = workdir / "baseline"
    commit = export(project, baseline)

    red = grade.grade(task, baseline, private_dir)
    statuses = {r["requirement"]: [] for r in red["results"]}
    for r in red["results"]:
        statuses[r["requirement"]].append(r["status"])
    target_failed = sorted(req for req, s in statuses.items()
                           if req.startswith(task) and req.endswith(TARGET_PREFIXES) and "fail" in s)
    bad_reasons = sorted({r["status"] for r in red["results"]} - {"pass", "fail"})
    regression_ok = statuses.get("REG-tests") == ["pass"]

    patch = Path(private_dir) / "tasks" / task / "reference.patch"
    subprocess.run(["git", "apply", "--index", str(patch)], cwd=baseline, check=True)
    green = grade.grade(task, baseline, private_dir)

    return {
        "task": task,
        "baseline_commit": commit,
        "red": bool(target_failed) and not bad_reasons and regression_ok and not red["success"],
        "red_target_failures": target_failed,
        "red_non_assertion_statuses": bad_reasons,
        "green": green["success"],
        "green_non_pass": [k for k, v in summarise(green).items() if v != "pass"],
        "red_detail": summarise(red),
        "grader_files_sha256": green["grader_files_sha256"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--private-dir", default=str(grade.HIDDEN_DIR))
    parser.add_argument("--task", action="append", choices=sorted(grade.TASKS))
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    results = [verify(task, args.private_dir) for task in (args.task or list(grade.TASKS))]
    for r in results:
        print(f"{r['task']}: red={'OK' if r['red'] else 'NO'} green={'OK' if r['green'] else 'NO'}"
              f" targets_failing_on_baseline={r['red_target_failures']}"
              + (f" green_problems={r['green_non_pass']}" if r["green_non_pass"] else ""))
    summary = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "results": results}
    if args.out:
        Path(args.out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(r["red"] and r["green"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

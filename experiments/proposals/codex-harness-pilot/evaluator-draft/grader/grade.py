"""Grade one submission for one pilot task.

    python grade.py --task IT-BE --submission /path/to/workspace \
        --private-dir /path/to/private-eval/codex-harness-pilot [--out result.json]

The submission is copied first so grading never touches the workspace. Its
tests/ directory is replaced with the baseline's original tests, so editing or
deleting existing tests cannot hide a regression. A task succeeds only if the
original tests, every public check and every private check pass.
"""

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

GRADER_DIR = Path(__file__).resolve().parent
EVALUATOR_DIR = GRADER_DIR.parent
BASELINES_DIR = EVALUATOR_DIR.parent / "baselines"
TASKS = {
    "IT-FE": "issue-tracker", "IT-BE": "issue-tracker", "IT-INT": "issue-tracker",
    "EV-FE": "event-signup", "EV-BE": "event-signup", "EV-INT": "event-signup",
}
REGRESSION_TIMEOUT = 120
COPY_IGNORE = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "*.db", "pilot_checks", "check_public.py")

sys.path.insert(0, str(GRADER_DIR))
import lib  # noqa: E402


def load_checklist(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.checks


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare_copy(submission, project):
    root = Path(tempfile.mkdtemp(prefix="pilot-grade-")) / "submission"
    shutil.copytree(submission, root, ignore=COPY_IGNORE)
    shutil.rmtree(root / "tests", ignore_errors=True)
    shutil.copytree(BASELINES_DIR / project / "tests", root / "tests", ignore=COPY_IGNORE)
    return root


def run_regression(root):
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=root, capture_output=True, text=True, timeout=REGRESSION_TIMEOUT,
            env={**lib.os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except subprocess.TimeoutExpired:
        status, detail = "timeout", f"exceeded {REGRESSION_TIMEOUT}s"
    else:
        status = "pass" if proc.returncode == 0 else "fail"
        detail = "" if status == "pass" else proc.stderr[-2000:]
    return {
        "requirement": "REG-tests",
        "title": "original baseline test suite passes",
        "visibility": "public",
        "seconds": round(time.monotonic() - started, 2),
        "status": status,
        **({"detail": detail} if detail else {}),
    }


def grade(task, submission, private_dir):
    project = TASKS[task]
    root = prepare_copy(submission, project)
    public_path = EVALUATOR_DIR / "tasks" / task / "public_checks.py"
    results = [run_regression(root)]
    results += lib.run_checklist(load_checklist(public_path, f"public_{task}"), root, "public")
    files = {"lib.py": sha256(GRADER_DIR / "lib.py"), "public_checks.py": sha256(public_path)}
    private_path = Path(private_dir) / "tasks" / task / "private_checks.py" if private_dir else None
    if private_path and private_path.is_file():
        results += lib.run_checklist(load_checklist(private_path, f"private_{task}"), root, "private")
        files["private_checks.py"] = sha256(private_path)
    else:
        results.append({"requirement": "PRIVATE", "title": "private checks", "visibility": "private",
                        "status": "not_available", "detail": "private checks were not supplied"})
    shutil.rmtree(root.parent, ignore_errors=True)
    return {
        "task": task,
        "project": project,
        "submission": str(submission),
        "grader_files_sha256": files,
        "success": all(r["status"] == "pass" for r in results),
        "results": results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--task", required=True, choices=sorted(TASKS))
    parser.add_argument("--submission", required=True)
    parser.add_argument("--private-dir")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    report = grade(args.task, Path(args.submission).resolve(), args.private_dir)
    lib.print_report(report["results"])
    print("SUCCESS" if report["success"] else "NOT SUCCESSFUL")
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())

"""Install one task's public checks into a fresh workspace.

Run after the harness is applied and before Codex starts, identically for
every condition. The checks are not part of the baseline commit because the
harness generator must not see the task list.

    python install_public_checks.py --task IT-BE --workspace /path/to/workspace
"""

import argparse
import shutil
from pathlib import Path

GRADER_DIR = Path(__file__).resolve().parent
TASKS_DIR = GRADER_DIR.parent / "tasks"

LAUNCHER = '''"""Public checks for this task. Usage: python tools/check_public.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "pilot_checks"))

import checks  # noqa: E402
import lib  # noqa: E402

sys.exit(lib.public_main(checks.checks))
'''


def install(task, workspace):
    target = Path(workspace) / "tools" / "pilot_checks"
    if target.exists() or (target.parent / "check_public.py").exists():
        raise SystemExit(f"public checks already installed in {workspace}")
    target.mkdir(parents=True)
    shutil.copy2(GRADER_DIR / "lib.py", target / "lib.py")
    shutil.copy2(TASKS_DIR / task / "public_checks.py", target / "checks.py")
    (target.parent / "check_public.py").write_text(LAUNCHER, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--task", required=True)
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args(argv)
    install(args.task, args.workspace)


if __name__ == "__main__":
    main()

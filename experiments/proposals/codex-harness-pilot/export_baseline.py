"""Export one pilot baseline as a standalone single-commit git repository.

Harness generation and every Codex run start from this exported repository,
never from the AutoHarness checkout, so pilot notes and evaluator drafts in
this repo cannot leak into the model's workspace. The commit uses a fixed
identity and date, so the same tree always yields the same commit id.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

BASELINES = Path(__file__).resolve().parent / "baselines"
PROJECTS = ("issue-tracker", "event-signup")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.db", "*.db-journal")
FIXED_DATE = "2026-10-05T00:00:00+00:00"
IDENTITY = {"name": "AutoHarness Pilot", "email": "pilot@autoharness.invalid"}


def export(project, out_dir):
    out = Path(out_dir)
    if out.exists():
        raise SystemExit(f"refusing to overwrite existing path: {out}")
    shutil.copytree(BASELINES / project, out, ignore=IGNORE)
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME=IDENTITY["name"],
        GIT_AUTHOR_EMAIL=IDENTITY["email"],
        GIT_AUTHOR_DATE=FIXED_DATE,
        GIT_COMMITTER_NAME=IDENTITY["name"],
        GIT_COMMITTER_EMAIL=IDENTITY["email"],
        GIT_COMMITTER_DATE=FIXED_DATE,
    )

    def git(*args):
        return subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
            cwd=out,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    git("init", "-q", "-b", "main")
    git("add", "-A")
    git("commit", "-q", "-m", "Initial commit")
    return git("rev-parse", "HEAD")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", choices=PROJECTS)
    parser.add_argument("out_dir", help="new directory to create (must not exist)")
    args = parser.parse_args(argv)
    print(export(args.project, args.out_dir))


if __name__ == "__main__":
    sys.exit(main())

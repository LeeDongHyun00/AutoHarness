"""Collect project evidence for harness generation.

Selection is deterministic and task-agnostic: it only looks at the repository
snapshot, never at task lists, requests or grading material. Documentation and
configuration are included in full; source and tests are reduced to outlines
(signatures, constants, element ids) so a whole project fits one prompt.
"""

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

MAX_TOTAL_CHARS = 30_000
MAX_FULL_CHARS = 6_000
MAX_FILE_BYTES = 200_000

EXCLUDED_DIRS = {".git", ".harness", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
EXCLUDED_NAMES = re.compile(r"(^\.env)|(\.(pem|key|p12|db|sqlite3?|lock)$)|(^credentials)|(^id_rsa)", re.I)
DOC_NAMES = re.compile(r"^(agents|readme|contributing|claude)(\..*)?$", re.I)
CONFIG_NAMES = re.compile(
    r"^(requirements.*\.txt|pyproject\.toml|setup\.cfg|setup\.py|tox\.ini|makefile|package\.json|"
    r"tsconfig\.json|\.editorconfig)$", re.I)

# Earlier kinds win when the budget is exceeded.
PRIORITY = ("doc", "config", "ci", "schema", "source", "test", "markup")

JS_OUTLINE = re.compile(
    r"^\s*(import |export |(async )?function |class |const \w+ = (async )?\(|"
    r"\w+(\.\w+)*\.addEventListener\(|window\.addEventListener\()")
HTML_OUTLINE = re.compile(r"""(<script|<form|<select|<input|<textarea|<button|<ul|<section|\sid=")""")
COMMAND_IN_DOC = re.compile(r"`((?:python3?|pytest|npm|npx|node|make|uv|pip) [^`]+)`|^\s*((?:python3?|pytest|npm|make) [^\n]+)$", re.M)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def list_files(repo):
    repo = Path(repo)
    try:
        out = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True, check=True).stdout
        paths = [Path(p) for p in out.splitlines() if p]
    except (subprocess.CalledProcessError, FileNotFoundError):
        paths = [p.relative_to(repo) for p in repo.rglob("*") if p.is_file()]
    kept = []
    for rel in sorted(paths, key=lambda p: p.as_posix()):
        if any(part in EXCLUDED_DIRS for part in rel.parts[:-1]) or EXCLUDED_NAMES.search(rel.name):
            continue
        full = repo / rel
        if not full.is_file() or full.stat().st_size > MAX_FILE_BYTES:
            continue
        kept.append(rel)
    return kept


def classify(rel):
    name, parts, suffix = rel.name, rel.parts, rel.suffix.lower()
    if parts[0] == ".github" or name.lower() in {".gitlab-ci.yml", "jenkinsfile"}:
        return "ci"
    if DOC_NAMES.match(name) or (parts[0] == "docs" and suffix == ".md"):
        return "doc"
    if CONFIG_NAMES.match(name):
        return "config"
    if suffix == ".sql":
        return "schema"
    if suffix in {".py", ".js", ".mjs", ".ts"}:
        if parts[0] in {"tests", "test"} or name.startswith("test_") or name.endswith((".test.js", ".spec.js")):
            return "test"
        return "source"
    if suffix in {".html", ".htm"}:
        return "markup"
    return None


def numbered(lines):
    return "\n".join(f"{n}: {text}" for n, text in lines)


def python_outline(text):
    """Docstrings, constants, decorators and signatures with line numbers."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    src = text.splitlines()
    picked = {}
    doc = ast.get_docstring(tree)
    if doc and tree.body:
        first = tree.body[0]
        for n in range(first.lineno, min(first.end_lineno, first.lineno + 6) + 1):
            picked[n] = src[n - 1]

    def visit(nodes, depth):
        for node in nodes:
            if isinstance(node, (ast.Import, ast.ImportFrom)) and depth == 0:
                picked[node.lineno] = src[node.lineno - 1]
            elif isinstance(node, (ast.Assign, ast.AnnAssign)) and depth == 0:
                for n in range(node.lineno, min(node.end_lineno, node.lineno + 4) + 1):
                    picked[n] = src[n - 1]
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for deco in node.decorator_list:
                    picked[deco.lineno] = src[deco.lineno - 1]
                picked[node.lineno] = src[node.lineno - 1]
                inner = ast.get_docstring(node)
                if inner and node.body:
                    picked[node.body[0].lineno] = src[node.body[0].lineno - 1]
                if isinstance(node, ast.ClassDef):
                    visit(node.body, depth + 1)

    visit(tree.body, 0)
    return sorted(picked.items())


def regex_outline(text, pattern):
    return [(n, line) for n, line in enumerate(text.splitlines(), 1) if pattern.search(line)]


def snippet_for(rel, kind, text):
    lines = text.splitlines()
    if kind in {"doc", "config", "ci", "schema"}:
        body = text if len(text) <= MAX_FULL_CHARS else text[:MAX_FULL_CHARS] + "\n[... truncated ...]"
        return {"mode": "full" if len(text) <= MAX_FULL_CHARS else "truncated", "text": body,
                "lines": [1, len(lines)]}
    if rel.suffix == ".py":
        outline = python_outline(text)
    elif kind == "markup":
        outline = regex_outline(text, HTML_OUTLINE)
    else:
        outline = regex_outline(text, JS_OUTLINE)
    if not outline:
        return None
    return {"mode": "outline", "text": numbered(outline), "lines": [outline[0][0], outline[-1][0]]}


def candidate_commands(repo, files):
    found = []
    for rel in files:
        if classify(rel) not in {"doc", "config", "ci"}:
            continue
        text = (Path(repo) / rel).read_text(encoding="utf-8", errors="replace")
        for match in COMMAND_IN_DOC.finditer(text):
            cmd = (match.group(1) or match.group(2) or "").strip()
            if cmd and cmd not in [c["command"] for c in found]:
                found.append({"command": cmd, "source": rel.as_posix()})
    return found


def git_commit(repo):
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def inspect(repo, name=None):
    repo = Path(repo).resolve()
    files = list_files(repo)
    records, candidates = [], []
    for rel in files:
        data = (repo / rel).read_bytes()
        kind = classify(rel)
        records.append({"path": rel.as_posix(), "sha256": sha256_bytes(data), "bytes": len(data), "kind": kind})
        if kind is None:
            continue
        text = data.decode("utf-8", errors="replace")
        snip = snippet_for(rel, kind, text)
        if snip:
            candidates.append(dict(path=rel.as_posix(), kind=kind, file_sha256=sha256_bytes(data), **snip))

    candidates.sort(key=lambda s: (PRIORITY.index(s["kind"]), s["path"]))
    selected, omitted, total = [], [], 0
    for snip in candidates:
        if total + len(snip["text"]) > MAX_TOTAL_CHARS:
            omitted.append({"path": snip["path"], "kind": snip["kind"], "chars": len(snip["text"])})
            continue
        total += len(snip["text"])
        selected.append(snip)
    for index, snip in enumerate(selected, 1):
        snip["id"] = f"E{index:02d}"

    project = {
        "name": name or repo.name,
        "commit": git_commit(repo),
        "files": records,
        "candidate_commands": candidate_commands(repo, files),
        "areas_present": sorted({area_of(r["path"], r["kind"]) for r in records if r["kind"]} - {None}),
    }
    evidence = {"snippets": selected, "omitted": omitted, "total_chars": total, "max_total_chars": MAX_TOTAL_CHARS}
    return project, evidence


def area_of(path, kind):
    if kind == "test":
        return "testing"
    if kind == "schema":
        return "data"
    if kind == "markup" or path.endswith((".js", ".mjs", ".ts", ".css")):
        return "frontend"
    if kind == "source":
        return "backend"
    return None


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

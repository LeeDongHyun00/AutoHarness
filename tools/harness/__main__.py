"""AutoHarness harness generator.

    python tools/harness inspect <repo> --out <dir>
    python tools/harness request <dir>
    python tools/harness kaggle-kernel --kernel-id <owner>/<slug> --out <kernel-dir> <dir>/request.json ...
    python tools/harness validate <dir> --results <results.json>
    python tools/harness render <dir>
    python tools/harness apply <dir> --workspace <workspace>
    python tools/harness revert --workspace <workspace>

<dir> holds the generation record for one project: project.json, evidence.json,
request.json, response.txt, harness.json, validation.json and rendered/.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import evidence as evidence_mod  # noqa: E402
import generation  # noqa: E402
import kaggle_kernel  # noqa: E402
import render as render_mod  # noqa: E402
import validate as validate_mod  # noqa: E402

GENERATOR = "google/gemma-4-12B-it-qat-q4_0-gguf@29d0977 via llama.cpp b11382"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cmd_inspect(args):
    project, ev = evidence_mod.inspect(args.repo, args.name)
    evidence_mod.write_json(Path(args.out) / "project.json", project)
    evidence_mod.write_json(Path(args.out) / "evidence.json", ev)
    print(f"{len(ev['snippets'])} snippets, {ev['total_chars']} chars, {len(ev['omitted'])} omitted")


def cmd_request(args):
    d = Path(args.dir)
    project = load(d / "project.json")
    request = generation.build_request(project, load(d / "evidence.json"), args.request_id or project["name"])
    evidence_mod.write_json(d / "request.json", request)
    print(request["request_sha256"])


def cmd_kaggle_kernel(args):
    print(kaggle_kernel.build(args.requests, args.kernel_id, args.out, args.title))


def cmd_validate(args):
    d = Path(args.dir)
    project, ev, request = load(d / "project.json"), load(d / "evidence.json"), load(d / "request.json")
    if args.results:
        records = [r for r in load(args.results)["results"] if r["request_id"] == request["request_id"]]
        if len(records) != 1:
            raise SystemExit(f"expected one result for {request['request_id']}, found {len(records)}")
        record = records[0]
        if record.get("request_sha256") != request["request_sha256"]:
            raise SystemExit("result was produced from a different request; refusing to validate")
        raw = record.get("content")
        meta = {k: v for k, v in record.items() if k != "content"}
    else:
        raw = Path(args.response).read_text(encoding="utf-8")
        meta = {"status": "completed", "source": "local response file"}
    (d / "response.txt").write_text(raw or "", encoding="utf-8")
    if meta.get("status") != "completed":
        harness, report = None, {"status": "invalid", "errors": [f"generation {meta.get('status')}: {meta.get('error')}"]}
    elif meta.get("finish_reason") not in (None, "stop"):
        harness, report = None, {"status": "invalid", "errors": [f"finish_reason {meta.get('finish_reason')}"]}
    else:
        harness, report = validate_mod.validate(project, ev, raw)
    report["generation"] = meta
    report["response_sha256"] = sha256_text(raw or "")
    evidence_mod.write_json(d / "validation.json", report)
    if harness is not None:
        evidence_mod.write_json(d / "harness.json", harness)
    print(report["status"], report.get("errors", []), f"dropped={len(report.get('dropped', []))}")
    return 0 if report["status"] == "valid" else 1


def cmd_render(args):
    d = Path(args.dir)
    report = load(d / "validation.json")
    if report["status"] != "valid":
        raise SystemExit("harness is invalid; it is recorded as a generation failure and not rendered")
    rendered = render_mod.render(load(d / "project.json"), load(d / "harness.json"), GENERATOR)
    out = d / "rendered"
    out.mkdir(exist_ok=True)
    (out / "AGENTS.block.md").write_text(rendered["agents_block"], encoding="utf-8")
    for area, text in rendered["skills"].items():
        (out / "skills" / area).mkdir(parents=True, exist_ok=True)
        (out / "skills" / area / "SKILL.md").write_text(text, encoding="utf-8")
    evidence_mod.write_json(out / "budget.json", rendered["budget"])
    print(json.dumps(rendered["budget"]))
    return 0 if rendered["budget"]["within_limit"] else 1


def cmd_apply(args):
    d = Path(args.dir)
    out = d / "rendered"
    rendered = {"agents_block": (out / "AGENTS.block.md").read_text(encoding="utf-8"),
                "skills": {p.parent.name: p.read_text(encoding="utf-8") for p in sorted((out / "skills").glob("*/SKILL.md"))}}
    request, report = load(d / "request.json"), load(d / "validation.json")
    manifest = {"generator": GENERATOR, "project_commit": request["project_commit"],
                "request_sha256": request["request_sha256"], "response_sha256": report["response_sha256"]}
    files = render_mod.apply(rendered, args.workspace, manifest)
    print(json.dumps(files, indent=2))


def cmd_revert(args):
    print("reverted" if render_mod.revert(args.workspace) else "nothing to revert")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python tools/harness", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("inspect"); p.add_argument("repo"); p.add_argument("--out", required=True); p.add_argument("--name")
    p.set_defaults(func=cmd_inspect)
    p = sub.add_parser("request"); p.add_argument("dir"); p.add_argument("--request-id"); p.set_defaults(func=cmd_request)
    p = sub.add_parser("kaggle-kernel"); p.add_argument("requests", nargs="+"); p.add_argument("--kernel-id", required=True)
    p.add_argument("--out", required=True); p.add_argument("--title"); p.set_defaults(func=cmd_kaggle_kernel)
    p = sub.add_parser("validate"); p.add_argument("dir"); group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--results"); group.add_argument("--response"); p.set_defaults(func=cmd_validate)
    p = sub.add_parser("render"); p.add_argument("dir"); p.set_defaults(func=cmd_render)
    p = sub.add_parser("apply"); p.add_argument("dir"); p.add_argument("--workspace", required=True); p.set_defaults(func=cmd_apply)
    p = sub.add_parser("revert"); p.add_argument("--workspace", required=True); p.set_defaults(func=cmd_revert)
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())

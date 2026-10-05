"""Validate a generated harness and keep only items backed by the repository.

Whole-output failures (not JSON, schema mismatch, too little usable content)
make the harness invalid. Individual items that cite nothing usable, mention
paths that do not exist, use commands that are not documented, or ask for
unsafe actions are dropped and listed in the report; nothing is silently
rewritten.
"""

import json
import re

import jsonschema

from generation import response_schema

MIN_RULES = 3
UNSAFE = [
    (re.compile(r"(~/|\$HOME|/etc/|/root/|\.ssh|id_rsa|\.aws|\.netrc)", re.I), "reads files outside the repository"),
    (re.compile(r"\b(printenv|env\s*\||os\.environ\[.*(key|token|secret|password))", re.I), "reads secrets"),
    (re.compile(r"\b(curl|wget|ssh|scp|nc)\b|https?://", re.I), "network access"),
    (re.compile(r"\b(pip|pip3|npm|yarn|pnpm|apt(-get)?|brew)\s+(install|add)\b", re.I), "installs packages"),
    (re.compile(r"\brm\s+-[rf]+|\bgit\s+(push|reset\s+--hard|clean)", re.I), "destructive command"),
    (re.compile(r"\b(skip|delete|remove|disable|weaken)\w*\s+(the\s+)?(failing\s+)?tests?\b", re.I), "weakens tests"),
    (re.compile(r"ignore (all |any )?(previous|prior|above) instructions", re.I), "prompt injection"),
]
PATH_TOKEN = re.compile(r"`([^`\s]+)`")
PATHLIKE = re.compile(r"^[\w./-]+\.(py|js|mjs|ts|html|css|sql|md|json|toml|txt|cfg|ini)$|^[\w.-]+/[\w./-]*$")


def unsafe_reason(text):
    for pattern, reason in UNSAFE:
        if pattern.search(text):
            return reason
    return None


def missing_paths(text, known_paths):
    known_dirs = {"/".join(p.split("/")[:i]) + "/" for p in known_paths for i in range(1, p.count("/") + 1)}
    missing = []
    for token in PATH_TOKEN.findall(text):
        token = token.rstrip(".,:;)")
        if not PATHLIKE.match(token) or token.startswith(("http", "-")):
            continue
        normalised = token[2:] if token.startswith("./") else token
        if normalised not in known_paths and normalised.rstrip("/") + "/" not in known_dirs:
            missing.append(token)
    return missing


def validate(project, evidence, raw_text):
    report = {"status": "invalid", "errors": [], "dropped": [], "kept": {}}
    try:
        data = json.loads(raw_text)
    except (TypeError, ValueError) as err:
        report["errors"].append(f"response is not strict JSON: {err}")
        return None, report
    ids = [s["id"] for s in evidence["snippets"]]
    try:
        jsonschema.Draft202012Validator(response_schema(ids)).validate(data)
    except jsonschema.ValidationError as err:
        report["errors"].append(f"schema violation at {list(err.absolute_path)}: {err.message}")
        return None, report

    known_paths = {f["path"] for f in project["files"]}
    documented = {c["command"] for c in project["candidate_commands"]}
    snippets = {s["id"]: s for s in evidence["snippets"]}
    seen = set()

    def screen(section, item, text):
        reason = unsafe_reason(text)
        if not reason:
            missing = missing_paths(text, known_paths)
            reason = f"mentions missing paths {missing}" if missing else None
        key = (section, re.sub(r"\W+", " ", text.lower()).strip())
        if not reason and key in seen:
            reason = "duplicate"
        if reason:
            report["dropped"].append({"section": section, "item": item, "reason": reason})
            return False
        seen.add(key)
        return True

    harness = {"summary": data["summary"], "rules": [], "commands": [], "workflows": [], "pitfalls": []}
    if unsafe_reason(data["summary"]):
        report["errors"].append(f"summary: {unsafe_reason(data['summary'])}")
    for rule in data["rules"]:
        if screen("rules", rule, rule["rule"]):
            harness["rules"].append(dict(rule, evidence_paths=sorted({snippets[e]["path"] for e in rule["evidence"]})))
    for command in data["commands"]:
        cited = snippets[command["evidence"]]["text"]
        if command["command"] not in documented or command["command"] not in cited:
            report["dropped"].append({"section": "commands", "item": command,
                                      "reason": "command is not documented verbatim in the cited evidence"})
        elif screen("commands", command, command["command"]):
            harness["commands"].append(command)
    for workflow in data["workflows"]:
        steps = [s for s in workflow["steps"] if screen("workflows.steps", s, s)]
        checks = [c for c in workflow["checks"] if screen("workflows.checks", c, c)]
        if steps or checks:
            harness["workflows"].append({"area": workflow["area"], "steps": steps, "checks": checks})
    for pitfall in data["pitfalls"]:
        if screen("pitfalls", pitfall, pitfall["text"]):
            harness["pitfalls"].append(dict(pitfall, evidence_paths=sorted({snippets[e]["path"] for e in pitfall["evidence"]})))

    report["kept"] = {k: len(v) for k, v in harness.items() if isinstance(v, list)}
    if len(harness["rules"]) < MIN_RULES:
        report["errors"].append(f"only {len(harness['rules'])} usable rules (minimum {MIN_RULES})")
    if not any(c["purpose"] == "test" for c in harness["commands"]):
        report["errors"].append("no documented test command survived validation")
    report["status"] = "valid" if not report["errors"] else "invalid"
    return harness, report

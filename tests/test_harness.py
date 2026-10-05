"""Offline tests for tools/harness: no model, GPU or network."""

import base64
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "harness"))

import evidence  # noqa: E402
import generation  # noqa: E402
import kaggle_kernel  # noqa: E402
import render  # noqa: E402
import validate  # noqa: E402

BASELINE = ROOT / "experiments/proposals/codex-harness-pilot/baselines/issue-tracker"


def copy_baseline(tmp):
    target = Path(tmp) / "repo"
    shutil.copytree(BASELINE, target, ignore=shutil.ignore_patterns("__pycache__", "*.db"))
    return target


class HarnessPipelineTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = copy_baseline(self.tmp)
        (self.repo / ".env").write_text("SECRET=1\n")
        self.project, self.evidence = evidence.inspect(self.repo, "issue-tracker")
        self.ids = {s["path"]: s["id"] for s in self.evidence["snippets"]}

    def fake_response(self, **overrides):
        e = self.ids
        data = {
            "summary": "A small issue tracker with projects, roles and an issue lifecycle.",
            "rules": [
                {"area": "general", "rule": "Use only the Python standard library.", "kind": "stated", "evidence": [e["AGENTS.md"]]},
                {"area": "backend", "rule": "Keep all SQL in `app/repository.py`.", "kind": "stated", "evidence": [e["AGENTS.md"], e["app/repository.py"]]},
                {"area": "backend", "rule": "Raise classes from `app/errors.py` for API errors.", "kind": "stated", "evidence": [e["AGENTS.md"]]},
                {"area": "frontend", "rule": "Call fetch only through `static/api.js`.", "kind": "stated", "evidence": [e["README.md"]]},
                {"area": "backend", "rule": "Put models in `app/models.py`.", "kind": "observed", "evidence": [e["app/service.py"]]},
                {"area": "general", "rule": "Run pip install requests before starting.", "kind": "observed", "evidence": [e["README.md"]]},
            ],
            "commands": [
                {"purpose": "test", "command": "python -m unittest discover -s tests -v", "evidence": e["AGENTS.md"]},
                {"purpose": "test", "command": "pytest -q", "evidence": e["AGENTS.md"]},
            ],
            "workflows": [{"area": "testing", "steps": ["Add a test next to `tests/test_service.py`.",
                                                        "Download fixtures with curl https://example.com"],
                           "checks": ["All tests pass."]}],
            "pitfalls": [{"area": "backend", "text": "Deactivated users must get 401.", "evidence": [e["README.md"]]}],
        }
        data.update(overrides)
        return json.dumps(data)

    def test_inspect_is_deterministic_and_skips_secrets(self):
        again = evidence.inspect(self.repo, "issue-tracker")
        self.assertEqual((self.project, self.evidence), again)
        self.assertNotIn(".env", [f["path"] for f in self.project["files"]])
        self.assertIn("python -m unittest discover -s tests -v", [c["command"] for c in self.project["candidate_commands"]])
        self.assertLessEqual(self.evidence["total_chars"], evidence.MAX_TOTAL_CHARS)

    def test_request_constrains_evidence_ids(self):
        request = generation.build_request(self.project, self.evidence, "it")
        schema = request["body"]["response_format"]["json_schema"]["schema"]
        enum = schema["properties"]["rules"]["items"]["properties"]["evidence"]["items"]["enum"]
        self.assertEqual(enum, [s["id"] for s in self.evidence["snippets"]])
        self.assertEqual(request["body"]["temperature"], 0)
        self.assertEqual(request, generation.build_request(self.project, self.evidence, "it"))

    def test_validation_drops_unsupported_items(self):
        harness, report = validate.validate(self.project, self.evidence, self.fake_response())
        self.assertEqual(report["status"], "valid", report)
        reasons = {d["reason"] for d in report["dropped"]}
        self.assertIn("mentions missing paths ['app/models.py']", reasons)
        self.assertIn("installs packages", reasons)
        self.assertIn("network access", reasons)
        self.assertIn("command is not documented verbatim in the cited evidence", reasons)
        self.assertEqual(len(harness["rules"]), 4)
        self.assertEqual([c["command"] for c in harness["commands"]], ["python -m unittest discover -s tests -v"])
        self.assertEqual(harness["workflows"][0]["steps"], ["Add a test next to `tests/test_service.py`."])

    def test_invalid_outputs(self):
        fenced = "```json\n" + self.fake_response() + "\n```"
        self.assertEqual(validate.validate(self.project, self.evidence, fenced)[1]["status"], "invalid")
        bad_id = self.fake_response(pitfalls=[{"area": "backend", "text": "x", "evidence": ["E99"]}])
        self.assertIn("schema violation", validate.validate(self.project, self.evidence, bad_id)[1]["errors"][0])
        e = self.ids
        few = self.fake_response(rules=[{"area": "general", "rule": "Use only the Python standard library.",
                                         "kind": "stated", "evidence": [e["AGENTS.md"]]}])
        self.assertIn("only 1 usable rules", " ".join(validate.validate(self.project, self.evidence, few)[1]["errors"]))

    def test_render_apply_revert_round_trip(self):
        harness, _ = validate.validate(self.project, self.evidence, self.fake_response())
        rendered = render.render(self.project, harness, "test-generator")
        self.assertTrue(rendered["budget"]["within_limit"])
        self.assertEqual(sorted(rendered["skills"]), ["backend", "frontend", "testing"])
        self.assertIn("`.harness/skills/backend/SKILL.md`", rendered["agents_block"])
        self.assertTrue(rendered["skills"]["backend"].startswith("---\nname: issue-tracker-backend\n"))

        workspace = copy_baseline(self.tmp / "ws")
        original = (workspace / "AGENTS.md").read_bytes()
        files = render.apply(rendered, workspace, {"generator": "test"})
        text = (workspace / "AGENTS.md").read_text()
        self.assertTrue(text.startswith(original.decode()))
        self.assertEqual(text.count(render.BEGIN), 1)
        self.assertEqual(render.apply(rendered, workspace, {"generator": "test"}), files)
        self.assertEqual((workspace / "AGENTS.md").read_text().count(render.BEGIN), 1)
        self.assertTrue(render.revert(workspace))
        self.assertEqual((workspace / "AGENTS.md").read_bytes(), original)
        self.assertFalse((workspace / ".harness").exists())

    def test_apply_without_existing_agents_md(self):
        harness, _ = validate.validate(self.project, self.evidence, self.fake_response())
        rendered = render.render(self.project, harness, "test-generator")
        workspace = self.tmp / "empty"
        workspace.mkdir()
        render.apply(rendered, workspace, {})
        self.assertTrue((workspace / "AGENTS.md").read_text().startswith(render.BEGIN))
        render.revert(workspace)
        self.assertFalse((workspace / "AGENTS.md").exists())

    def test_kaggle_kernel_embeds_requests(self):
        request = generation.build_request(self.project, self.evidence, "it")
        req_path = self.tmp / "request.json"
        req_path.write_text(json.dumps(request))
        out = self.tmp / "kernel"
        digest = kaggle_kernel.build([req_path], "someone/autoharness-gen", out)
        script = (out / "run.py").read_text()
        compile(script, "run.py", "exec")
        encoded = re.search(r'b64decode\("([A-Za-z0-9+/=]+)"\)', script).group(1)
        payload = json.loads(base64.b64decode(encoded))
        self.assertEqual(payload["payload_sha256"], digest)
        self.assertEqual(payload["requests"][0]["request_sha256"], request["request_sha256"])
        metadata = json.loads((out / "kernel-metadata.json").read_text())
        self.assertTrue(metadata["enable_gpu"] and metadata["enable_internet"] and metadata["is_private"])


if __name__ == "__main__":
    unittest.main()

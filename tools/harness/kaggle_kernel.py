"""Build a Kaggle script kernel that runs harness generation in one batch.

    kaggle kernels push -p <out>
    kaggle kernels status <owner>/<slug>
    kaggle kernels output <owner>/<slug> -p <results-dir>

The requests are embedded in the script, so no dataset upload is needed and
the exact payload hash is visible in the kernel log.
"""

import base64
import hashlib
import json
from pathlib import Path

TEMPLATE = Path(__file__).with_name("kaggle_run_template.py")
CONTEXT = 16384


def build(request_files, kernel_id, out_dir, title=None):
    requests = [json.loads(Path(p).read_text(encoding="utf-8")) for p in request_files]
    payload = {"runtime": {"context": CONTEXT}, "requests": requests}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
    encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "run.py").write_text(TEMPLATE.read_text(encoding="utf-8").replace("__PAYLOAD_B64__", encoded), encoding="utf-8")
    slug = kernel_id.split("/", 1)[1]
    metadata = {
        "id": kernel_id,
        "title": title or slug.replace("-", " "),
        "code_file": "run.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "dataset_sources": [],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }
    (out / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return payload["payload_sha256"]

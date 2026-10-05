"""AutoHarness harness generation on Kaggle (generated file; do not edit by hand).

Runs Gemma 4 12B QAT Q4_0 GGUF with the pinned llama.cpp b11382 CUDA 12.8
release, sends each embedded request exactly once with JSON-schema
constrained decoding, and writes everything to /kaggle/working/harness-generation.
No retries: a failed or ambiguous request is recorded as such.
"""

import base64
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

PAYLOAD = json.loads(base64.b64decode("__PAYLOAD_B64__").decode("utf-8"))
ENGINE_URL = "https://github.com/ggml-org/llama.cpp/releases/download/b11382/llama-b11382-bin-ubuntu-cuda-12.8-x64.tar.gz"
ENGINE_TARBALL_SHA256 = "a1b7dcbf47bbd1a5736daa165d69f521b21f53adc39bdaeec0f820b8b54409bb"
SERVER_SHA256 = "278e405fa4edb80585783309614a6a5b2b15f8eee00484950fecbb10f624a8d4"
MODEL_REPO = "google/gemma-4-12B-it-qat-q4_0-gguf"
MODEL_REVISION = "29d097773436b69ff9feafd636ab4cf873786537"
MODEL_SHA256 = "93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b"
CONTEXT = PAYLOAD["runtime"]["context"]
PORT = 18090
REQUEST_TIMEOUT = 1200

WORK = Path("/kaggle/working")
OUT = WORK / "harness-generation"
OUT.mkdir(parents=True, exist_ok=True)
EVENTS = OUT / "events.log"


def log(message):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {message}"
    print(line, flush=True)
    with EVENTS.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def call(path, body=None, timeout=120):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def write_results(results, runtime):
    (OUT / "results.json").write_text(json.dumps({"runtime": runtime, "results": results}, ensure_ascii=False, indent=2),
                                      encoding="utf-8")


def main():
    log(f"payload {PAYLOAD['payload_sha256']} with {len(PAYLOAD['requests'])} request(s)")
    gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                                  text=True)
    log("gpu " + gpu.strip().replace("\n", " | "))
    if "T4" not in gpu:
        # Earlier Gemma runs used T4; a different GPU is recorded, not hidden.
        log("warning: accelerator is not a T4; results are kept but the GPU differs from earlier runs")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "huggingface_hub==1.31.0"], check=True)

    tarball = WORK / "llama-b11382.tar.gz"
    urllib.request.urlretrieve(ENGINE_URL, tarball)
    assert sha256_file(tarball) == ENGINE_TARBALL_SHA256, "engine tarball hash mismatch"
    engine = WORK / "llama-b11382"
    engine.mkdir(exist_ok=True)
    with tarfile.open(tarball) as archive:
        archive.extractall(engine, filter="data")
    servers = list(engine.rglob("llama-server"))
    assert len(servers) == 1 and sha256_file(servers[0]) == SERVER_SHA256, "llama-server hash mismatch"
    server_bin = servers[0]
    server_bin.chmod(0o755)
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = ":".join(sorted({str(p.parent) for p in engine.rglob("*.so*")}) + [env.get("LD_LIBRARY_PATH", "")])
    version = subprocess.check_output([str(server_bin), "--version"], env=env, stderr=subprocess.STDOUT, text=True)
    log("engine " + version.strip().replace("\n", " "))

    from huggingface_hub import snapshot_download

    model_dir = Path(snapshot_download(repo_id=MODEL_REPO, revision=MODEL_REVISION, allow_patterns=["*.gguf"]))
    models = [p for p in model_dir.glob("*.gguf")
              if not any(x in p.name.lower() for x in ("mmproj", "projector", "assistant", "drafter"))]
    assert len(models) == 1, f"expected one model file, found {models}"
    model = models[0]
    model_sha = sha256_file(model)
    assert model_sha == MODEL_SHA256, f"model hash mismatch: {model_sha}"

    runtime = {"model_repo": MODEL_REPO, "model_revision": MODEL_REVISION, "model_file": model.name,
               "model_sha256": model_sha, "engine_url": ENGINE_URL, "server_sha256": SERVER_SHA256,
               "server_version": version.strip(), "context": CONTEXT, "gpu": gpu.strip(),
               "flags": ["-ngl", "99", "--parallel", "1", "--reasoning-budget", "0"],
               "payload_sha256": PAYLOAD["payload_sha256"]}
    (OUT / "runtime-lock.json").write_text(json.dumps(runtime, indent=2), encoding="utf-8")

    server_log = (OUT / "server.log").open("ab")
    server = subprocess.Popen([str(server_bin), "-m", str(model), "-c", str(CONTEXT), "-ngl", "99", "--parallel", "1",
                               "--host", "127.0.0.1", "--port", str(PORT), "--reasoning-budget", "0"],
                              env=env, stdout=server_log, stderr=subprocess.STDOUT)
    results = []
    try:
        deadline = time.time() + 900
        while True:
            try:
                if call("/health", timeout=5).get("status") == "ok":
                    break
            except (urllib.error.URLError, ConnectionError, OSError, ValueError):
                pass
            if server.poll() is not None or time.time() > deadline:
                raise RuntimeError("llama-server did not become ready; see server.log")
            time.sleep(2)
        log("server ready")

        for item in PAYLOAD["requests"]:
            body = item["body"]
            record = {"request_id": item["request_id"], "request_sha256": item["request_sha256"]}
            try:
                prompt = call("/apply-template", body)["prompt"]
                tokens = call("/tokenize", {"content": prompt, "add_special": True, "parse_special": True})["tokens"]
                record["input_tokens_preflight"] = len(tokens)
                if len(tokens) + body["max_tokens"] + 8 > CONTEXT:
                    record.update(status="budget_exceeded")
                    results.append(record)
                    write_results(results, runtime)
                    continue
                started = time.time()
                response = call("/v1/chat/completions", body, timeout=REQUEST_TIMEOUT)
                choice = response["choices"][0]
                record.update(status="completed", seconds=round(time.time() - started, 3),
                              finish_reason=choice.get("finish_reason"), content=choice["message"].get("content"),
                              usage=response.get("usage"), timings=response.get("timings"))
            except urllib.error.HTTPError as err:
                record.update(status="failed", error=f"HTTP {err.code}: {err.read()[:2000].decode('utf-8', 'replace')}")
            except Exception as err:  # timeouts are ambiguous and are not retried
                record.update(status="ambiguous", error=f"{type(err).__name__}: {err}")
            log(f"{item['request_id']} -> {record['status']}")
            results.append(record)
            write_results(results, runtime)
    finally:
        server.terminate()
        try:
            server.wait(30)
        except subprocess.TimeoutExpired:
            server.kill()
        write_results(results, runtime)
        for leftover in (tarball,):
            leftover.unlink(missing_ok=True)
    log("done")


if __name__ == "__main__":
    main()

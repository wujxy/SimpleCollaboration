#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time


def option(name: str) -> str | None:
    try:
        return sys.argv[sys.argv.index(name) + 1]
    except (ValueError, IndexError):
        return None


name = option("--name") or "unknown"
log_dir = Path(os.environ["SIMPLECOLLAB_FAKE_LOG_DIR"])
log_dir.mkdir(parents=True, exist_ok=True)
(log_dir / f"{name}.argv.json").write_text(json.dumps(sys.argv), encoding="utf-8")
(log_dir / f"{name}.pid").write_text(str(os.getpid()), encoding="utf-8")

session_id = option("--resume") or f"session-{name}"
print(json.dumps({"type": "system", "subtype": "init", "session_id": session_id}), flush=True)

if os.environ.get("SIMPLECOLLAB_FAKE_MALFORMED") == name:
    print("not-json", flush=True)
if os.environ.get("SIMPLECOLLAB_FAKE_STDERR") == name:
    print(f"failure includes {os.environ.get('TEST_API_TOKEN', '')}", file=sys.stderr, flush=True)
if os.environ.get("SIMPLECOLLAB_FAKE_FAIL") in (name, "all"):
    raise SystemExit(7)

for raw in sys.stdin:
    message = json.loads(raw)
    with (log_dir / f"{name}.input.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(message) + "\n")
    print(json.dumps({
        "type": "assistant",
        "session_id": session_id,
        "message": {
            "id": f"call-{name}",
            "model": "fake",
            "content": [{"type": "text", "text": f"working as {name}"}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    }), flush=True)
    if os.environ.get("SIMPLECOLLAB_FAKE_HANG"):
        while True:
            time.sleep(1)
    print(json.dumps({
        "type": "result",
        "subtype": "success",
        "session_id": session_id,
        "is_error": False,
        "result": f"idle {name}",
    }), flush=True)

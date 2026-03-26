#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import assemble_runtime
from app.config import load_config
from app.contracts import TaskRequest


def build_request(*, path: str, max_entries: int) -> TaskRequest:
    return TaskRequest(
        task_id="demo-minimal-agent-os",
        task_type="demo.minimal",
        message="Run the minimal Agent OS demo.",
        context={
            "session_id": "demo-session",
            "demo_mode": "minimal",
            "demo_path": path,
            "demo_max_entries": max_entries,
            "execution_policy": "demo_safe",
            "runtime_profile": "minimal_demo",
        },
    )


def format_summary(payload: dict[str, object]) -> str:
    demo = dict(payload.get("demo") or {})
    lines = [
        f"module_id: {payload.get('module_id')}",
        f"tool: {demo.get('tool_name')}",
        f"provider: {demo.get('provider_id')}",
        f"resolved_path: {demo.get('resolved_path')}",
        f"entry_count: {demo.get('entry_count')}",
    ]
    entry_names = list(demo.get("entry_names") or [])
    if entry_names:
        lines.append("entries: " + ", ".join(str(item) for item in entry_names[:5]))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the minimal Agent OS demo flow.")
    parser.add_argument("--path", default=".", help="Workspace path to read through workspace.read.")
    parser.add_argument("--max-entries", type=int, default=5, help="Maximum directory entries to return.")
    parser.add_argument("--json", action="store_true", help="Print the full result as JSON.")
    parser.add_argument("--check", action="store_true", help="Fail unless the expected tool/provider path succeeds.")
    args = parser.parse_args()

    runtime = assemble_runtime(load_config())
    response = runtime.dispatch(build_request(path=args.path, max_entries=args.max_entries), module_id="office_module")
    snapshot = runtime.kernel.health_snapshot()
    trace = list(snapshot.get("recent_traces") or [])[-1]
    result = {
        "ok": bool(response.ok),
        "text": response.text,
        "payload": dict(response.payload or {}),
        "warnings": list(response.warnings or []),
        "error": response.error,
        "trace": trace,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(response.text or "Minimal Agent OS demo finished.")
        print(format_summary(result["payload"]))
        print(f"trace_module: {trace.get('module_id')}")
        print(f"trace_outcome: {trace.get('final_outcome')}")

    if not response.ok:
        return 1
    if args.check:
        demo = dict(response.payload.get("demo") or {})
        if demo.get("tool_name") != "workspace.read":
            print("unexpected demo tool", file=sys.stderr)
            return 1
        if demo.get("provider_id") != "local_workspace_provider":
            print("unexpected demo provider", file=sys.stderr)
            return 1
        if trace.get("final_outcome") != "ok":
            print("trace did not record a successful outcome", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

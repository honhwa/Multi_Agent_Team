from __future__ import annotations

from app.bootstrap import assemble_runtime
from app.config import load_config
from app.contracts import TaskRequest
from tests.support_agent_os import DummyLegacyHost


def test_kernel_dispatch_office_request_generates_trace() -> None:
    runtime = assemble_runtime(load_config(), legacy_host=DummyLegacyHost())

    response = runtime.dispatch(
        TaskRequest(
            task_id="integration-1",
            task_type="chat",
            message="hello",
            context={"history_turns": [], "summary": "", "session_id": "s-1"},
        ),
        module_id="office_module",
    )

    assert response.ok is True
    snapshot = runtime.kernel.health_snapshot()
    trace = snapshot["recent_traces"][-1]
    assert trace["module_id"] == "office_module"
    assert trace["final_outcome"] == "ok"
    assert "selected_tools" in trace and trace["selected_tools"]


def test_kernel_dispatch_minimal_demo_hits_workspace_provider() -> None:
    runtime = assemble_runtime(load_config())

    response = runtime.dispatch(
        TaskRequest(
            task_id="integration-demo",
            task_type="demo.minimal",
            message="run the minimal demo",
            context={
                "session_id": "demo-session",
                "demo_path": ".",
                "demo_max_entries": 3,
                "execution_policy": "demo_safe",
                "runtime_profile": "minimal_demo",
            },
        ),
        module_id="office_module",
    )

    assert response.ok is True
    demo = dict(response.payload.get("demo") or {})
    assert demo["tool_name"] == "workspace.read"
    assert demo["provider_id"] == "local_workspace_provider"
    trace = runtime.kernel.health_snapshot()["recent_traces"][-1]
    assert trace["runtime_profile"] == "minimal_demo"
    assert trace["execution_policy"] == "demo_safe"
    assert trace["selected_tools"] == ["workspace.read"]
    assert trace["selected_providers"] == ["local_workspace_provider"]
    assert any(event["stage"] == "tool_dispatch" for event in trace["events"])

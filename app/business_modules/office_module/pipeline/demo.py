from __future__ import annotations

from typing import Any

from app.contracts import TaskRequest, TaskResponse, ToolCall, ToolResult
from app.kernel.runtime_context import RuntimeContext


_DEMO_ROLE_CHAIN = ["router", "worker"]


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def run_minimal_demo(
    *,
    request: TaskRequest,
    context: RuntimeContext,
    kernel_context: Any,
    module_id: str,
) -> TaskResponse:
    tool_runtime = kernel_context.lookup_module("tool_runtime_module") if kernel_context is not None else None
    if tool_runtime is None or not hasattr(tool_runtime, "execute"):
        context.health_state = "degraded"
        return TaskResponse(
            ok=False,
            task_id=request.task_id,
            error="tool_runtime_module is unavailable",
            warnings=["minimal demo could not resolve the tool runtime module"],
            payload={"module_id": module_id, "demo": {"ok": False}},
        )

    request_context = dict(request.context or {})
    requested_path = str(request_context.get("demo_path") or ".")
    max_entries = max(1, min(20, _coerce_int(request_context.get("demo_max_entries"), 5)))
    call = ToolCall(
        name="workspace.read",
        arguments={"path": requested_path, "max_entries": max_entries},
        timeout_sec=5.0,
        metadata={
            "source": "office_module.demo.minimal",
            "request_id": request.task_id,
        },
    )
    result = tool_runtime.execute(call)
    if not isinstance(result, ToolResult):
        result = ToolResult(
            ok=False,
            tool_name=call.name,
            provider_id="",
            error="tool runtime returned an invalid result",
        )

    context.selected_roles = list(_DEMO_ROLE_CHAIN)
    context.selected_tools = [call.name]
    context.selected_providers = [result.provider_id] if result.provider_id else []
    context.execution_policy = context.execution_policy or str(request_context.get("execution_policy") or "demo_safe")
    context.runtime_profile = context.runtime_profile or str(request_context.get("runtime_profile") or "minimal_demo")

    response_payload = {
        "module_id": module_id,
        "selected_roles": list(context.selected_roles),
        "selected_tools": list(context.selected_tools),
        "selected_providers": list(context.selected_providers),
        "module_pipeline": [
            {
                "stage": "dispatch",
                "detail": "KernelHost resolved office_module.",
                "status": "complete",
            },
            {
                "stage": "module_handle",
                "detail": "office_module handled the request in minimal demo mode.",
                "status": "complete",
            },
            {
                "stage": "tool_call",
                "detail": f"tool_runtime_module executed {call.name} through ProviderRegistry.",
                "status": "complete" if result.ok else "error",
            },
        ],
        "demo": {
            "ok": bool(result.ok),
            "tool_name": call.name,
            "provider_id": result.provider_id,
            "requested_path": requested_path,
            "resolved_path": str(result.data.get("path") or requested_path),
            "entry_count": len(result.data.get("entries") or []),
            "entry_names": [
                str(item.get("name") or "")
                for item in list(result.data.get("entries") or [])
                if isinstance(item, dict)
            ],
            "fallback_used": bool(result.fallback_used),
            "attempts": int(result.attempts),
            "tool_result": result.to_dict(),
        },
    }
    if result.ok:
        response_text = (
            "Minimal Agent OS demo succeeded. "
            f"KernelHost dispatched {module_id}, and {call.name} returned "
            f"{response_payload['demo']['entry_count']} entries from {response_payload['demo']['resolved_path']}."
        )
        return TaskResponse(
            ok=True,
            task_id=request.task_id,
            text=response_text,
            payload=response_payload,
        )

    context.health_state = "degraded"
    return TaskResponse(
        ok=False,
        task_id=request.task_id,
        error=result.error or "minimal demo failed",
        warnings=["workspace.read did not succeed during the minimal demo"],
        payload=response_payload,
    )

from __future__ import annotations

from app.bootstrap import AgentOSAssembleConfig, assemble_runtime
from app.config import load_config
from app.contracts import HealthReport, TaskRequest, ToolCall, ToolResult
from tests.support_agent_os import bind_fake_research_provider


class FailingResearchProvider:
    provider_id = "failing_research_provider"
    supported_tools = ["web.search", "web.fetch"]

    def execute(self, call: ToolCall) -> ToolResult:
        return ToolResult(
            ok=False,
            tool_name=call.name,
            provider_id=self.provider_id,
            error=f"simulated provider failure for {call.name}",
        )

    def health_check(self) -> HealthReport:
        return HealthReport(component_id=self.provider_id, status="healthy", summary="failing research provider ready")


def _runtime():
    return assemble_runtime(
        load_config(),
        assemble_config=AgentOSAssembleConfig(
            include_research_module=True,
            include_coding_module=False,
            include_adaptation_module=False,
            enable_session_provider=True,
        ),
    )


def test_kernel_dispatch_research_request_marks_provider_fallback_as_degraded_success() -> None:
    runtime = _runtime()
    runtime.kernel.register_provider(FailingResearchProvider())
    bind_fake_research_provider(runtime, fallback_providers=[])
    for tool_name in ("web.search", "web.fetch"):
        contract = runtime.kernel.registry.get_tool_contract(tool_name)
        assert contract is not None
        runtime.kernel.registry.register_tool_contract(
            contract,
            primary_provider="failing_research_provider",
            fallback_providers=["fake_research_provider"],
        )

    response = runtime.dispatch(
        TaskRequest(
            task_id="research-provider-fallback",
            task_type="task.research",
            message="provider fallback research scenario",
            context={
                "session_id": "research-provider-fallback",
                "fetch_top_result": True,
                "execution_policy": "research_pipeline",
                "runtime_profile": "research_eval",
            },
        ),
        module_id="research_module",
    )

    assert response.ok is True
    assert response.payload["result_grade"] == "degraded"
    assert response.payload["return_strategy"] == "return_answer_with_provider_fallback_note"
    assert response.payload["research"]["provider_fallback_used"] is True
    assert response.payload["research"]["search"]["fallback_used"] is True
    trace = runtime.kernel.health_snapshot()["recent_traces"][-1]
    assert trace["final_outcome"] == "ok"
    assert trace["selected_providers"] == ["fake_research_provider"]


def test_kernel_dispatch_research_request_reports_failed_when_no_provider_returns_evidence() -> None:
    runtime = _runtime()
    runtime.kernel.register_provider(FailingResearchProvider())
    for tool_name in ("web.search", "web.fetch"):
        contract = runtime.kernel.registry.get_tool_contract(tool_name)
        assert contract is not None
        runtime.kernel.registry.register_tool_contract(
            contract,
            primary_provider="failing_research_provider",
            fallback_providers=[],
        )

    response = runtime.dispatch(
        TaskRequest(
            task_id="research-hard-failure",
            task_type="task.research",
            message="hard failure research scenario",
            context={
                "session_id": "research-hard-failure",
                "fetch_top_result": True,
                "execution_policy": "research_pipeline",
                "runtime_profile": "research_eval",
            },
        ),
        module_id="research_module",
    )

    assert response.ok is False
    assert response.payload["result_grade"] == "failed"
    assert response.payload["return_strategy"] == "report_failure"
    assert response.payload["research"]["evidence_completeness"] == "none"
    trace = runtime.kernel.health_snapshot()["recent_traces"][-1]
    assert trace["final_outcome"] == "failed"

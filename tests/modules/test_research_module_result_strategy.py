from __future__ import annotations

from app.bootstrap import AgentOSAssembleConfig, assemble_runtime
from app.config import load_config
from app.contracts import TaskRequest
from tests.support_agent_os import bind_fake_research_provider


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


def test_research_module_fetch_failure_returns_degraded_search_only_response() -> None:
    runtime = _runtime()
    bind_fake_research_provider(runtime, fetch_fail_urls={"https://example.com/source-one"})

    response = runtime.dispatch(
        TaskRequest(
            task_id="research-fetch-failure",
            task_type="task.research",
            message="fetch failure research scenario",
            context={"session_id": "research-fetch-failure", "fetch_top_result": True},
        ),
        module_id="research_module",
    )

    assert response.ok is True
    assert response.payload["result_grade"] == "degraded"
    assert response.payload["return_strategy"] == "return_search_only_with_caveat"
    assert response.payload["research"]["evidence_completeness"] == "partial"
    assert response.payload["research"]["fetch_success"] is False
    assert "Fetched evidence:" not in response.text
    assert any("fetch failed" in warning for warning in response.warnings)


def test_research_module_empty_source_set_returns_insufficient_evidence() -> None:
    runtime = _runtime()
    bind_fake_research_provider(runtime, results_by_query={"empty source research scenario": []})

    response = runtime.dispatch(
        TaskRequest(
            task_id="research-empty-sources",
            task_type="task.research",
            message="empty source research scenario",
            context={"session_id": "research-empty-sources", "research_query": "empty source research scenario", "fetch_top_result": True},
        ),
        module_id="research_module",
    )

    assert response.ok is True
    assert response.payload["result_grade"] == "insufficient_evidence"
    assert response.payload["return_strategy"] == "ask_rewrite_query"
    assert response.payload["research"]["source_count"] == 0
    assert response.payload["research"]["evidence_completeness"] == "insufficient"
    assert "rephrase the query" in response.text.lower()


def test_research_module_single_source_response_is_marked_insufficient() -> None:
    runtime = _runtime()
    bind_fake_research_provider(
        runtime,
        results_by_query={
            "sparse evidence research scenario": [
                {
                    "title": "Sparse Evidence Source",
                    "url": "https://example.com/sparse-evidence",
                    "snippet": "Only one source is available.",
                    "domain": "example.com",
                    "score": 6.1,
                    "source": "fake_research",
                }
            ]
        },
    )

    response = runtime.dispatch(
        TaskRequest(
            task_id="research-sparse-evidence",
            task_type="task.research",
            message="sparse evidence research scenario",
            context={"session_id": "research-sparse-evidence", "research_query": "sparse evidence research scenario", "fetch_top_result": True},
        ),
        module_id="research_module",
    )

    assert response.ok is True
    assert response.payload["result_grade"] == "insufficient_evidence"
    assert response.payload["return_strategy"] == "report_unreliable_and_offer_swarm"
    assert response.payload["research"]["source_count"] == 1
    assert response.payload["research"]["partial_results"] is True
    assert "Only one usable source was found" in response.text


def test_research_module_conflicting_sources_are_marked_unreliable() -> None:
    runtime = _runtime()
    bind_fake_research_provider(
        runtime,
        results_by_query={
            "conflicting evidence research scenario": [
                {
                    "title": "Shared Research Conflict",
                    "url": "https://example.com/conflict-alpha",
                    "snippet": "Architecture source says one thing.",
                    "domain": "example.com",
                    "score": 9.2,
                    "source": "fake_research",
                },
                {
                    "title": "Shared Research Conflict",
                    "url": "https://evidence.example.org/conflict-beta",
                    "snippet": "Independent source points elsewhere.",
                    "domain": "evidence.example.org",
                    "score": 9.1,
                    "source": "fake_research",
                },
            ]
        },
    )

    response = runtime.dispatch(
        TaskRequest(
            task_id="research-conflict",
            task_type="task.research",
            message="conflicting evidence research scenario",
            context={"session_id": "research-conflict", "research_query": "conflicting evidence research scenario", "fetch_top_result": True},
        ),
        module_id="research_module",
    )

    assert response.ok is True
    assert response.payload["result_grade"] == "insufficient_evidence"
    assert response.payload["return_strategy"] == "report_unreliable_and_offer_swarm"
    assert response.payload["research"]["conflict_detected"] is True
    assert len(response.payload["research"]["conflicts"]) == 1
    assert "not reliable enough for a confident answer" in response.text

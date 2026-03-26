from __future__ import annotations

from typing import Any

from app.intent_classifier import IntentClassifier
from app.intent_schema import IntentClassification
from app.policy_router import PolicyRouter
from app.router_signals import RouterSignalExtractor


class _StubSettings:
    def __init__(self, *, enable_tools: bool = True) -> None:
        self.enable_tools = enable_tools


class _StubAgent:
    def _looks_like_context_dependent_followup(self, text: str) -> bool:
        return "继续" in str(text or "")

    def _looks_like_spec_lookup_request(self, user_message: str, attachment_metas: list[dict[str, Any]]) -> bool:
        _ = attachment_metas
        return "spec" in str(user_message or "").lower()

    def _requires_evidence_mode(self, user_message: str, attachment_metas: list[dict[str, Any]]) -> bool:
        _ = attachment_metas
        return "证据" in str(user_message or "")

    def _attachment_needs_tooling(self, meta: dict[str, Any]) -> bool:
        return bool(meta.get("needs_tooling"))

    def _attachment_is_inline_parseable(self, meta: dict[str, Any]) -> bool:
        return bool(meta.get("inline_parseable", True))

    def _looks_like_inline_document_payload(self, user_message: str) -> bool:
        return "```" in str(user_message or "")

    def _looks_like_understanding_request(self, user_message: str) -> bool:
        lowered = str(user_message or "").lower()
        return ("解释" in lowered) or ("understand" in lowered)

    def _looks_like_holistic_document_explanation_request(self, user_message: str) -> bool:
        return "整体" in str(user_message or "")

    def _looks_like_source_trace_request(self, user_message: str) -> bool:
        return "出处" in str(user_message or "")

    def _looks_like_explicit_tool_confirmation(self, user_message: str) -> bool:
        return str(user_message or "").strip() in {"继续", "执行"}

    def _looks_like_meeting_minutes_request(self, user_message: str) -> bool:
        return "会议纪要" in str(user_message or "")

    def _looks_like_internal_ticket_reference(self, user_message: str) -> bool:
        return "jira" in str(user_message or "").lower()

    def _request_likely_requires_tools(self, user_message: str, attachment_metas: list[dict[str, Any]]) -> bool:
        return bool(attachment_metas) or ("查找" in str(user_message or ""))

    def _looks_like_local_code_lookup_request(self, user_message: str, attachment_metas: list[dict[str, Any]]) -> bool:
        _ = attachment_metas
        return "函数" in str(user_message or "")

    def _message_has_explicit_local_path(self, user_message: str) -> bool:
        return "/" in str(user_message or "")

    def _has_file_like_lookup_token(self, text: str) -> bool:
        lowered = str(text or "").lower()
        return ".py" in lowered or ".md" in lowered

    def _should_auto_search_default_roots(self, user_message: str, attachment_metas: list[dict[str, Any]]) -> bool:
        _ = attachment_metas
        return "默认目录" in str(user_message or "")

    def _infer_followup_primary_intent_from_state(
        self,
        *,
        user_message: str,
        route_state: dict[str, Any] | None,
        signals: dict[str, Any],
    ) -> str:
        _ = user_message, signals
        return str((route_state or {}).get("primary_intent") or "")

    def _classify_primary_intent(
        self,
        *,
        user_message: str,
        attachment_metas: list[dict[str, Any]],
        route_state: dict[str, Any] | None,
        signals: dict[str, Any],
    ) -> str:
        _ = user_message, attachment_metas, route_state
        if signals.get("source_trace_request") or signals.get("spec_lookup_request"):
            return "evidence"
        if signals.get("local_code_lookup_request"):
            return "code_lookup"
        return "understanding"

    def _default_execution_policy_for_intent(self, primary_intent: str) -> str:
        mapping = {
            "evidence": "evidence_full_pipeline",
            "code_lookup": "code_lookup_with_tools",
            "understanding": "understanding_direct",
        }
        return mapping.get(str(primary_intent or ""), "standard_full_pipeline")

    def _resolve_execution_policy(
        self,
        *,
        primary_intent: str,
        user_message: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        signals: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        _ = user_message, attachment_metas, settings
        out = dict(fallback or {})
        out["primary_intent"] = primary_intent
        out["use_worker_tools"] = bool(signals.get("request_requires_tools"))
        out["execution_policy"] = self._default_execution_policy_for_intent(primary_intent)
        out["needs_llm_router"] = True
        out["reason"] = "stub_policy_router"
        return out


def test_router_signal_extractor_and_rule_intent_classifier() -> None:
    agent = _StubAgent()
    extractor = RouterSignalExtractor(agent, news_hints=("news", "新闻"))
    settings = _StubSettings(enable_tools=True)
    attachments = [{"inline_parseable": False, "needs_tooling": True}]
    signals = extractor.extract(
        user_message="请在附件里定位出处并给解释",
        attachment_metas=attachments,
        settings=settings,
        route_state={"primary_intent": "understanding"},
        inline_followup_context=False,
    )
    assert signals.has_attachments is True
    assert signals.source_trace_request is True
    assert signals.request_requires_tools is True
    assert signals.attachment_needs_tooling is True

    classifier = IntentClassifier(agent)
    intent = classifier.classify_rules(
        user_message="请在附件里定位出处并给解释",
        attachment_metas=attachments,
        route_state={"primary_intent": "understanding"},
        signals=signals,
    )
    assert intent.primary_intent == "evidence"
    assert intent.requires_grounding is True
    assert intent.requires_tools is True
    assert intent.action_type == "search"


def test_policy_router_injects_intent_metadata() -> None:
    agent = _StubAgent()
    policy_router = PolicyRouter(agent)
    settings = _StubSettings(enable_tools=True)
    classifier = IntentClassification(
        primary_intent="code_lookup",
        secondary_intents=["code_lookup", "attachment_read"],
        requires_tools=True,
        requires_grounding=False,
        requires_web=False,
        requires_local_lookup=True,
        action_type="read",
        confidence=0.88,
        reason_short="stub",
        source="llm_intent_classifier",
        classifier_model="gpt-test",
    )
    fallback = policy_router.build_fallback(
        intent=classifier,
        user_message="帮我看这个函数",
        attachment_metas=[],
        settings=settings,
        signals=extractor_signals_for_test(),
    )
    routed = policy_router.route(
        intent=classifier,
        user_message="帮我看这个函数",
        attachment_metas=[],
        settings=settings,
        signals=extractor_signals_for_test(),
        fallback=fallback,
        source_override="llm_intent_classifier",
        force_disable_llm_router=True,
    )
    assert routed["primary_intent"] == "code_lookup"
    assert routed["action_type"] == "read"
    assert routed["intent_source"] == "llm_intent_classifier"
    assert routed["needs_llm_router"] is False
    assert routed["source"] == "llm_intent_classifier"
    assert routed["router_model"] == "gpt-test"


def extractor_signals_for_test():
    return RouterSignalExtractor(_StubAgent(), news_hints=("news",)).extract(
        user_message="帮我查找函数",
        attachment_metas=[],
        settings=_StubSettings(enable_tools=True),
        route_state={},
        inline_followup_context=False,
    )

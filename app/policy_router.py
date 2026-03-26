from __future__ import annotations

from typing import Any

from app.intent_schema import IntentClassification, RequestSignals, RouteDecision


class PolicyRouter:
    def __init__(self, agent: Any) -> None:
        self._agent = agent

    def build_fallback(
        self,
        *,
        intent: IntentClassification,
        user_message: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        signals: RequestSignals,
    ) -> dict[str, Any]:
        return {
            "task_type": "standard",
            "complexity": "medium",
            "use_planner": True,
            "use_worker_tools": bool(bool(getattr(settings, "enable_tools", False)) and signals.request_requires_tools),
            "use_reviewer": True,
            "use_revision": True,
            "use_structurer": True,
            "use_web_prefetch": bool(bool(getattr(settings, "enable_tools", False)) and signals.web_request),
            "use_conflict_detector": True,
            "specialists": [],
            "needs_llm_router": False,
            "reason": "rules_default_full_pipeline",
            "source": "rules",
            "summary": "默认走完整流水线。",
            "router_model": "",
            "primary_intent": intent.primary_intent,
            "secondary_intents": list(intent.secondary_intents),
            "requires_tools": bool(intent.requires_tools),
            "requires_grounding": bool(intent.requires_grounding),
            "requires_web": bool(intent.requires_web),
            "requires_local_lookup": bool(intent.requires_local_lookup),
            "action_type": intent.action_type,
            "intent_confidence": float(intent.confidence),
            "intent_source": str(intent.source or "rules_intent_classifier"),
            "intent_reason": str(intent.reason_short or ""),
            "execution_policy": self._agent._default_execution_policy_for_intent(intent.primary_intent),
            "spec_lookup_request": bool(signals.spec_lookup_request),
            "evidence_required_mode": bool(signals.evidence_required),
            "default_root_search": bool(signals.default_root_search),
        }

    def route(
        self,
        *,
        intent: IntentClassification,
        user_message: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        signals: RequestSignals,
        fallback: dict[str, Any],
        source_override: str = "",
        force_disable_llm_router: bool = False,
    ) -> dict[str, Any]:
        routed = self._agent._resolve_execution_policy(
            primary_intent=intent.primary_intent,
            user_message=user_message,
            attachment_metas=attachment_metas,
            settings=settings,
            signals=signals.to_dict(),
            fallback=fallback,
        )
        out = dict(routed or {})
        out.update(
            {
                "primary_intent": intent.primary_intent,
                "secondary_intents": list(intent.secondary_intents),
                "requires_tools": bool(intent.requires_tools),
                "requires_grounding": bool(intent.requires_grounding),
                "requires_web": bool(intent.requires_web),
                "requires_local_lookup": bool(intent.requires_local_lookup),
                "action_type": intent.action_type,
                "intent_confidence": float(intent.confidence),
                "intent_source": str(intent.source or out.get("intent_source") or "rules_intent_classifier"),
                "intent_reason": str(intent.reason_short or out.get("intent_reason") or ""),
            }
        )
        if intent.classifier_model:
            out["router_model"] = intent.classifier_model
        if source_override:
            out["source"] = source_override
        if force_disable_llm_router:
            out["needs_llm_router"] = False

        decision = RouteDecision.model_validate(
            {
                **fallback,
                **out,
            }
        )
        return decision.to_route_dict()

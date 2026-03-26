from __future__ import annotations

import json
from typing import Any

from app.intent_schema import IntentClassification, RequestSignals


_ALLOWED_PRIMARY_INTENTS = {
    "understanding",
    "evidence",
    "web",
    "code_lookup",
    "generation",
    "meeting_minutes",
    "qa",
    "standard",
}

_ALLOWED_ACTION_TYPES = {"answer", "search", "read", "modify", "create"}


class IntentClassifier:
    def __init__(self, agent: Any) -> None:
        self._agent = agent

    def classify_rules(
        self,
        *,
        user_message: str,
        attachment_metas: list[dict[str, Any]],
        route_state: dict[str, Any] | None,
        signals: RequestSignals,
    ) -> IntentClassification:
        signal_dict = signals.to_dict()
        primary_intent = self._agent._classify_primary_intent(
            user_message=user_message,
            attachment_metas=attachment_metas,
            route_state=route_state,
            signals=signal_dict,
        )
        return self._build_from_primary_intent(primary_intent=primary_intent, signals=signals, source="rules_intent_classifier")

    def classify_with_llm(
        self,
        *,
        requested_model: str,
        user_message: str,
        summary: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        signals: RequestSignals,
        fallback: IntentClassification,
    ) -> tuple[IntentClassification, str]:
        auth_summary = self._agent._auth_manager.auth_summary()
        if not bool(auth_summary.get("available")):
            return fallback, json.dumps({"skipped": auth_summary.get("reason") or "openai_auth_missing"}, ensure_ascii=False)

        classifier_input = "\n".join(
            [
                f"user_message:\n{str(user_message or '').strip() or '(empty)'}",
                f"history_summary:\n{str(summary or '').strip() or '(none)'}",
                f"attachments:\n{self._agent._summarize_attachment_metas_for_agents(attachment_metas)}",
                f"enable_tools={str(bool(getattr(settings, 'enable_tools', False))).lower()}",
                f"signals={json.dumps(signals.to_dict(), ensure_ascii=False)}",
                f"rules_fallback={json.dumps(fallback.to_dict(), ensure_ascii=False)}",
            ]
        )
        messages = [
            self._agent._SystemMessage(
                content=(
                    "你是 Intent Classifier。"
                    "只负责语义分类，不直接给执行链路。"
                    "只返回 JSON 对象，字段固定为 "
                    "primary_intent, secondary_intents, requires_tools, requires_grounding, "
                    "requires_web, requires_local_lookup, action_type, confidence, reason_short。"
                    "primary_intent 只能是 understanding, evidence, web, code_lookup, generation, meeting_minutes, qa, standard。"
                    "action_type 只能是 answer, search, read, modify, create。"
                    "confidence 范围 0~1。"
                )
            ),
            self._agent._HumanMessage(content=classifier_input),
        ]
        try:
            ai_msg, _, effective_model, notes = self._agent._invoke_chat_with_runner(
                messages=messages,
                model=self._agent.config.summary_model or requested_model,
                max_output_tokens=500,
                enable_tools=False,
            )
            raw_text = self._agent._content_to_text(getattr(ai_msg, "content", "")).strip()
            parsed = self._agent._parse_json_object(raw_text)
            if not parsed:
                degraded = fallback.model_copy(
                    update={
                        "source": "rules_intent_classifier",
                        "reason_short": f"{fallback.reason_short} intent_classifier_invalid_json".strip(),
                        "classifier_model": effective_model,
                    }
                )
                return degraded, raw_text
            classified = self._normalize_payload(
                payload=parsed,
                fallback=fallback,
                source="llm_intent_classifier",
                classifier_model=effective_model,
            )
            if notes:
                extra = self._agent._normalize_string_list(notes, limit=2, item_limit=120)
                if extra:
                    classified.reason_short = "; ".join([classified.reason_short, *extra]).strip("; ")
            return classified, raw_text
        except Exception as exc:
            degraded = fallback.model_copy(
                update={
                    "source": "rules_intent_classifier",
                    "reason_short": f"{fallback.reason_short} intent_classifier_failed".strip(),
                }
            )
            return degraded, json.dumps({"error": str(exc)}, ensure_ascii=False)

    def classification_from_route(self, route: dict[str, Any]) -> IntentClassification:
        payload = {
            "primary_intent": route.get("primary_intent"),
            "secondary_intents": route.get("secondary_intents"),
            "requires_tools": route.get("requires_tools"),
            "requires_grounding": route.get("requires_grounding"),
            "requires_web": route.get("requires_web"),
            "requires_local_lookup": route.get("requires_local_lookup"),
            "action_type": route.get("action_type"),
            "confidence": route.get("intent_confidence") or route.get("confidence"),
            "reason_short": route.get("intent_reason") or route.get("reason"),
            "source": route.get("intent_source") or route.get("source"),
            "classifier_model": route.get("router_model"),
        }
        fallback = IntentClassification()
        return self._normalize_payload(payload=payload, fallback=fallback, source=str(payload.get("source") or "rules_intent_classifier"))

    def _build_from_primary_intent(
        self,
        *,
        primary_intent: str,
        signals: RequestSignals,
        source: str,
    ) -> IntentClassification:
        normalized_primary = str(primary_intent or "").strip().lower()
        if normalized_primary not in _ALLOWED_PRIMARY_INTENTS:
            normalized_primary = "standard"

        secondary_intents = self._derive_secondary_intents(normalized_primary, signals)
        requires_tools = bool(
            signals.request_requires_tools
            or signals.attachment_needs_tooling
            or normalized_primary in {"evidence", "web", "code_lookup"}
            or (normalized_primary == "generation" and signals.grounded_code_generation_context)
        )
        requires_grounding = bool(
            signals.spec_lookup_request
            or signals.evidence_required
            or signals.source_trace_request
            or normalized_primary in {"evidence", "web"}
        )
        requires_web = bool(signals.web_request or normalized_primary == "web")
        requires_local_lookup = bool(
            signals.local_code_lookup_request
            or signals.has_attachments
            or signals.attachment_needs_tooling
            or signals.default_root_search
        )

        action_type = self._infer_action_type(
            primary_intent=normalized_primary,
            requires_tools=requires_tools,
            grounded_generation=signals.grounded_code_generation_context,
        )

        confidence = self._estimate_confidence(normalized_primary, signals)
        reason_short = self._build_reason_short(normalized_primary, signals)

        return IntentClassification(
            primary_intent=normalized_primary,  # type: ignore[arg-type]
            secondary_intents=secondary_intents,
            requires_tools=requires_tools,
            requires_grounding=requires_grounding,
            requires_web=requires_web,
            requires_local_lookup=requires_local_lookup,
            action_type=action_type,  # type: ignore[arg-type]
            confidence=confidence,
            reason_short=reason_short,
            source=source,
        )

    def _normalize_payload(
        self,
        *,
        payload: dict[str, Any],
        fallback: IntentClassification,
        source: str,
        classifier_model: str = "",
    ) -> IntentClassification:
        primary_intent = str(payload.get("primary_intent") or fallback.primary_intent).strip().lower()
        if primary_intent not in _ALLOWED_PRIMARY_INTENTS:
            primary_intent = fallback.primary_intent

        raw_secondary = payload.get("secondary_intents")
        secondary_intents: list[str] = []
        if isinstance(raw_secondary, list):
            for item in raw_secondary:
                text = str(item or "").strip().lower()
                if not text or text in secondary_intents:
                    continue
                secondary_intents.append(text)
                if len(secondary_intents) >= 6:
                    break
        if not secondary_intents:
            secondary_intents = list(fallback.secondary_intents)

        action_type = str(payload.get("action_type") or fallback.action_type).strip().lower()
        if action_type not in _ALLOWED_ACTION_TYPES:
            action_type = fallback.action_type

        confidence_raw = payload.get("confidence", fallback.confidence)
        try:
            confidence = float(confidence_raw)
        except Exception:
            confidence = float(fallback.confidence)
        confidence = max(0.0, min(1.0, confidence))

        return IntentClassification(
            primary_intent=primary_intent,  # type: ignore[arg-type]
            secondary_intents=secondary_intents,
            requires_tools=bool(payload.get("requires_tools", fallback.requires_tools)),
            requires_grounding=bool(payload.get("requires_grounding", fallback.requires_grounding)),
            requires_web=bool(payload.get("requires_web", fallback.requires_web)),
            requires_local_lookup=bool(payload.get("requires_local_lookup", fallback.requires_local_lookup)),
            action_type=action_type,  # type: ignore[arg-type]
            confidence=confidence,
            reason_short=str(payload.get("reason_short") or fallback.reason_short).strip(),
            source=str(payload.get("source") or source or fallback.source).strip() or source or fallback.source,
            classifier_model=str(classifier_model or payload.get("classifier_model") or fallback.classifier_model).strip(),
        )

    def _derive_secondary_intents(self, primary_intent: str, signals: RequestSignals) -> list[str]:
        out: list[str] = []

        def add(value: str) -> None:
            item = str(value or "").strip().lower()
            if item and item not in out:
                out.append(item)

        if signals.web_request:
            add("web_search")
        if signals.source_trace_request or signals.spec_lookup_request or signals.evidence_required:
            add("evidence_lookup")
        if signals.local_code_lookup_request:
            add("code_lookup")
        if signals.has_attachments:
            add("attachment_read")
        if signals.meeting_minutes_request:
            add("meeting_minutes")
        if signals.inline_document_payload:
            add("inline_document")
        if signals.context_dependent_followup:
            add("followup_transform")
        if primary_intent == "generation" and signals.grounded_code_generation_context:
            add("grounded_generation")

        return out[:6]

    def _infer_action_type(
        self,
        *,
        primary_intent: str,
        requires_tools: bool,
        grounded_generation: bool,
    ) -> str:
        if primary_intent in {"evidence", "web"}:
            return "search"
        if primary_intent == "code_lookup":
            return "read"
        if primary_intent == "generation":
            return "modify" if grounded_generation or requires_tools else "create"
        if primary_intent in {"understanding", "meeting_minutes", "qa"}:
            return "answer"
        return "search" if requires_tools else "answer"

    def _estimate_confidence(self, primary_intent: str, signals: RequestSignals) -> float:
        if primary_intent == "evidence" and (signals.source_trace_request or signals.spec_lookup_request or signals.evidence_required):
            return 0.94
        if primary_intent == "web" and signals.web_request:
            return 0.92
        if primary_intent == "code_lookup" and signals.local_code_lookup_request:
            return 0.93
        if primary_intent == "meeting_minutes" and signals.meeting_minutes_request:
            return 0.9
        if primary_intent == "understanding" and signals.has_attachments and signals.understanding_request:
            return 0.9
        if primary_intent == "generation":
            return 0.84 if signals.grounded_code_generation_context else 0.78
        if primary_intent == "qa":
            return 0.78
        if primary_intent == "standard":
            return 0.56
        return 0.72

    def _build_reason_short(self, primary_intent: str, signals: RequestSignals) -> str:
        reasons: list[str] = [f"primary_intent={primary_intent}"]
        if signals.source_trace_request:
            reasons.append("source_trace_request=true")
        if signals.spec_lookup_request:
            reasons.append("spec_lookup_request=true")
        if signals.web_request:
            reasons.append("web_request=true")
        if signals.local_code_lookup_request:
            reasons.append("local_code_lookup_request=true")
        if signals.has_attachments:
            reasons.append("has_attachments=true")
        if signals.inline_followup_context:
            reasons.append("inline_followup_context=true")
        return ", ".join(reasons[:4])

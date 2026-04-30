# PLAN.md — Codex-style Runtime Activity Streaming for Multi_Agent_Team

Branch: `feature/codex-style-activity-streaming`
Date: 2026-04-30
Owner: Codex / Agent
Target repo: `jonhncatt/Multi_Agent_Team`

## Problem Summary

The current activity timeline is mostly status-oriented, so users often only see coarse markers such as model start/end and tool start/end. Non-tool turns provide little observable intermediate state, tool debug views conflate preview with the underlying arguments, and answer streaming feels batched.

Observed stream-path evidence in the current code:

- `app/static/app.js` already appends `item/agentMessage/delta` progressively.
- `app/main.py` already forwards SSE events progressively.
- `app/vintage_programmer_runtime.py` only emits final answer text through `_emit_agent_message_events(...)`.
- `app/codex_runner.py` consumes the provider stream to completion and returns a final AI message, so upstream answer deltas are lost before the runtime emits SSE.

## Root Cause Hypothesis

Primary hypothesis:

- The current trace system exists, but the event taxonomy is too coarse to express meaningful runtime progress for non-tool turns or detailed tool audit state.
- Streaming is first lost at the backend provider/runtime boundary because `CodexResponsesRunner` buffers the streamed response to completion and the runtime only emits a final answer delta.

Secondary hypothesis:

- Tool transparency is limited because `tool_trace_summary` only produces a display preview/summary, and the trace/tool event payloads do not separate raw arguments, preview, and validation state.

This hypothesis is based on code inspection and will be verified with runtime tests and localhost smoke checks.

## Success Criteria

1. Non-tool turns emit visible activity events beyond start/end markers.
2. Tool turns expose tool name, raw arguments, preview, and schema validation result distinctly.
3. Progressive answer deltas are emitted when the backend receives progressive chunks.
4. If upstream still cannot provide progressive chunks for a provider, the evidence path makes that clear.
5. No fabricated hidden chain-of-thought is surfaced.
6. Old trace-event consumers remain compatible.
7. Tests pass.
8. Manual verification shows improved observability without unrelated behavior changes.

## Non-goals

- No migration of the whole repo to a different API surface.
- No app-shell redesign.
- No parallel runtime architecture.
- No broad refactor outside runtime activity streaming, tool audit detail, and frontend rendering.
- No fake reasoning stream.

## Implementation Phases

### Phase 1 — Observability Baseline

- Add normalized activity-event helpers in `app/trace_events.py`.
- Add stream diagnostics timestamps/metadata around provider chunk receipt and runtime event emission.
- Keep existing trace events compatible while introducing richer activity payload structure.

### Phase 2 — Runtime Activity Events

- Emit runtime-known activity stages for both tool and non-tool turns.
- Add answer lifecycle events such as `answer.started`, `answer.delta`, and `answer.done`.
- Add non-tool runtime stages such as request analysis, tool decision, and direct answer generation.

### Phase 3 — Tool Audit Split

- Extend tool activity payloads with `raw_arguments`, `arguments_preview`, `preview_error`, and `schema_validation`.
- Derive validation from existing tool descriptors/schemas where available.
- Ensure preview failure never discards raw arguments.

### Phase 4 — Frontend Timeline and Delta Rendering

- Preserve incremental answer rendering instead of replacing whole messages.
- Render expandable detail sections for activity events and tool audit detail.
- Keep current timeline structure but enrich the card content.

### Phase 5 — Regression Coverage and Manual Verification

- Add/update unit and integration tests for streaming, activity events, and schema validation.
- Run localhost smoke checks for a no-tool turn and a tool turn.

## Tests

- `pytest -q`
- `node --check app/static/app.js`
- Focused runtime/trace/tool summary tests while iterating
- Manual localhost stream check through the in-app browser

## Risks

- UI noise from too many events
- Render churn from frequent deltas
- Schema validation drifting from actual tool definitions
- Confusing users by over-labeling summary content as “reasoning”

Mitigation:

- Keep the taxonomy compact and collapse verbose details by default.
- Use a small frontend paint buffer only if necessary, without losing semantic events.
- Prefer existing tool descriptor schema sources.
- Label only runtime-known live stages and label any post-answer summaries explicitly.

## Verification Commands

- `git status`
- `pytest -q`
- `node --check app/static/app.js`
- `git log --oneline -5`

## Final Report Format

1. Branch name
2. Root cause
3. Files changed
4. Exact fix summary
5. Tests run
6. Manual verification result
7. Git status
8. Latest commits

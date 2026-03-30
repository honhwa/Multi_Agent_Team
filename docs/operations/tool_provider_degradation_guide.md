# Tool Provider Degradation Guide

## Purpose

Tools are stable capability names. Providers are replaceable implementations behind those tools.

The runtime contract is:

```text
business module
  -> ToolRuntimeModule / ToolBus
  -> ToolRegistry
  -> ProviderRegistry
  -> provider.execute(ToolCall)
```

## State Model

Providers can be in one of these runtime states:

- `ready`
- `degraded`
- `disabled`
- `circuit_open`

`ProviderRegistry.record_failure(...)` increments a failure counter. After repeated failures, the provider is marked degraded and the circuit opens.

## What Counts As A Failure

The ToolBus marks failures when:

- the provider times out
- the provider raises `ProviderUnavailableError`
- the provider raises any other exception
- the provider returns an unsuccessful `ToolResult`

## Fallback Behavior

Fallback happens in two layers:

1. Ordered providers for the same tool
2. Explicit fallback tools from `ToolCall.fallback_tools`

The ToolBus records fallback and provider failure events on the kernel trace.

## Operational Rules

- Do not let modules import providers directly.
- Register a `ToolContract` before routing a new tool.
- Prefer one primary provider and a small fallback set.
- Degrade aggressively on repeated provider failures.
- Keep provider health checks cheap and deterministic.

## Standard Contracts

Current formal tools are registered in [`app/bootstrap/assemble.py`](../../app/bootstrap/assemble.py).

Current provider implementations live under [`app/tool_providers/`](../../app/tool_providers).

## How To Debug A Provider Incident

1. Run the minimal demo if the issue is in workspace access.
2. Inspect `recent_traces` from the kernel health snapshot.
3. Look for `provider_failed`, `provider_circuit_open`, and `tool_fallback` events.
4. Check the provider state in `registry.provider_states`.
5. Roll back or disable the provider before changing module logic.

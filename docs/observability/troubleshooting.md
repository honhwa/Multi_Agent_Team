# Troubleshooting Guide

## Start With The Smallest Repro

Use the minimal demo first:

```bash
python scripts/demo_minimal_agent_os.py --check
```

If that fails, the issue is below the LLM layer and usually sits in KernelHost, ToolRegistry, ProviderRegistry, or workspace access.

## Where To Look

- request path: [`docs/architecture/current_execution_path.md`](../architecture/current_execution_path.md)
- trace fields: [`docs/observability/trace_guide.md`](trace_guide.md)
- tool/provider degradation: [`docs/operations/tool_provider_degradation_guide.md`](../operations/tool_provider_degradation_guide.md)

## Common Failure Modes

### Module not found

Symptoms:

- `business module not found`
- trace stops before `module_complete`

Check:

- module registration in `assemble_runtime()`
- manifest validation
- `KernelHost.resolve_module(...)`

### Provider degraded or circuit open

Symptoms:

- tool dispatch happens but no successful result arrives
- trace contains `provider_failed` or `provider_circuit_open`

Check:

- `kernel.health_snapshot()['registry']['provider_states']`
- provider health check
- fallback provider availability

### Trace exists but is not detailed enough

Set:

- `AGENT_OS_TRACE=1`
- `AGENT_OS_TRACE_VERBOSE=1`

Then inspect `artifacts/agent_os_traces/`.

### HTTP service runs but product path feels wrong

Check whether you are using the correct entrypoint:

- day-to-day app: `./run.sh` or `./run.ps1`
- role lab: `./run-role-agent-lab.sh`
- kernel view: `./run-kernel-robot.sh`

## Escalation Order

1. minimal demo
2. kernel trace
3. provider state
4. module health
5. full HTTP/UI reproduction

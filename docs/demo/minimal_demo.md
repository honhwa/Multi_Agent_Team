# Minimal Demo

## Purpose

This is the shortest product demo for the current Agent OS path.

It proves:

```text
KernelHost.dispatch
  -> office_module.handle
  -> tool_runtime_module.execute
  -> LocalWorkspaceProvider
  -> TaskResponse + trace
```

## Command

```bash
python scripts/demo_minimal_agent_os.py --check
```

Optional JSON output:

```bash
python scripts/demo_minimal_agent_os.py --json
```

## Expected Result

A successful run reports:

- `module_id: office_module`
- `tool: workspace.read`
- `provider: local_workspace_provider`
- `trace_outcome: ok`

## Why This Matters

If this demo passes but the full chat flow fails, the problem is usually above the kernel/tool-provider boundary.
If this demo fails, fix the runtime boundary before tuning prompts or router heuristics.

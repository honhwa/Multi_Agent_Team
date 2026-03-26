# Module Integration Guide

## Goal

A business module should be pluggable without changing `KernelHost` behavior.

The integration contract is:

```text
ModuleManifest
  + handle(TaskRequest, RuntimeContext) -> TaskResponse
  + health_check()
  + init(kernel_context)
  + shutdown()
```

## Required Files

A production module should provide:

- `module.py`: formal module entrypoint
- `manifest.py` or `module.json`: declarative metadata
- `pipeline/`: module-local execution stages
- `policies/`: module-local policy catalog
- `tests/`: module contract and integration coverage

`office_module` is the reference implementation:

- [`app/business_modules/office_module/module.py`](/Users/dalizhou/Desktop/new_validation_agent/app/business_modules/office_module/module.py)
- [`app/business_modules/office_module/module.json`](/Users/dalizhou/Desktop/new_validation_agent/app/business_modules/office_module/module.json)
- [`app/business_modules/office_module/manifest.py`](/Users/dalizhou/Desktop/new_validation_agent/app/business_modules/office_module/manifest.py)

## Manifest Checklist

At minimum, define:

- `module_id`
- `module_kind`
- `version`
- `description`
- `capabilities`
- `required_tools`
- `optional_tools`
- `required_system_modules`
- `healthcheck`
- `rollback_strategy`
- `owner`
- `compatibility_level`

Kernel startup validates the manifest before the module becomes runnable.

## Registration Path

1. Add the module implementation.
2. Register it in [`app/bootstrap/assemble.py`](/Users/dalizhou/Desktop/new_validation_agent/app/bootstrap/assemble.py).
3. Ensure `KernelHost.init()` can initialize and health-check it.
4. Cover the module with tests under `tests/modules/` and at least one integration test under `tests/integration/`.

## Runtime Rules

- Modules receive requests only through `KernelHost.dispatch(...)`.
- Modules must not call providers directly.
- External capability usage must go through `ToolRuntimeModule` or `ToolBus`.
- Module-specific router/planner/worker logic stays inside the module boundary.
- Compatibility delegation must be explicit and marked as shim.

## Testing Checklist

For every new or changed module, verify:

- manifest validation
- health check behavior
- `handle(...)` happy path
- degraded path
- tool usage through `ToolRegistry`
- compatibility shim behavior if still present

Use the current suite as the baseline:

- `pytest -q tests/modules`
- `pytest -q tests/integration`

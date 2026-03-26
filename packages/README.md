# Packages Boundary Guide

## Canonical Python Packages

These are the formal import targets:

- `packages.agent_core`
- `packages.office_modules`
- `packages.runtime_core`

These should be treated as the stable Python package layer.

## Product Shells

These directories are product-facing shells, not shared runtime libraries:

- `packages/kernel-robot`
- `packages/role-agent-lab`

They are consumers of the runtime, not the runtime itself.

## Experimental Or Internal Packages

- `packages/office_addons`

This area is currently internal and should not be treated as a stable external API.

## Compatibility Placeholders

These directories exist only to document or bridge old distribution names:

- `packages/agent-core`
- `packages/office-modules`
- `packages/runtime-core`

Do not import from them in Python code.

## Removal Direction

- keep snake_case directories as the canonical implementation
- keep hyphenated directories as documentation-only placeholders during migration
- remove compatibility placeholders once external references are updated

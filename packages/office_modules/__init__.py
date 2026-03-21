from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.runtime_core import CapabilityBundle

from .roles import build_office_role_registry
from .tools import get_tool_executor


def _manifest_path() -> Path:
    return (Path(__file__).resolve().parent / "manifest.json").resolve()


def read_office_manifest() -> dict[str, Any]:
    return json.loads(_manifest_path().read_text(encoding="utf-8"))


def build_capability_bundle(*, config: Any | None = None) -> CapabilityBundle:
    manifest = read_office_manifest()
    metadata = {
        "profiles": list(manifest.get("profiles") or []),
        "tools": list(manifest.get("tools") or []),
        "roles": list(manifest.get("roles") or []),
    }
    return CapabilityBundle(
        module_id=str(manifest.get("module_id") or "office_modules"),
        version=str(manifest.get("version") or "0.1.0"),
        manifest=manifest,
        build_role_registry=build_office_role_registry,
        tool_executor_factory=get_tool_executor,
        metadata=metadata,
    )


def load_office_capability_bundle(*, config: Any | None = None) -> CapabilityBundle:
    return build_capability_bundle(config=config)


__all__ = [
    "build_capability_bundle",
    "build_office_role_registry",
    "get_tool_executor",
    "load_office_capability_bundle",
    "read_office_manifest",
]

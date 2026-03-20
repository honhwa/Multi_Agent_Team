from __future__ import annotations

from typing import Any


class ToolRegistryModule:
    module_id = "tool_registry"
    version = "1.0.0"

    def build_langchain_tools(self, *, agent: Any) -> list[Any]:
        return agent._build_langchain_tools()

    def describe_tools(self, *, agent: Any) -> dict[str, Any]:
        tools = list(getattr(agent, "_lc_tools", None) or self.build_langchain_tools(agent=agent))
        items: list[dict[str, Any]] = []
        for tool in tools:
            items.append(
                {
                    "name": str(getattr(tool, "name", "") or ""),
                    "description": str(getattr(tool, "description", "") or "")[:200],
                }
            )
        return {
            "module_id": self.module_id,
            "version": self.version,
            "tool_count": len(items),
            "tools": items,
        }

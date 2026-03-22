from __future__ import annotations

from typing import Any

from packages.runtime_core.capability_loader import ToolModule

from app.local_tools import LocalToolExecutor


def get_tool_executor(config: Any) -> LocalToolExecutor:
    return LocalToolExecutor(config)


def build_office_tool_modules() -> tuple[ToolModule, ...]:
    return (
        ToolModule(
            module_id="office_tools",
            title="Office Tool Module",
            description="默认办公工具模块，当前封装 LocalToolExecutor。",
            build_executor=get_tool_executor,
            default=True,
            tool_names=(
                "run_shell",
                "list_directory",
                "read_text_file",
                "search_codebase",
                "search_web",
                "write_text_file",
            ),
            metadata={"family": "office", "executor": "LocalToolExecutor"},
        ),
    )

from __future__ import annotations

from typing import Any

from app.local_tools import LocalToolExecutor


def get_tool_executor(config: Any) -> LocalToolExecutor:
    return LocalToolExecutor(config)

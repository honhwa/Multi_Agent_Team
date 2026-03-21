from packages.agent_core.role_registry import RegisteredRole, RoleHandler, RoleRegistry
from packages.office_modules.roles import build_office_role_registry as build_default_role_registry

__all__ = [
    "RegisteredRole",
    "RoleHandler",
    "RoleRegistry",
    "build_default_role_registry",
]

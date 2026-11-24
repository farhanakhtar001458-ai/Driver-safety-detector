"""Role-based access control.

Roles are fixed platform roles; permission grants are data-driven so a super
administrator can adjust them at runtime (stored in the ``roles`` /
``permissions`` tables). This module exposes the default matrix used to seed
the database and fast in-code checks for request authorisation.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, FrozenSet


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    FLEET_MANAGER = "fleet_manager"
    SAFETY_OFFICER = "safety_officer"
    DRIVER = "driver"


ROLE_LABELS: Dict[str, str] = {
    UserRole.SUPER_ADMIN.value: "Super Admin",
    UserRole.ORG_ADMIN.value: "Organisation Admin",
    UserRole.FLEET_MANAGER.value: "Fleet Manager",
    UserRole.SAFETY_OFFICER.value: "Safety Officer",
    UserRole.DRIVER.value: "Driver",
}

# Every permission used anywhere in the API. Grouped by resource.
ALL_PERMISSIONS: list[str] = [
    "dashboard:read",
    "vehicles:read", "vehicles:create", "vehicles:update", "vehicles:delete",
    "drivers:read", "drivers:create", "drivers:update", "drivers:delete",
    "tracking:read", "tracking:manage",
    "behaviour:read", "behaviour:configure",
    "scores:read", "scores:configure",
    "risk:read", "risk:assess",
    "incidents:read", "incidents:create", "incidents:manage",
    "maintenance:read", "maintenance:manage",
    "reports:read", "reports:generate",
    "notifications:read", "notifications:manage",
    "assistant:use",
    "road_safety:read", "road_safety:report",
    "team:read", "team:manage",
    "settings:read", "settings:manage",
    "billing:read", "billing:manage",
    "audit:read",
    "ai_models:read", "ai_models:manage",
    "organisations:manage",
    "subscriptions:manage",
]

_READ_ONLY = {"dashboard:read"}

DEFAULT_PERMISSIONS: Dict[UserRole, FrozenSet[str]] = {
    UserRole.SUPER_ADMIN: frozenset(ALL_PERMISSIONS),
    UserRole.ORG_ADMIN: frozenset(ALL_PERMISSIONS) - {
        "organisations:manage",
        "subscriptions:manage",
        "ai_models:manage",
    },
    UserRole.FLEET_MANAGER: frozenset(
        {
            "dashboard:read",
            "vehicles:read", "vehicles:create", "vehicles:update",
            "drivers:read",
            "tracking:read", "tracking:manage",
            "behaviour:read",
            "scores:read",
            "risk:read", "risk:assess",
            "incidents:read", "incidents:create", "incidents:manage",
            "maintenance:read", "maintenance:manage",
            "reports:read", "reports:generate",
            "notifications:read",
            "assistant:use",
            "road_safety:read",
            "team:read",
        }
    ),
    UserRole.SAFETY_OFFICER: frozenset(
        {
            "dashboard:read",
            "vehicles:read",
            "drivers:read",
            "tracking:read",
            "behaviour:read",
            "scores:read",
            "risk:read", "risk:assess",
            "incidents:read", "incidents:create", "incidents:manage",
            "reports:read", "reports:generate",
            "notifications:read",
            "assistant:use",
            "road_safety:read", "road_safety:report",
        }
    ),
    UserRole.DRIVER: frozenset(
        {
            "dashboard:read",
            "vehicles:read",
            "drivers:read",
            "tracking:read",
            "behaviour:read",
            "scores:read",
            "risk:read",
            "reports:read",
            "notifications:read", "notifications:manage",
            "assistant:use",
            "road_safety:read",
        }
    ),
}

MANAGEABLE_ROLES_BY_ROLE: Dict[UserRole, FrozenSet[UserRole]] = {
    UserRole.SUPER_ADMIN: frozenset(UserRole),
    UserRole.ORG_ADMIN: frozenset(
        {UserRole.FLEET_MANAGER, UserRole.SAFETY_OFFICER, UserRole.DRIVER, UserRole.ORG_ADMIN}
    ),
    UserRole.FLEET_MANAGER: frozenset({UserRole.DRIVER}),
    UserRole.SAFETY_OFFICER: frozenset(),
    UserRole.DRIVER: frozenset(),
}


def permissions_for(role: str | UserRole) -> FrozenSet[str]:
    role_value = role.value if isinstance(role, UserRole) else str(role)
    try:
        return DEFAULT_PERMISSIONS[UserRole(role_value)]
    except KeyError:
        return frozenset()


def role_has_permission(role: str | UserRole, permission: str) -> bool:
    perms = permissions_for(role)
    if "*" in perms:
        return True
    if permission in perms:
        return True
    # resource-level wildcard e.g. "vehicles:*"
    resource = permission.split(":")[0]
    return f"{resource}:*" in perms


def can_assign_role(actor_role: str | UserRole, target_role: str | UserRole) -> bool:
    try:
        actor = UserRole(actor_role.value if isinstance(actor_role, UserRole) else actor_role)
        target = UserRole(target_role.value if isinstance(target_role, UserRole) else target_role)
    except ValueError:
        return False
    return target in MANAGEABLE_ROLES_BY_ROLE.get(actor, frozenset())

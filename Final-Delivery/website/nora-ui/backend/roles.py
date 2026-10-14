"""Canonical administrative roles and their server-enforced permissions."""

from __future__ import annotations

from typing import Final

ROLE_OWNER: Final = "owner"
ROLE_MANAGER: Final = "manager"
ROLE_CLUB_SUPERVISOR: Final = "club-supervisor"
ROLE_KEYS: Final = (ROLE_OWNER, ROLE_MANAGER, ROLE_CLUB_SUPERVISOR)
ASSIGNABLE_ROLE_KEYS: Final = (ROLE_MANAGER, ROLE_CLUB_SUPERVISOR)

# These keys follow the existing permission catalogue in nora-ui/data.js.
_MANAGER_PERMISSIONS = frozenset(
    {
        "ev_create",
        "ev_publish",
        "ev_cancel",
        "attendance",
        "certificate",
        "fm_create",
        "fm_responses",
        "fm_export",
        "receipt_approve",
        "us_view",
        "us_edit",
        "us_approve",
        "us_block",
        "us_notes",
        "us_export",
        "sp_answer",
        "sp_reopen",
        "qa_audit",
        "qa_complaint",
        "qa_quality",
        "qa_fix",
        "qa_report",
        "bc_send",
        "bc_event",
        "pr_media",
        "pr_campaign",
        "pr_invite",
        "dev_course",
        "dev_process",
        "dev_kpi",
        "dev_review",
        "rp_view",
        "rp_export",
    }
)
_CLUB_PERMISSIONS = frozenset({"cl_member", "cl_session", "cl_cert", "cl_content"})
_UNRESOLVED_NON_OWNER_PERMISSIONS = frozenset({"cl_dues", "sys_points"})
_OWNER_ONLY_PERMISSIONS = frozenset(
    {
        "finance",
        "role_assign",
        "sys_fields",
        "sys_settings",
        "sys_backup",
        "cert_final",
        "user_delete",
        "public_roster",
    }
)

_ALL_PERMISSIONS = frozenset(
    _MANAGER_PERMISSIONS
    | _CLUB_PERMISSIONS
    | _UNRESOLVED_NON_OWNER_PERMISSIONS
    | _OWNER_ONLY_PERMISSIONS
)
_ROLE_PERMISSIONS: Final = {
    ROLE_OWNER: _ALL_PERMISSIONS,
    ROLE_MANAGER: _MANAGER_PERMISSIONS,
    ROLE_CLUB_SUPERVISOR: _MANAGER_PERMISSIONS | _CLUB_PERMISSIONS,
}


def permissions_for_role(role: str | None) -> frozenset[str]:
    """Return permissions for a recognized role; unknown/absent roles deny all."""
    return _ROLE_PERMISSIONS.get(role or "", frozenset())


def has_permission(role: str | None, permission: str) -> bool:
    return permission in permissions_for_role(role)


def is_assignable_role(role: object) -> bool:
    return isinstance(role, str) and role in ASSIGNABLE_ROLE_KEYS

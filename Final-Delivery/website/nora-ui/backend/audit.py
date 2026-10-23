"""Append-only administrative audit trail.

Every sensitive owner/manager action records *who* (owner id or account id and
role), *what* (action + target) and *the outcome*. Payloads are reduced to a
small, scalar-only ``details`` dictionary and anything that looks like
credential material is dropped before it reaches the database, so the trail
can never leak passwords, tokens or uploaded content.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AdminAuditEventRecord

ACTOR_OWNER = "owner"
ACTOR_ACCOUNT = "account"

# Keys that may never be persisted, whatever the caller passes.
_FORBIDDEN_KEY_PARTS = ("password", "secret", "token", "credential", "hash", "value", "cookie", "csrf")
_MAX_DETAIL_KEYS = 12
_MAX_DETAIL_TEXT = 160

# Catalogue of actions the panel knows how to label. Unknown actions are still
# stored (the API is additive) but kept to this character class.
ACTIONS = frozenset(
    {
        "role.set",
        "role.clear",
        "manager_credentials.set",
        "manager_credentials.remove",
        "service_secret.store",
        "service_secret.clear",
        "service_secret.test",
        "workflow.decide",
        "form.publish",
        "form.pause",
        "form.response.delete",
        "backup.upload",
        "backup.audit",
        "backup.delete",
        "site_content.update",
        "content.create",
        "content.update",
        "content.status",
        "attendance.check_in",
        "attendance.undo_check_in",
        "cooperation_request.update",
    }
)


def sanitize_details(details: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep only short scalar values under non-sensitive keys."""
    cleaned: dict[str, Any] = {}
    if not details:
        return cleaned
    for key, value in details.items():
        name = str(key)
        lowered = name.lower()
        if any(part in lowered for part in _FORBIDDEN_KEY_PARTS):
            continue
        if isinstance(value, bool) or value is None:
            cleaned[name] = value
        elif isinstance(value, (int, float)):
            cleaned[name] = value
        elif isinstance(value, str):
            cleaned[name] = value[:_MAX_DETAIL_TEXT]
        else:
            continue
        if len(cleaned) >= _MAX_DETAIL_KEYS:
            break
    return cleaned


def record_admin_event(
    db: Session,
    *,
    actor_kind: str,
    actor_id: str,
    actor_role: str,
    action: str,
    target_type: str = "",
    target_id: str = "",
    outcome: str = "ok",
    details: Mapping[str, Any] | None = None,
) -> AdminAuditEventRecord:
    """Add one audit row to the current transaction (caller commits)."""
    if actor_kind not in (ACTOR_OWNER, ACTOR_ACCOUNT):
        raise ValueError("invalid_audit_actor")
    record = AdminAuditEventRecord(
        id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
        actor_kind=actor_kind,
        actor_id=str(actor_id)[:120],
        actor_role=str(actor_role or "")[:32],
        action=str(action)[:64],
        target_type=str(target_type or "")[:32],
        target_id=str(target_id or "")[:120],
        outcome=str(outcome or "ok")[:32],
        details=sanitize_details(details),
    )
    db.add(record)
    return record


def audit_event_view(record: AdminAuditEventRecord) -> dict[str, Any]:
    created = record.created_at
    if created is not None and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return {
        "id": record.id,
        "created_at": created.isoformat() if created else None,
        "actor_kind": record.actor_kind,
        "actor_id": record.actor_id,
        "actor_role": record.actor_role,
        "action": record.action,
        "target_type": record.target_type,
        "target_id": record.target_id,
        "outcome": record.outcome,
        "details": dict(record.details or {}),
    }


def list_admin_events(
    db: Session,
    *,
    limit: int,
    offset: int,
    action: str = "",
    target_type: str = "",
    target_id: str = "",
) -> tuple[list[AdminAuditEventRecord], bool]:
    query = select(AdminAuditEventRecord)
    if action.endswith("."):
        # Group filter such as ``role.`` or ``workflow.``: every action in that family.
        # The prefix is validated upstream to ``[a-z_.]`` so it contains no LIKE wildcards.
        query = query.where(AdminAuditEventRecord.action.like(action + "%"))
    elif action:
        query = query.where(AdminAuditEventRecord.action == action)
    if target_type:
        query = query.where(AdminAuditEventRecord.target_type == target_type)
    if target_id:
        # پروندهٔ کاربر (ممیزی C5): فقط رویدادهایی که هدفشان دقیقاً همین شناسه است؛ بدون LIKE و بدون حدس.
        query = query.where(AdminAuditEventRecord.target_id == target_id)
    rows = db.scalars(
        query.order_by(AdminAuditEventRecord.created_at.desc(), AdminAuditEventRecord.id)
        .offset(offset)
        .limit(limit + 1)
    ).all()
    return list(rows[:limit]), len(rows) > limit

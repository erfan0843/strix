"""Link server-side review decisions back to rows imported from this SQLite DB."""
from __future__ import annotations

from typing import Any, Callable


_SPECS = {
    "profile_review": {
        "table": "profile_submissions",
        "id_key": "_legacy_profile_submission_id",
        "reason_column": "rejection_reason",
    },
    "receipt_review": {
        "table": "payment_receipts",
        "id_key": "_legacy_receipt_id",
        "reason_column": "reject_reason",
    },
}


def project_legacy_review(
    kind: str,
    task: dict[str, Any],
    decision: str,
    *,
    db_execute: Callable[..., Any],
) -> bool:
    """Project an authorized API decision only onto its matching imported row.

    Returns ``False`` when the task is not a migration task or the local row no
    longer matches. A failed eligible write raises so callers do not silently
    claim the local projection succeeded.
    """
    spec = _SPECS.get(kind)
    if spec is None or decision not in {"approved", "rejected"}:
        return False
    payload = task.get("payload")
    if not isinstance(payload, dict):
        return False
    raw_row_id = payload.get(spec["id_key"])
    try:
        row_id = int(raw_row_id)
    except (TypeError, ValueError, OverflowError):
        return False
    task_id = task.get("id")
    source_id = payload.get("_legacy_source_id")
    if row_id <= 0 or not isinstance(task_id, str) or not task_id:
        return False
    if not isinstance(source_id, str) or not source_id:
        return False

    source = db_execute(
        "SELECT value FROM nora_legacy_migration_meta WHERE key='source_id'",
        fetch="one",
    )
    if not source or source.get("value") != source_id:
        return False
    table = spec["table"]
    row = db_execute(
        f"SELECT status, shared_task_id FROM {table} WHERE id=?",
        (row_id,),
        fetch="one",
    )
    if (not row or row.get("status") != "pending"
            or row.get("shared_task_id") not in (None, "", task_id)):
        return False

    reason = task.get("review_reason") if decision == "rejected" else None
    reviewed_by = task.get("reviewed_by_bale_user_id")
    reason_column = spec["reason_column"]
    db_execute(
        f"UPDATE {table} SET status=?, reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP, "
        f"{reason_column}=?, shared_task_id=? WHERE id=? AND status='pending' "
        "AND COALESCE(shared_task_id,'') IN ('',?)",
        (decision, reviewed_by, reason, task_id, row_id, task_id),
    )
    projected = db_execute(
        f"SELECT status, shared_task_id FROM {table} WHERE id=?",
        (row_id,),
        fetch="one",
    )
    if (not projected or projected.get("status") != decision
            or projected.get("shared_task_id") != task_id):
        raise RuntimeError("legacy_review_projection_failed")
    return True

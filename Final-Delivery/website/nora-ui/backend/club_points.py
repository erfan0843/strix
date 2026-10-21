"""Shared mirror of the Bale bot's points ledger: helpers for the bot sync API and the read-only panel.

The bot's SQLite ``points_ledger`` is the only place where club points are
created, spent or corrected. This module never computes, awards or changes
points; it stores verified copies (:class:`backend.models.ClubPointsEntryRecord`)
whose owner is resolved **server-side** from the Bale user id through
``platform_identities`` – never from a client-supplied account id. Entries of
people without a server identity are not stored (the bot keeps them as
``unmapped`` and retries after the person links an account).

Honesty rules for the panel:
* a balance is only ever the ``balance_after`` of the newest mirrored entry;
* ``history_complete`` is derived from the balance chain of the mirrored rows
  (first row must start from zero, every row must continue the previous one);
  anything else is reported as partial, never silently filled.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping
import unicodedata
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    AccountProfileRecord,
    AccountRecord,
    ClubPointsEntryRecord,
    PlatformIdentityRecord,
)

SOURCE = "shared_server_database"
ENTRY_TYPES = ("opening_balance", "award", "spend", "refund", "reversal", "manual_adjust")
ACTOR_KINDS = ("system", "admin", "user")
EXTERNAL_KEY_RE = re.compile(r"[A-Za-z0-9:_-]{3,120}")
BALE_USER_ID_RE = re.compile(r"[1-9][0-9]{0,19}")
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}")
SOURCE_RE = re.compile(r"[a-z][a-z0-9_]{1,39}")
REF_KEY_RE = re.compile(r"[A-Za-z0-9:_.\-]{1,200}")
_ENTRY_FIELDS = {
    "ledger_id", "delta", "balance_after", "entry_type", "source", "ref_key", "reason",
    "actor_kind", "reverses_external_key", "created_at",
}
_IMMUTABLE_FIELDS = ("ledger_id", "delta", "balance_after", "entry_type", "source", "ref_key",
                     "reverses_external_key")
_MAX_ABS = 1_000_000_000


class ClubPointsError(ValueError):
    """Validation failure; ``code`` is the stable API error code."""

    def __init__(self, code: str, status_code: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _int(value: Any, field: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ClubPointsError(f"invalid_{field}")
    if abs(value) > _MAX_ABS or (minimum is not None and value < minimum):
        raise ClubPointsError(f"invalid_{field}")
    return value


def _text(value: Any, field: str, limit: int, *, required: bool = False) -> str:
    if value is None:
        if required:
            raise ClubPointsError(f"invalid_{field}")
        return ""
    if not isinstance(value, str):
        raise ClubPointsError(f"invalid_{field}")
    text = unicodedata.normalize("NFKC", value).replace("\x00", "").strip()
    if len(text) > limit or (required and not text):
        raise ClubPointsError(f"invalid_{field}")
    return text


def resolve_owner(db: Session, bale_user_id: str) -> AccountRecord | None:
    """Existing server account for a Bale id; never creates one (no auto-matching)."""
    if not BALE_USER_ID_RE.fullmatch(bale_user_id or ""):
        raise ClubPointsError("invalid_bale_user_id")
    identity = db.scalar(
        select(PlatformIdentityRecord).where(
            PlatformIdentityRecord.provider == "bale",
            PlatformIdentityRecord.provider_user_id == bale_user_id,
        )
    )
    if identity is None:
        return None
    return db.get(AccountRecord, identity.account_id)


def validate_submission(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize the bot payload; raises :class:`ClubPointsError` on anything unexpected."""
    if set(payload) - {"bale_user_id", "external_key", "entry"} or {"bale_user_id", "external_key", "entry"} - set(payload):
        raise ClubPointsError("invalid_points_payload", 400)
    raw_user_id = payload.get("bale_user_id")
    if isinstance(raw_user_id, bool) or not isinstance(raw_user_id, (str, int)):
        raise ClubPointsError("invalid_bale_user_id")
    bale_user_id = str(raw_user_id)
    if not BALE_USER_ID_RE.fullmatch(bale_user_id):
        raise ClubPointsError("invalid_bale_user_id")
    external_key = payload.get("external_key")
    if not isinstance(external_key, str) or not EXTERNAL_KEY_RE.fullmatch(external_key):
        raise ClubPointsError("invalid_external_key")
    source_id, _, ledger_part = external_key.rpartition(":")
    if not source_id or not UUID_RE.fullmatch(source_id) or not ledger_part.isdigit():
        raise ClubPointsError("invalid_external_key")
    data = payload.get("entry")
    if not isinstance(data, dict) or set(data) - _ENTRY_FIELDS:
        raise ClubPointsError("invalid_points_entry")
    fields: dict[str, Any] = {"source_id": source_id}
    fields["ledger_id"] = _int(data.get("ledger_id"), "ledger_id", minimum=1)
    if fields["ledger_id"] != int(ledger_part):
        raise ClubPointsError("invalid_external_key")
    fields["delta"] = _int(data.get("delta"), "delta")
    fields["balance_after"] = _int(data.get("balance_after"), "balance_after")
    entry_type = data.get("entry_type")
    if entry_type not in ENTRY_TYPES:
        raise ClubPointsError("invalid_entry_type")
    fields["entry_type"] = entry_type
    if fields["delta"] == 0 and entry_type != "opening_balance":
        raise ClubPointsError("invalid_delta")
    source = data.get("source")
    if not isinstance(source, str) or not SOURCE_RE.fullmatch(source):
        raise ClubPointsError("invalid_source")
    fields["source"] = source
    ref_key = data.get("ref_key")
    if not isinstance(ref_key, str) or not REF_KEY_RE.fullmatch(ref_key):
        raise ClubPointsError("invalid_ref_key")
    fields["ref_key"] = ref_key
    fields["reason"] = _text(data.get("reason"), "reason", 500)
    actor_kind = data.get("actor_kind", "system")
    if actor_kind not in ACTOR_KINDS:
        raise ClubPointsError("invalid_actor_kind")
    fields["actor_kind"] = actor_kind
    reverses = data.get("reverses_external_key")
    if reverses is not None and (not isinstance(reverses, str) or not EXTERNAL_KEY_RE.fullmatch(reverses)):
        raise ClubPointsError("invalid_reverses_external_key")
    if entry_type == "reversal" and not reverses:
        raise ClubPointsError("invalid_reverses_external_key")
    fields["reverses_external_key"] = reverses or None
    fields["bot_created_at"] = _text(data.get("created_at"), "created_at", 40)
    return {"bale_user_id": bale_user_id, "external_key": external_key, "fields": fields}


def upsert(db: Session, submission: Mapping[str, Any]) -> tuple[ClubPointsEntryRecord, bool]:
    """Store the mirror row once. Owner must already exist; an existing key with different data is rejected."""
    account = resolve_owner(db, submission["bale_user_id"])
    if account is None:
        raise ClubPointsError("owner_identity_not_found", 404)
    fields = dict(submission["fields"])
    record = db.scalar(
        select(ClubPointsEntryRecord).where(ClubPointsEntryRecord.external_key == submission["external_key"])
    )
    if record is not None:
        if record.account_id != account.id or record.bale_user_id != submission["bale_user_id"]:
            raise ClubPointsError("points_entry_owner_mismatch", 409)
        for name in _IMMUTABLE_FIELDS:
            if getattr(record, name) != fields[name]:
                raise ClubPointsError("points_entry_conflict", 409)
        record.synced_at = _utc_now()
        db.flush()
        return record, False
    record = ClubPointsEntryRecord(
        id=str(uuid.uuid4()), account_id=account.id, bale_user_id=submission["bale_user_id"],
        external_key=submission["external_key"], **fields,
    )
    db.add(record)
    db.flush()
    return record, True


def _display_names(db: Session, account_ids: set[str]) -> dict[str, str]:
    if not account_ids:
        return {}
    return {
        account_id: str(((fields or {}).get("fullName") or ""))[:120]
        for account_id, fields in db.execute(
            select(AccountProfileRecord.account_id, AccountProfileRecord.fields).where(
                AccountProfileRecord.account_id.in_(account_ids)
            )
        ).all()
    }


def row(record: ClubPointsEntryRecord, *, display_name: str = "") -> dict[str, Any]:
    """Panel representation; no phone, no token, no raw admin id."""
    return {
        "id": record.id,
        "external_key": record.external_key,
        "ledger_id": record.ledger_id,
        "delta": record.delta,
        "balance_after": record.balance_after,
        "entry_type": record.entry_type,
        "source": record.source,
        "ref_key": record.ref_key,
        "reason": record.reason,
        "actor_kind": record.actor_kind,
        "reverses_external_key": record.reverses_external_key,
        "bot_created_at": record.bot_created_at or None,
        "synced_at": _iso(record.synced_at),
        "holder": {
            "account_id": record.account_id,
            "bale_user_id": record.bale_user_id,
            "display_name": display_name,
            "name_source": "profile" if display_name else "none",
        },
    }


def chain_summary(entries: list[ClubPointsEntryRecord]) -> dict[str, Any]:
    """Derive what the mirror can honestly say about one person from the balance chain.

    ``entries`` must be the person's mirrored rows ordered by ``ledger_id``.
    """
    if not entries:
        return {"entries": 0, "latest_balance": None, "latest_ledger_id": None,
                "history_complete": False, "chain_breaks": 0, "has_opening": False}
    breaks = 0
    expected = 0
    for item in entries:
        if expected + item.delta != item.balance_after:
            breaks += 1
        expected = item.balance_after
    last = entries[-1]
    return {
        "entries": len(entries),
        "latest_balance": last.balance_after,
        "latest_ledger_id": last.ledger_id,
        "latest_bot_created_at": last.bot_created_at or None,
        "latest_synced_at": _iso(last.synced_at),
        "history_complete": breaks == 0,
        "chain_breaks": breaks,
        "has_opening": any(item.entry_type == "opening_balance" for item in entries),
    }


def list_entries(
    db: Session, *, account_id: str = "", bale_user_id: str = "", entry_type: str = "",
    q: str = "", limit: int = 20, offset: int = 0,
) -> dict[str, Any]:
    query = select(ClubPointsEntryRecord)
    if account_id:
        query = query.where(ClubPointsEntryRecord.account_id == account_id)
    if bale_user_id:
        query = query.where(ClubPointsEntryRecord.bale_user_id == bale_user_id)
    if entry_type in ENTRY_TYPES:
        query = query.where(ClubPointsEntryRecord.entry_type == entry_type)
    needle = unicodedata.normalize("NFKC", q or "").strip().lower()
    candidates = list(db.scalars(
        query.order_by(ClubPointsEntryRecord.ledger_id.desc(), ClubPointsEntryRecord.id).limit(5000)
    ).all())
    names = _display_names(db, {item.account_id for item in candidates})
    selected: list[ClubPointsEntryRecord] = []
    for item in candidates:
        if needle:
            haystack = " ".join(part for part in (
                item.ref_key.lower(), item.source.lower(), item.entry_type,
                unicodedata.normalize("NFKC", item.reason).lower(),
                unicodedata.normalize("NFKC", names.get(item.account_id, "")).lower(),
                item.bale_user_id, item.account_id.lower(), item.external_key.lower(),
            ) if part)
            if needle not in haystack:
                continue
        selected.append(item)
    page = selected[offset: offset + limit]
    counts = {
        name: int(count)
        for name, count in db.execute(
            select(ClubPointsEntryRecord.entry_type, func.count(ClubPointsEntryRecord.id))
            .group_by(ClubPointsEntryRecord.entry_type)
        ).all()
    }
    return {
        "source": SOURCE,
        "items": [row(item, display_name=names.get(item.account_id, "")) for item in page],
        "total": len(selected),
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < len(selected),
        "q": q,
        "entry_type": entry_type,
        "counts": {name: counts.get(name, 0) for name in ENTRY_TYPES},
        "write_routes": False,
    }


def member_summary(db: Session, account_id: str) -> dict[str, Any] | None:
    """Mirror-derived summary for one account (``None`` when nothing was mirrored)."""
    entries = list(db.scalars(
        select(ClubPointsEntryRecord)
        .where(ClubPointsEntryRecord.account_id == account_id)
        .order_by(ClubPointsEntryRecord.ledger_id)
    ).all())
    if not entries:
        return None
    summary = chain_summary(entries)
    summary.update({
        "account_id": account_id,
        "bale_user_id": entries[-1].bale_user_id,
        "display_name": _display_names(db, {account_id}).get(account_id, ""),
        "source": SOURCE,
    })
    return summary


def list_members(db: Session, *, q: str = "", limit: int = 20, offset: int = 0) -> dict[str, Any]:
    entries = list(db.scalars(
        select(ClubPointsEntryRecord).order_by(ClubPointsEntryRecord.account_id, ClubPointsEntryRecord.ledger_id)
    ).all())
    grouped: dict[str, list[ClubPointsEntryRecord]] = {}
    for item in entries:
        grouped.setdefault(item.account_id, []).append(item)
    names = _display_names(db, set(grouped))
    needle = unicodedata.normalize("NFKC", q or "").strip().lower()
    members: list[dict[str, Any]] = []
    for account_id, items in grouped.items():
        name = names.get(account_id, "")
        if needle and needle not in " ".join((
            unicodedata.normalize("NFKC", name).lower(), items[-1].bale_user_id, account_id.lower())):
            continue
        summary = chain_summary(items)
        summary.update({"account_id": account_id, "bale_user_id": items[-1].bale_user_id, "display_name": name})
        members.append(summary)
    members.sort(key=lambda m: (-(m["latest_ledger_id"] or 0), m["account_id"]))
    page = members[offset: offset + limit]
    return {
        "source": SOURCE,
        "items": page,
        "total": len(members),
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < len(members),
        "q": q,
        "partial": sum(1 for m in members if not m["history_complete"]),
        "write_routes": False,
    }

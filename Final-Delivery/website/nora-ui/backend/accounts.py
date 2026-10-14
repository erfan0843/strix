"""Shared account lookups for verified Bale and phone identities.

Callers must verify a Bale Mini App signature or a one-time phone challenge
before using these helpers. They participate in the caller's transaction and
never authenticate raw browser input or commit on their own.
"""

from __future__ import annotations

import re
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .models import AccountRecord, PlatformIdentityRecord
from .otp import normalize_iran_phone, phone_digest

_BALE_PROVIDER = "bale"
_PHONE_PROVIDER = "phone"
_BALE_ID = re.compile(r"[0-9]{1,40}\Z")


def _normalize_bale_user_id(value: int | str) -> str:
    if isinstance(value, bool):
        raise ValueError("invalid_bale_user_id")
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("invalid_bale_user_id")
        return str(value)
    if isinstance(value, str) and _BALE_ID.fullmatch(value):
        normalized = str(int(value))
        if normalized != "0":
            return normalized
    raise ValueError("invalid_bale_user_id")


def _get_or_create_verified_account(db: Session, provider: str, subject: str) -> AccountRecord:
    identity_query = (
        select(PlatformIdentityRecord)
        .options(joinedload(PlatformIdentityRecord.account))
        .where(
            PlatformIdentityRecord.provider == provider,
            PlatformIdentityRecord.provider_user_id == subject,
        )
    )
    identity = db.scalar(identity_query)
    if identity is not None:
        return identity.account

    account = AccountRecord(id=str(uuid4()))
    identity = PlatformIdentityRecord(
        id=str(uuid4()),
        account=account,
        provider=provider,
        provider_user_id=subject,
    )
    try:
        with db.begin_nested():
            db.add(account)
            db.add(identity)
            db.flush()
    except IntegrityError:
        # A concurrent first login may have inserted the same identity.
        winner = db.scalar(identity_query)
        if winner is None:
            raise
        return winner.account
    return account


def get_or_create_bale_account(db: Session, bale_user_id: int | str) -> AccountRecord:
    """Return the canonical account for a verified Bale user ID."""
    return _get_or_create_verified_account(db, _BALE_PROVIDER, _normalize_bale_user_id(bale_user_id))


def get_or_create_phone_account(
    db: Session, verified_phone: str, *, pepper: str
) -> AccountRecord:
    """Return the canonical account for a verified phone without storing it raw."""
    phone = normalize_iran_phone(verified_phone)
    if phone is None or phone != verified_phone or not pepper:
        raise ValueError("invalid_verified_phone")
    return _get_or_create_verified_account(db, _PHONE_PROVIDER, phone_digest(pepper, phone))

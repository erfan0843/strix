from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.accounts import get_or_create_bale_account
from backend.models import AccountRecord, Base, PlatformIdentityRecord


@pytest.fixture
def account_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_bale_identity_resolves_to_one_account_without_committing(account_db):
    first = get_or_create_bale_account(account_db, 73421)
    first_id = first.id
    assert account_db.in_transaction()
    account_db.commit()

    second = get_or_create_bale_account(account_db, "73421")
    assert second.id == first_id
    assert account_db.scalar(select(func.count()).select_from(AccountRecord)) == 1
    assert account_db.scalar(select(func.count()).select_from(PlatformIdentityRecord)) == 1

    identity = account_db.scalar(select(PlatformIdentityRecord))
    assert identity.provider == "bale"
    assert identity.provider_user_id == "73421"
    assert identity.account_id == first_id


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "", " 73421", "۷۳۴۲۱", "0"])
def test_invalid_bale_ids_are_rejected(account_db, value):
    with pytest.raises(ValueError, match="invalid_bale_user_id"):
        get_or_create_bale_account(account_db, value)
    assert account_db.scalar(select(func.count()).select_from(AccountRecord)) == 0


def test_account_identity_is_removed_by_account_cascade(account_db):
    account = get_or_create_bale_account(account_db, 73422)
    account_db.commit()

    account_db.delete(account)
    account_db.commit()

    assert account_db.scalar(select(func.count()).select_from(AccountRecord)) == 0
    assert account_db.scalar(select(func.count()).select_from(PlatformIdentityRecord)) == 0

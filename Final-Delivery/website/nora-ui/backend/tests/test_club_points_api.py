"""Read-only mirror of the bot's points ledger: bot sync (``/api/bot/club/points``) and panel read API.

In-memory SQLite only. The bot stays the only writer of points; the server
stores verified copies whose owner is resolved from the Bale id on the server.
Unmapped owners are never stored, keys are never re-owned, an existing key with
different data is rejected (the ledger is immutable), and no admin route can
create, award or spend points.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend import club_points as club_points_mod  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import AccountRecord, Base, ClubPointsEntryRecord  # noqa: E402
from backend.roles import ROLE_CLUB_SUPERVISOR  # noqa: E402
from backend.security import hash_password  # noqa: E402

from test_admin_users_attendance_api import set_profile  # noqa: E402
from test_workflows_api import (  # noqa: E402
    BOT_TOKEN,
    SERVICE_TOKEN,
    assign_manager,
    bale_login,
    owner_login,
    owner_write_headers,
    service_headers,
)

SOURCE_ID = "0c7f7f5e-9c1e-4a7e-8a1c-2b3d4e5f6a7b"


def make_app():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"),
        cookie_secure=False,
        bale_bot_token=BOT_TOKEN,
        bot_service_token=SERVICE_TOKEN,
        owner_bale_user_id="70001",
    )
    return create_app(settings, engine=engine), engine


def entry(ledger_id: int, delta: int, balance_after: int, **extra) -> dict:
    data = {
        "ledger_id": ledger_id, "delta": delta, "balance_after": balance_after,
        "entry_type": "award" if delta > 0 else "spend", "source": "achievement",
        "ref_key": f"ach:910001:k{ledger_id}", "reason": "", "actor_kind": "system",
        "reverses_external_key": None, "created_at": "2026-10-21 09:00:00",
    }
    data.update(extra)
    return data


def submit(client: TestClient, *, bale_user_id: str, ledger_id: int, data: dict, key: str | None = None):
    payload = {"bale_user_id": bale_user_id, "external_key": key or f"{SOURCE_ID}:{ledger_id}", "entry": data}
    return client.post("/api/bot/club/points", json=payload, headers=service_headers())


def assign_club_supervisor(client: TestClient, account_id: str) -> None:
    assign_manager(client, account_id)
    client.cookies.clear()
    owner_login(client)
    response = client.put(
        f"/api/owner/accounts/{account_id}/role",
        json={"role": ROLE_CLUB_SUPERVISOR},
        headers=owner_write_headers(client),
    )
    assert response.status_code == 200, response.text
    client.cookies.clear()
    username = "workflow." + account_id[-4:]
    login = client.post(
        "/api/auth/manager-login",
        json={"username": username, "password": "workflow-manager-password-2026"},
        headers={"Origin": "http://testserver"},
    )
    assert login.status_code == 200, login.text


def test_bot_sync_auth_identity_idempotency_and_immutability():
    app, engine = make_app()
    try:
        with TestClient(app) as client:
            # Service identity is mandatory; a wrong token is not enough.
            assert client.post("/api/bot/club/points", json={}).status_code == 401
            assert client.post("/api/bot/club/points", json={}, headers={"Authorization": "Bearer wrong"}).status_code == 401
            # Owner without a server identity: not stored, no account created → bot keeps it as "unmapped".
            missing = submit(client, bale_user_id="919999", ledger_id=9, data=entry(9, 5, 5))
            assert missing.status_code == 404 and missing.json()["detail"] == "owner_identity_not_found"
            with Session(engine) as db:
                assert db.scalar(select(func.count(AccountRecord.id))) == 0
                assert db.scalar(select(func.count(ClubPointsEntryRecord.id))) == 0

            holder = bale_login(client, 910001)
            client.cookies.clear()
            other = bale_login(client, 910002)
            client.cookies.clear()
            assert other != holder

            opening = submit(client, bale_user_id="910001", ledger_id=1,
                             data=entry(1, 120, 120, entry_type="opening_balance", source="legacy_counter",
                                        ref_key="opening:910001", reason="موجودی شمارندهٔ قدیمی"))
            assert opening.status_code == 200, opening.text
            body = opening.json()
            assert body["created"] is True and body["account_id"] == holder and body["balance_after"] == 120
            first_id = body["id"]

            # Retrying the same request (network retry) never creates a second row.
            replay = submit(client, bale_user_id="910001", ledger_id=1,
                            data=entry(1, 120, 120, entry_type="opening_balance", source="legacy_counter",
                                       ref_key="opening:910001", reason="موجودی شمارندهٔ قدیمی"))
            assert replay.status_code == 200 and replay.json()["created"] is False and replay.json()["id"] == first_id
            with Session(engine) as db:
                assert db.scalar(select(func.count(ClubPointsEntryRecord.id))) == 1

            # The mirror is immutable: same key with different data is rejected, not overwritten.
            tampered = submit(client, bale_user_id="910001", ledger_id=1,
                              data=entry(1, 999, 999, entry_type="opening_balance", source="legacy_counter",
                                         ref_key="opening:910001", reason="x"))
            assert tampered.status_code == 409 and tampered.json()["detail"] == "points_entry_conflict"
            with Session(engine) as db:
                assert db.get(ClubPointsEntryRecord, first_id).delta == 120

            # The same external key can never be re-owned by another Bale id.
            hijack = submit(client, bale_user_id="910002", ledger_id=1,
                            data=entry(1, 120, 120, entry_type="opening_balance", source="legacy_counter",
                                       ref_key="opening:910001"))
            assert hijack.status_code == 409 and hijack.json()["detail"] == "points_entry_owner_mismatch"

            # Validation: external key must carry the bot source id and the ledger id.
            assert submit(client, bale_user_id="910001", ledger_id=2, data=entry(2, 5, 125), key="k:2").status_code == 422
            assert submit(client, bale_user_id="910001", ledger_id=2, data=entry(3, 5, 125)).status_code == 422
            assert submit(client, bale_user_id="910001", ledger_id=2, data=entry(2, 0, 120)).status_code == 422
            assert submit(client, bale_user_id="910001", ledger_id=2, data=entry(2, 5, 125, entry_type="bonus")).status_code == 422
            assert submit(client, bale_user_id="910001", ledger_id=2, data=entry(2, 5, 125, source="Bad Source")).status_code == 422
            assert submit(client, bale_user_id="910001", ledger_id=2, data=entry(2, 5, 125, ref_key="has space")).status_code == 422
            assert submit(client, bale_user_id="910001", ledger_id=2, data={**entry(2, 5, 125), "token": "x"}).status_code == 422
            assert submit(client, bale_user_id="910001", ledger_id=2, data=entry(2, -5, 115, entry_type="reversal")).status_code == 422
            assert submit(client, bale_user_id="not-an-id", ledger_id=2, data=entry(2, 5, 125)).status_code == 422
            assert client.post("/api/bot/club/points", json={"bale_user_id": "910001"}, headers=service_headers()).status_code == 400
            with Session(engine) as db:
                assert db.scalar(select(func.count(ClubPointsEntryRecord.id))) == 1

            # A reversal carries the key of the row it reverses.
            spend = submit(client, bale_user_id="910001", ledger_id=2,
                           data=entry(2, -20, 100, entry_type="spend", source="reward_redeem", ref_key="redeem:7"))
            assert spend.status_code == 200 and spend.json()["created"] is True
            reversal = submit(client, bale_user_id="910001", ledger_id=3,
                              data=entry(3, 20, 120, entry_type="reversal", source="reversal", ref_key="rev:2",
                                         reverses_external_key=f"{SOURCE_ID}:2", actor_kind="admin", reason="رد درخواست"))
            assert reversal.status_code == 200 and reversal.json()["balance_after"] == 120
    finally:
        engine.dispose()


def test_admin_read_api_permissions_states_and_no_write_route():
    app, engine = make_app()
    try:
        with TestClient(app) as client:
            holder = bale_login(client, 910001)
            client.cookies.clear()
            partial = bale_login(client, 910005)
            client.cookies.clear()
            manager = bale_login(client, 910004)
            client.cookies.clear()
            supervisor = bale_login(client, 910006)
            client.cookies.clear()
            set_profile(engine, holder, fullName="زهرا موسوی", nationalId="0012345678", phone="09120000000")

            # Empty state before any sync: honest zeros, no invented balance.
            owner_login(client)
            empty = client.get("/api/admin/club/points/members")
            assert empty.status_code == 200 and empty.json()["items"] == [] and empty.json()["total"] == 0
            assert empty.json()["write_routes"] is False
            assert client.get("/api/admin/club/points").json()["total"] == 0
            client.cookies.clear()

            # Complete history for the holder: opening + award + spend.
            for ledger_id, data in (
                (1, entry(1, 120, 120, entry_type="opening_balance", source="legacy_counter", ref_key="opening:910001")),
                (2, entry(2, 10, 130, ref_key="ach:910001:first_step")),
                (3, entry(3, -30, 100, entry_type="spend", source="reward_redeem", ref_key="redeem:4", actor_kind="user")),
            ):
                assert submit(client, bale_user_id="910001", ledger_id=ledger_id, data=data).status_code == 200
            # Partial history for another member: the first mirrored row does not start from zero
            # (earlier rows were unmapped at sync time) → reported as incomplete, never filled in.
            assert submit(client, bale_user_id="910005", ledger_id=7,
                          data=entry(7, 5, 45, ref_key="ach:910005:x")).status_code == 200

            # Anonymous, plain member and plain manager (no cl_member) are blocked at the API.
            assert client.get("/api/admin/club/points").status_code == 401
            bale_login(client, 910003)
            assert client.get("/api/admin/club/points").status_code == 403
            assert client.get("/api/admin/club/points/members").status_code == 403
            assert client.get(f"/api/admin/club/points/members/{holder}").status_code == 403
            client.cookies.clear()
            assign_manager(client, manager)
            assert client.get("/api/admin/club/points").status_code == 403
            assert client.get("/api/admin/club/points/members").status_code == 403
            client.cookies.clear()

            # Club supervisor (has cl_member) reads the mirror.
            assign_club_supervisor(client, supervisor)
            listing = client.get("/api/admin/club/points")
            assert listing.status_code == 200, listing.text
            body = listing.json()
            assert body["source"] == "shared_server_database" and body["total"] == 4 and body["write_routes"] is False
            assert body["counts"] == {"opening_balance": 1, "award": 2, "spend": 1, "refund": 0, "reversal": 0, "manual_adjust": 0}
            assert [item["ledger_id"] for item in body["items"]] == [7, 3, 2, 1]
            newest = body["items"][1]
            assert newest["holder"] == {
                "account_id": holder, "bale_user_id": "910001", "display_name": "زهرا موسوی", "name_source": "profile",
            }
            for item in body["items"]:
                flattened = repr(item).lower()
                assert "0012345678" not in flattened and "0912" not in flattened
                assert "hash" not in flattened and "token" not in flattened and "phone" not in flattened
                assert "actor_id" not in item
            assert client.get("/api/admin/club/points?entry_type=spend").json()["total"] == 1
            assert client.get("/api/admin/club/points?q=زهرا").json()["total"] == 3
            assert client.get("/api/admin/club/points?q=redeem:4").json()["total"] == 1
            assert client.get(f"/api/admin/club/points?account_id={holder}").json()["total"] == 3
            assert client.get("/api/admin/club/points?bale_user_id=910005").json()["total"] == 1
            assert client.get("/api/admin/club/points?entry_type=bonus").status_code == 422
            page = client.get("/api/admin/club/points?limit=3&offset=3").json()
            assert len(page["items"]) == 1 and page["has_more"] is False

            members = client.get("/api/admin/club/points/members").json()
            assert members["total"] == 2 and members["partial"] == 1
            by_account = {item["account_id"]: item for item in members["items"]}
            full = by_account[holder]
            assert full["latest_balance"] == 100 and full["entries"] == 3 and full["history_complete"] is True
            assert full["has_opening"] is True and full["latest_ledger_id"] == 3 and full["display_name"] == "زهرا موسوی"
            incomplete = by_account[partial]
            assert incomplete["latest_balance"] == 45 and incomplete["history_complete"] is False
            assert incomplete["chain_breaks"] == 1 and incomplete["has_opening"] is False
            assert client.get("/api/admin/club/points/members?q=زهرا").json()["total"] == 1

            detail = client.get(f"/api/admin/club/points/members/{holder}")
            assert detail.status_code == 200, detail.text
            data = detail.json()
            assert data["latest_balance"] == 100 and [row["ledger_id"] for row in data["history"]] == [3, 2, 1]
            assert "0012345678" not in repr(data) and "0912" not in repr(data)
            # Members without any mirrored row are not invented.
            assert client.get(f"/api/admin/club/points/members/{manager}").status_code == 404
            assert client.get("/api/admin/club/points/members/not-a-uuid").status_code == 404

            # There is no panel-side write route for points at all.
            for method, path in (
                ("post", "/api/admin/club/points"),
                ("post", f"/api/admin/club/points/members/{holder}"),
                ("post", f"/api/admin/club/points/members/{holder}/adjust"),
                ("put", f"/api/admin/club/points/members/{holder}"),
                ("delete", f"/api/admin/club/points/{body['items'][0]['id']}"),
            ):
                response = client.request(method.upper(), path, json={"delta": 10, "reason": "x"},
                                          headers={"Origin": "http://testserver"})
                assert response.status_code in {404, 405}, (method, path, response.status_code)
            with Session(engine) as db:
                assert db.scalar(select(func.count(ClubPointsEntryRecord.id))) == 4

            # Owner sees the same mirror.
            client.cookies.clear()
            owner_login(client)
            assert client.get("/api/admin/club/points/members").json()["total"] == 2
    finally:
        engine.dispose()


def test_chain_summary_is_derived_not_guessed():
    class Row:
        def __init__(self, ledger_id, delta, balance_after, entry_type="award", synced_at=None, bot_created_at=""):
            self.ledger_id = ledger_id
            self.delta = delta
            self.balance_after = balance_after
            self.entry_type = entry_type
            self.synced_at = synced_at
            self.bot_created_at = bot_created_at

    assert club_points_mod.chain_summary([]) == {
        "entries": 0, "latest_balance": None, "latest_ledger_id": None,
        "history_complete": False, "chain_breaks": 0, "has_opening": False,
    }
    complete = club_points_mod.chain_summary([Row(1, 50, 50, "opening_balance"), Row(2, -20, 30), Row(3, 5, 35)])
    assert complete["history_complete"] is True and complete["latest_balance"] == 35 and complete["has_opening"]
    broken = club_points_mod.chain_summary([Row(4, 5, 35), Row(6, 5, 45)])
    assert broken["history_complete"] is False and broken["chain_breaks"] == 2 and broken["latest_balance"] == 45

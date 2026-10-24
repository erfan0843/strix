"""Phase 9.5 §3: read-only integrity audit of the purchase chain.

A real card purchase is driven through the HTTP API (form → receipt → inbox approval) so the
chain form → response → payment → ledger → access is genuine.  The audit must be clean on it,
then every inconsistency the brief lists is injected straight into the database and the report
must name it — while the database stays byte-for-byte unchanged (no auto-fix).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend import integrity  # noqa: E402
from backend.models import (  # noqa: E402
    EventRecordingRecord,
    FormPaymentRecord,
    FormRecord,
    RecordingAccessRecord,
    RecordingOrderRecord,
)
from test_event_registration_gate import gate_app  # noqa: E402
from test_recordings_api import (  # noqa: E402
    build_sellable_product,
    held_event,
    inbox_decide,
    purchase_form,
    set_status,
    submit_purchase,
    upload_purchase_receipt,
)
from test_workflows_api import account_write_headers, assign_manager, bale_login, owner_login  # noqa: E402

TABLES = ("forms", "form_responses", "form_payments", "recording_orders", "recording_access", "event_recordings")


def _fingerprint(engine) -> dict[str, list[tuple]]:
    with engine.connect() as conn:
        return {table: sorted(tuple(map(str, row)) for row in conn.execute(text(f"SELECT * FROM {table}")).all()) for table in TABLES}


def _codes(report: dict) -> set[str]:
    return {f["code"] for f in report["findings"]}


def _buy(app, owner: TestClient) -> dict:
    """Runs inside the caller's ``with TestClient(app)`` block (the in-memory DB lives with the app)."""
    if True:
        owner_login(owner)
        event_id, _version = held_event(owner, 0)
        product = build_sellable_product(owner, event_id)
        recording_id = product["recording"]["id"]
        form_id = purchase_form(owner, recording_id, price=900_000)
        assert set_status(owner, event_id, "ready").status_code == 200
        assert set_status(owner, event_id, "published").status_code == 200
        member = TestClient(app)
        member_id = bale_login(member, 95001)
        assert submit_purchase(member, form_id, name="خریدار ممیزی").status_code == 200
        receipt = upload_purchase_receipt(member, form_id, note="واریز شد")
        assert receipt.status_code == 200
        manager_id = bale_login(TestClient(app), 95003)
        manager = TestClient(app)
        assign_manager(manager, manager_id)
        approved = inbox_decide(manager, receipt.json()["review_task_id"], "approved", "تطبیق مبلغ", account_write_headers(manager))
        assert approved.status_code == 200, approved.text
        staff = owner
        return {"event_id": event_id, "recording_id": recording_id, "form_id": form_id, "member_id": member_id, "staff": staff}


def test_audit_is_clean_on_a_real_purchase_and_names_every_injected_inconsistency():
    app, engine = gate_app()
    with TestClient(app) as owner:
        ctx = _buy(app, owner)
        now = datetime.now(timezone.utc)
        with Session(engine) as db:
            report = integrity.run(db, now)
        assert report["read_only"] is True and report["findings"] == [], report
        assert report["scanned"]["purchase_forms"] == 1 and report["scanned"]["payments"] == 1
        assert report["scanned"]["orders"] == 1 and report["scanned"]["access_rows"] == 1
        assert report["severity"] == {"error": 0, "warning": 0, "info": 0}

        # The panel endpoint returns the same report; rp_view only.
        staff = ctx["staff"]
        via_api = staff.get("/api/admin/integrity/recordings")
        assert via_api.status_code == 200 and via_api.json()["findings"] == [] and via_api.headers["cache-control"] == "no-store"
        assert TestClient(app).get("/api/admin/integrity/recordings").status_code == 401
        plain = TestClient(app)
        bale_login(plain, 95009)
        assert plain.get("/api/admin/integrity/recordings").status_code == 403

        with Session(engine) as db:
            access = db.scalar(select(RecordingAccessRecord))
            order = db.scalar(select(RecordingOrderRecord))
            payment = db.scalar(select(FormPaymentRecord))
            form = db.scalar(select(FormRecord).where(FormRecord.purpose == "recording_access"))
            ids = {"access": access.id, "order": order.id, "payment": payment.id, "form": form.id, "response": order.form_response_id}

        def scenario(mutate, expected: set[str], *, severity: str) -> None:
            before = _fingerprint(engine)
            with Session(engine) as db:
                mutate(db)
                db.commit()
            mutated = _fingerprint(engine)
            with Session(engine) as db:
                report = integrity.run(db, now)
                db.rollback()
            assert expected <= _codes(report), (expected, report["findings"])
            assert report["severity"][severity] >= 1
            assert all(set(f["refs"]) <= {
                "payment_id", "form_id", "response_id", "recording_id", "account_id", "access_state", "access_id", "order_id",
                "expires_at", "access_account_id", "order_account_id", "order_status", "response_account_id", "form_payment_id",
                "payment_status", "payment_ids", "order_ids", "form_ids", "form_event_id", "recording_event_id", "event_id",
            } for f in report["findings"]), "findings must carry ids only"
            assert _fingerprint(engine) == mutated, "audit must not write"
            # undo
            with Session(engine) as db:
                for table in TABLES:
                    db.execute(text(f"DELETE FROM {table}"))
                db.commit()
            _restore(engine, before)
            with Session(engine) as db:
                assert integrity.run(db, now)["findings"] == []

        # 1. paid response whose access was removed → error
        scenario(lambda db: db.delete(db.get(RecordingAccessRecord, ids["access"])),
                 {"paid_payment_without_access"}, severity="error")
        # 2. access revoked while the payment is still settled (and never refunded) → error
        def revoke(db):
            row = db.get(RecordingAccessRecord, ids["access"])
            row.status = "revoked"
            row.revoked_at = now
        scenario(revoke, {"paid_payment_without_access"}, severity="error")
        # 3. purchase access without a ledger reference → error
        def drop_order_ref(db):
            db.get(RecordingAccessRecord, ids["access"]).order_id = None
        scenario(drop_order_ref, {"purchase_access_without_order"}, severity="error")
        # 4. refund recorded on the ledger but access still active → error
        def refund(db):
            db.get(RecordingOrderRecord, ids["order"]).status = "refunded"
        scenario(refund, {"refund_without_revoke"}, severity="error")
        # 5. ledger says paid, form payment flipped back to pending → error
        def unsettle(db):
            db.get(FormPaymentRecord, ids["payment"]).status = "pending"
        scenario(unsettle, {"order_payment_not_settled"}, severity="error")
        # 6. access on the wrong account → error
        def wrong_account(db):
            row = db.get(RecordingAccessRecord, ids["access"])
            row.account_id = _other_account(db, row.account_id)
        scenario(wrong_account, {"access_account_mismatch", "paid_payment_without_access"}, severity="error")
        # 7. duplicate payment: the schema already forbids a second payment per response and a second
        #    ledger row per payment (UNIQUE constraints, proven below); the remaining duplication risk is
        #    a second paid ledger row for the same (product, account) without a form payment → warning
        with Session(engine) as db:
            src = db.get(RecordingOrderRecord, ids["order"])
            with pytest.raises(IntegrityError):
                with db.begin_nested():
                    db.add(RecordingOrderRecord(
                        id="dupe-order-00000000000000000000001", recording_id=src.recording_id, account_id=src.account_id,
                        method=src.method, status="paid_manual", amount=src.amount, currency=src.currency,
                        idempotency_key="dupe-order-key-0001", form_payment_id=src.form_payment_id,
                    ))
                    db.flush()
            pay = db.get(FormPaymentRecord, ids["payment"])
            with pytest.raises(IntegrityError):
                with db.begin_nested():
                    db.add(FormPaymentRecord(
                        id="dupe-payment-0001", form_id=pay.form_id, draft_id=pay.draft_id, response_id=pay.response_id,
                        form_version=pay.form_version, method=pay.method, status="paid_manual", amount=pay.amount,
                        currency=pay.currency, party_count=1, selection={}, idempotency_key="dupe-payment-key-0001",
                    ))
                    db.flush()
            db.rollback()

        def duplicate_ledger(db):
            src = db.get(RecordingOrderRecord, ids["order"])
            db.add(RecordingOrderRecord(
                id="dupe-order-00000000000000000000001", recording_id=src.recording_id, account_id=src.account_id,
                method=src.method, status="paid_manual", amount=src.amount, currency=src.currency,
                idempotency_key="dupe-order-key-0001",
            ))
        scenario(duplicate_ledger, {"duplicate_paid_orders", "order_without_form_payment"}, severity="warning")
        # 8. the purchase form of a product on sale is unpublished → warning
        def pause_form(db):
            db.get(FormRecord, ids["form"]).status = "paused"
        scenario(pause_form, {"purchase_form_unpublished"}, severity="warning")
        # 9. purchase form pointing at a vanished product → warning (+ product on sale without form)
        def detach_form(db):
            db.get(FormRecord, ids["form"]).recording_id = None
        scenario(detach_form, {"purchase_form_without_product", "published_without_purchase_form"}, severity="warning")
        # 10. active row with a past expiry → info only (state is computed per request)
        def expire(db):
            db.get(RecordingAccessRecord, ids["access"]).expires_at = now - timedelta(days=1)
        scenario(expire, {"stale_active_status", "paid_payment_without_access"}, severity="info")


def _other_account(db: Session, account_id: str) -> str:
    row = db.execute(text("SELECT id FROM accounts WHERE id != :a ORDER BY id LIMIT 1"), {"a": account_id}).first()
    assert row is not None
    return str(row[0])


def _restore(engine, snapshot: dict[str, list[tuple]]) -> None:
    """Scenarios mutate a single column; rebuilding from the pre-scenario copy is simplest and exact."""
    with engine.connect() as conn:
        for table, rows in snapshot.items():
            columns = [c[1] for c in conn.execute(text(f"PRAGMA table_info({table})")).all()]
            for row in rows:
                values = {col: (None if val == "None" else val) for col, val in zip(columns, row)}
                placeholders = ", ".join(f":{c}" for c in columns)
                conn.execute(text(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"), values)
        conn.commit()


def test_cli_tool_reports_and_exits_nonzero_on_errors(monkeypatch, tmp_path):
    app, engine = gate_app()
    with TestClient(app) as owner:
        _buy(app, owner)
        with Session(engine) as db:
            db.delete(db.scalar(select(RecordingAccessRecord)))
            db.commit()
        # Share the in-memory engine with the tool through a file-backed copy (sqlite backup API).
        import sqlite3
        target = tmp_path / "audit.db"
        raw = engine.raw_connection()
        try:
            dest = sqlite3.connect(target)
            raw.driver_connection.backup(dest)  # type: ignore[attr-defined]
            dest.close()
        finally:
            raw.close()
        monkeypatch.setenv("NORA_DATABASE_URL", f"sqlite:///{target}")
        import importlib.util
        spec = importlib.util.spec_from_file_location("recording_access_audit", BACKEND_PARENT / "tools" / "recording-access-audit.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        assert module.main(["--json"]) == 2
        assert module.main(["--fail-on", "error"]) == 2
        with Session(engine) as db:
            assert db.scalar(select(RecordingAccessRecord)) is None  # still nothing re-granted
            assert db.scalar(select(EventRecordingRecord)).status == "published"

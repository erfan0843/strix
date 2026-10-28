"""Phase 9.5 — read-only integrity audit of the purchase chain.

Walks ``forms`` (purpose ``recording_access``) → ``form_responses`` / ``form_payments`` →
``recording_orders`` (internal ledger) → ``recording_access`` (entitlement) and reports every
place where the chain is broken.  It **never** writes: no auto-fix, no status flip, no
re-grant.  Findings carry record ids only (no names, mobiles or Bale ids) so the report can be
attached to an operations ticket.

Finding codes (``severity`` ``error`` = access or money is wrong today, ``warning`` = sale
cannot proceed / history is incomplete, ``info`` = cosmetic/stale but behaviour is correct):

* ``paid_payment_without_access``      settled form payment, no active entitlement
* ``paid_payment_without_account``     settled payment whose draft has no account to grant to
* ``paid_payment_without_ledger``      settled payment with no ``recording_orders`` row
* ``purchase_access_without_order``    ``source='purchase'`` access that points at no ledger row
* ``purchase_access_order_missing``    ``order_id`` dangling
* ``access_with_unpaid_order``         active purchase access while its order is not paid
* ``refund_without_revoke``            order refunded but access still active
* ``order_without_form_payment``       ledger row older than the form-centric path (no payment ref)
* ``order_payment_missing``            ``form_payment_id`` dangling
* ``order_payment_not_settled``        ledger says paid, form payment says otherwise
* ``payment_unrelated_form``           the referenced payment belongs to another product / a non-purchase form
* ``access_account_mismatch``          access holder ≠ order payer
* ``order_account_mismatch``           order payer ≠ account that owns the response draft
* ``duplicate_settled_payments``       more than one settled payment for one response
* ``duplicate_orders_for_payment``     one form payment referenced by several ledger rows
* ``duplicate_paid_orders``            several paid orders for one (product, account)
* ``purchase_form_without_product``    purchase form with no / dangling ``recording_id``
* ``purchase_form_event_mismatch``     form.event_id ≠ product.event_id
* ``published_without_purchase_form``  paid product on sale with no purchase form at all (free products are claimed without one)
* ``purchase_form_unpublished``        product on sale whose only purchase form is not published
* ``stale_active_status``              ``status='active'`` with a past ``expires_at`` (state is computed per request, so no leak)
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    EventRecordingRecord,
    FormPaymentRecord,
    FormRecord,
    FormResponseDraftRecord,
    FormResponseRecord,
    RecordingAccessRecord,
    RecordingOrderRecord,
)
from .recordings import PAID_ORDER_STATUSES, PURCHASE_FORM_PURPOSE, access_state

SETTLED_PAYMENT_STATUSES: tuple[str, ...] = ("paid", "paid_manual")
SEVERITY: dict[str, str] = {
    "paid_payment_without_access": "error",
    "paid_payment_without_account": "error",
    "paid_payment_without_ledger": "warning",
    "purchase_access_without_order": "error",
    "purchase_access_order_missing": "error",
    "access_with_unpaid_order": "error",
    "refund_without_revoke": "error",
    "order_without_form_payment": "warning",
    "order_payment_missing": "error",
    "order_payment_not_settled": "error",
    "payment_unrelated_form": "error",
    "access_account_mismatch": "error",
    "order_account_mismatch": "error",
    "duplicate_settled_payments": "error",
    "duplicate_orders_for_payment": "error",
    "duplicate_paid_orders": "warning",
    "purchase_form_without_product": "warning",
    "purchase_form_event_mismatch": "warning",
    "published_without_purchase_form": "warning",
    "purchase_form_unpublished": "warning",
    "stale_active_status": "info",
}


@dataclass
class Finding:
    code: str
    severity: str
    refs: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def run(db: Session, now: datetime | None = None) -> dict[str, Any]:
    """Return ``{generated_at, scanned, counts, findings}``; performs only SELECTs."""
    now = now or datetime.now(timezone.utc)
    findings: list[Finding] = []

    def add(code: str, **refs: Any) -> None:
        findings.append(Finding(code=code, severity=SEVERITY[code], refs=refs))

    forms = {f.id: f for f in db.scalars(select(FormRecord).where(FormRecord.purpose == PURCHASE_FORM_PURPOSE)).all()}
    recordings = {r.id: r for r in db.scalars(select(EventRecordingRecord)).all()}
    orders = list(db.scalars(select(RecordingOrderRecord)).all())
    orders_by_id = {o.id: o for o in orders}
    accesses = list(db.scalars(select(RecordingAccessRecord)).all())
    access_by_key = {(a.recording_id, a.account_id): a for a in accesses}
    payments = list(db.scalars(select(FormPaymentRecord).where(FormPaymentRecord.form_id.in_(list(forms)))).all()) if forms else []
    payments_by_id = {p.id: p for p in payments}
    response_ids = {p.response_id for p in payments if p.response_id} | {o.form_response_id for o in orders if o.form_response_id}
    responses = {
        r.id: r for r in db.scalars(select(FormResponseRecord).where(FormResponseRecord.id.in_(list(response_ids)))).all()
    } if response_ids else {}
    draft_ids = {r.draft_id for r in responses.values()}
    drafts = {
        d.id: d for d in db.scalars(select(FormResponseDraftRecord).where(FormResponseDraftRecord.id.in_(list(draft_ids)))).all()
    } if draft_ids else {}
    orders_by_response: dict[str, list[RecordingOrderRecord]] = defaultdict(list)
    orders_by_payment: dict[str, list[RecordingOrderRecord]] = defaultdict(list)
    for order in orders:
        if order.form_response_id:
            orders_by_response[order.form_response_id].append(order)
        if order.form_payment_id:
            orders_by_payment[order.form_payment_id].append(order)

    def response_account(response_id: str | None) -> str | None:
        response = responses.get(response_id or "")
        draft = drafts.get(response.draft_id) if response else None
        return draft.account_id if draft else None

    # ── 1. settled payments must end in an active entitlement ──
    settled_by_response: dict[str, list[FormPaymentRecord]] = defaultdict(list)
    for payment in payments:
        if payment.status not in SETTLED_PAYMENT_STATUSES:
            continue
        form = forms[payment.form_id]
        if payment.response_id:
            settled_by_response[payment.response_id].append(payment)
        account_id = response_account(payment.response_id)
        if not account_id:
            add("paid_payment_without_account", payment_id=payment.id, form_id=form.id, response_id=payment.response_id)
            continue
        ledger = orders_by_payment.get(payment.id) or orders_by_response.get(payment.response_id or "", [])
        if not ledger:
            add("paid_payment_without_ledger", payment_id=payment.id, form_id=form.id, response_id=payment.response_id)
        if ledger and all(o.status == "refunded" for o in ledger):
            continue  # refunded on purpose; the access side is checked below
        if not form.recording_id:
            continue  # reported once per form in section 4
        access = access_by_key.get((form.recording_id, account_id))
        if access is None or access_state(access, now) != "active":
            add(
                "paid_payment_without_access", payment_id=payment.id, form_id=form.id, response_id=payment.response_id,
                recording_id=form.recording_id, account_id=account_id,
                access_state=access_state(access, now) if access else "none",
            )
    for response_id, rows in settled_by_response.items():
        if len(rows) > 1:
            add("duplicate_settled_payments", response_id=response_id, payment_ids=sorted(p.id for p in rows))

    # ── 2. purchase entitlements must trace back to a settled form payment ──
    for access in accesses:
        state = access_state(access, now)
        if access.status == "active" and state == "expired":
            expires = _utc(access.expires_at)
            add("stale_active_status", access_id=access.id, recording_id=access.recording_id, expires_at=expires.isoformat() if expires else None)
        if access.source != "purchase":
            continue
        if not access.order_id:
            add("purchase_access_without_order", access_id=access.id, recording_id=access.recording_id, account_id=access.account_id, access_state=state)
            continue
        linked = orders_by_id.get(access.order_id)
        if linked is None:
            add("purchase_access_order_missing", access_id=access.id, order_id=access.order_id, access_state=state)
            continue
        if linked.account_id != access.account_id:
            add("access_account_mismatch", access_id=access.id, order_id=linked.id, access_account_id=access.account_id, order_account_id=linked.account_id)
        if linked.status == "refunded":
            if state == "active":
                add("refund_without_revoke", access_id=access.id, order_id=linked.id)
        elif linked.status not in PAID_ORDER_STATUSES and state == "active":
            add("access_with_unpaid_order", access_id=access.id, order_id=linked.id, order_status=linked.status)

    # ── 3. ledger rows must mirror a settled payment of a related purchase form ──
    paid_orders_by_pair: dict[tuple[str, str], list[str]] = defaultdict(list)
    for order in orders:
        if order.status in PAID_ORDER_STATUSES:
            paid_orders_by_pair[(order.recording_id, order.account_id)].append(order.id)
        if order.form_response_id:
            owner = response_account(order.form_response_id)
            if owner and owner != order.account_id:
                add("order_account_mismatch", order_id=order.id, order_account_id=order.account_id, response_account_id=owner, response_id=order.form_response_id)
        if not order.form_payment_id:
            if order.status in PAID_ORDER_STATUSES:
                add("order_without_form_payment", order_id=order.id, recording_id=order.recording_id, order_status=order.status)
            continue
        payment_row = payments_by_id.get(order.form_payment_id) or db.get(FormPaymentRecord, order.form_payment_id)
        if payment_row is None:
            add("order_payment_missing", order_id=order.id, form_payment_id=order.form_payment_id)
            continue
        linked_form = forms.get(payment_row.form_id)
        if linked_form is None or linked_form.recording_id != order.recording_id:
            add("payment_unrelated_form", order_id=order.id, form_payment_id=payment_row.id, form_id=payment_row.form_id, recording_id=order.recording_id)
        if order.status in PAID_ORDER_STATUSES and payment_row.status not in SETTLED_PAYMENT_STATUSES:
            add("order_payment_not_settled", order_id=order.id, form_payment_id=payment_row.id, order_status=order.status, payment_status=payment_row.status)
    for payment_id, order_rows in orders_by_payment.items():
        if len(order_rows) > 1:
            add("duplicate_orders_for_payment", form_payment_id=payment_id, order_ids=sorted(o.id for o in order_rows))
    for (recording_id, account_id), ids in paid_orders_by_pair.items():
        if len(ids) > 1:
            add("duplicate_paid_orders", recording_id=recording_id, account_id=account_id, order_ids=sorted(ids))

    # ── 4. purchase forms must point at a real product; products on sale need a published form ──
    forms_by_recording: dict[str, list[FormRecord]] = defaultdict(list)
    for form in forms.values():
        product = recordings.get(form.recording_id or "")
        if product is None:
            add("purchase_form_without_product", form_id=form.id, recording_id=form.recording_id)
            continue
        forms_by_recording[product.id].append(form)
        if form.event_id and form.event_id != product.event_id:
            add("purchase_form_event_mismatch", form_id=form.id, form_event_id=form.event_id, recording_event_id=product.event_id)
    for recording in recordings.values():
        if recording.status != "published":
            continue
        product_forms = forms_by_recording.get(recording.id, [])
        if not product_forms:
            if int(recording.price or 0) > 0:  # a free product is claimed without a form (no fake transaction)
                add("published_without_purchase_form", recording_id=recording.id, event_id=recording.event_id)
        elif not any(f.status == "published" for f in product_forms):
            add("purchase_form_unpublished", recording_id=recording.id, form_ids=sorted(f.id for f in product_forms))

    counts: dict[str, int] = defaultdict(int)
    by_severity: dict[str, int] = {"error": 0, "warning": 0, "info": 0}
    for finding in findings:
        counts[finding.code] += 1
        by_severity[finding.severity] += 1
    return {
        "generated_at": now.isoformat(),
        "read_only": True,
        "scanned": {
            "purchase_forms": len(forms), "payments": len(payments), "orders": len(orders),
            "access_rows": len(accesses), "products": len(recordings),
        },
        "severity": by_severity,
        "counts": dict(sorted(counts.items())),
        "findings": [f.as_dict() for f in findings],
    }

"""Shared tickets render only API-returned data and never query legacy responses."""
# ruff: noqa: INP001

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

import shared_api  # noqa: E402
import shared_form_ticket as flow  # noqa: E402


RESPONSE_ID = "123e4567-e89b-12d3-a456-426614174001"
TICKET = {
    "source": "shared_server_database",
    "response_id": RESPONSE_ID,
    "form_id": "123e4567-e89b-12d3-a456-426614174000",
    "serial": "NORA-123E4567E89B12D3A456",
    "form_title": "ثبت‌نام کارگاه",
    "event_title": "کارگاه فرهنگ ایرانی",
    "event_date": "۱۴۰۵/۰۸/۲۲",
    "event_time": "۱۶:۳۰ تا ۱۹:۰۰",
    "participant_name": "لیلا رضایی",
    "ticket_type": {"id": "priority", "name": "ورودی ویژه"},
    "issued_at": "2026-10-01T10:00:00+00:00",
    "receipt_required": False,
    "receipt_submitted": False,
    "checked_in": False,
    "checked_in_at": None,
}


def test_ticket_image_uses_shared_payload_and_never_calls_legacy_response_builder(monkeypatch):
    observed = {}

    def build(data, out_path=None):
        observed["data"] = data
        observed["out_path"] = out_path
        Path(out_path).write_bytes(b"shared ticket image")
        return out_path

    def legacy_builder(*_args, **_kwargs):
        raise AssertionError("legacy SQLite response lookup must not be used")

    fake_renderer = SimpleNamespace(
        build_shared_form_ticket=build,
        build_for_response=legacy_builder,
        build=legacy_builder,
    )
    monkeypatch.setitem(sys.modules, "ticket", fake_renderer)
    monkeypatch.setattr(
        flow.config, "deep_link", lambda payload: "https://ble.ir/nora?start=" + payload
    )

    sent = []

    def send_photo(cid, image_path, caption, **_kwargs):
        assert Path(image_path).read_bytes() == b"shared ticket image"
        sent.append((cid, caption))
        return {"ok": True}

    monkeypatch.setattr(flow, "send_photo", send_photo)
    monkeypatch.setattr(
        flow,
        "send",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("text fallback")),
    )

    assert flow._deliver(73421, TICKET)["ok"] is True
    assert observed["data"]["name"] == "لیلا رضایی"
    assert observed["data"]["event_title"] == "کارگاه فرهنگ ایرانی"
    assert observed["data"]["event_date"] == "۱۴۰۵/۰۸/۲۲"
    assert observed["data"]["event_time"] == "۱۶:۳۰ تا ۱۹:۰۰"
    assert observed["data"]["ticket_type_name"] == "ورودی ویژه"
    assert observed["data"]["serial"] == TICKET["serial"]
    assert "issued_at" not in observed["data"]
    assert observed["data"]["qr_data"] == "https://ble.ir/nora?start=ftv_" + RESPONSE_ID
    assert sent[0][0] == 73421
    assert sent[0][1] == "بلیتت آماده‌ست 🎫"
    assert not Path(observed["out_path"]).exists()  # temporary image is removed after sending


def test_admin_ticket_verification_shows_the_assigned_type(monkeypatch):
    sent = []
    monkeypatch.setattr(
        shared_api, "verify_bot_form_ticket", lambda *_args: TICKET
    )
    monkeypatch.setattr(
        flow, "send", lambda cid, text, _keyboard=None: sent.append((cid, text)) or "sent"
    )

    assert flow.verify(99999, 99999, RESPONSE_ID) == "sent"
    assert sent[0][0] == 99999
    assert "مدل بلیت: ورودی ویژه" in sent[0][1]
    assert TICKET["serial"] in sent[0][1]


def test_public_claim_is_private_and_uses_shared_api(monkeypatch):
    calls = []
    monkeypatch.setattr(
        flow, "send", lambda cid, text, _keyboard=None: calls.append((cid, text)) or "sent"
    )
    monkeypatch.setattr(
        flow,
        "_deliver",
        lambda cid, ticket: calls.append((cid, ticket["serial"])) or "ticket-sent",
    )
    monkeypatch.setattr(
        shared_api,
        "claim_bot_form_ticket",
        lambda uid, token: calls.append((uid, token)) or TICKET,
    )

    assert flow.deliver_claim(-100, 73421, "T" * 48) == "sent"
    assert calls[0][0] == -100
    assert len(calls) == 1

    assert flow.deliver_claim(73421, 73421, "T" * 48) == "ticket-sent"
    assert calls[-2] == (73421, "T" * 48)
    assert calls[-1] == (73421, TICKET["serial"])


def test_missing_receipt_points_to_the_form_without_collecting_it_in_bale(monkeypatch):
    calls = []
    ticket = {**TICKET, "receipt_required": True, "receipt_submitted": False}
    monkeypatch.setattr(
        shared_api,
        "claim_bot_form_ticket",
        lambda uid, token: calls.append((uid, token)) or ticket,
    )
    monkeypatch.setattr(
        flow,
        "_deliver",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("ticket must wait for the form upload")
        ),
    )
    monkeypatch.setattr(
        flow, "send", lambda cid, text, _keyboard=None: calls.append((cid, text)) or "sent"
    )

    assert flow.deliver_claim(73421, 73421, "T" * 48) == "sent"
    assert calls[0] == (73421, "T" * 48)
    assert calls[1][0] == 73421
    assert "فیش" in calls[1][1] and "خود فرم" in calls[1][1]


def test_reopened_claim_delivers_ticket_after_receipt_was_submitted(monkeypatch):
    ticket = {**TICKET, "receipt_required": True, "receipt_submitted": True}
    sent = []
    monkeypatch.setattr(
        shared_api, "claim_bot_form_ticket", lambda *_args: ticket
    )
    monkeypatch.setattr(
        flow, "_deliver", lambda cid, data: sent.append((cid, data)) or "ticket-sent"
    )

    assert flow.deliver_claim(73421, 73421, "T" * 48) == "ticket-sent"
    assert sent == [(73421, ticket)]


def test_image_render_failure_never_substitutes_a_text_only_ticket(monkeypatch):
    sent = []
    fake_renderer = SimpleNamespace(
        build_shared_form_ticket=lambda *_args, **_kwargs: None,
        build_for_response=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy response lookup must not be used")
        ),
    )
    monkeypatch.setitem(sys.modules, "ticket", fake_renderer)
    monkeypatch.setattr(
        flow, "send", lambda cid, text, _keyboard=None: sent.append((cid, text)) or "sent"
    )
    monkeypatch.setattr(
        flow,
        "send_photo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no image was rendered")),
    )

    assert flow._deliver(73421, TICKET) == "sent"
    assert sent[0][0] == 73421
    assert "عکس بلیت رو بسازم" in sent[0][1]
    assert TICKET["serial"] not in sent[0][1]


def test_waitlist_does_not_request_or_render_a_ticket(monkeypatch):
    calls = []
    monkeypatch.setattr(
        flow, "send", lambda cid, text, _keyboard=None: calls.append((cid, text)) or "sent"
    )
    monkeypatch.setattr(
        shared_api,
        "get_bot_form_ticket",
        lambda *_args: (_ for _ in ()).throw(shared_api.SharedAPIError(409, "ticket_not_accepted")),
    )
    monkeypatch.setattr(
        flow,
        "_deliver",
        lambda *_args: (_ for _ in ()).throw(AssertionError("ticket must not be rendered")),
    )

    assert flow.deliver_response(73421, 73421, TICKET["form_id"], RESPONSE_ID) is None
    assert calls == []


def test_manual_receipt_review_claim_explains_waiting_without_issuing_a_ticket(monkeypatch):
    calls = []
    monkeypatch.setattr(
        shared_api,
        "claim_bot_form_ticket",
        lambda *_args: (_ for _ in ()).throw(
            shared_api.SharedAPIError(409, "ticket_payment_not_confirmed")
        ),
    )
    monkeypatch.setattr(
        flow, "send", lambda cid, text, _keyboard=None: calls.append((cid, text)) or "sent"
    )
    monkeypatch.setattr(
        flow,
        "_deliver",
        lambda *_args: (_ for _ in ()).throw(AssertionError("ticket must wait for manual approval")),
    )

    assert flow.deliver_claim(73421, 73421, "T" * 48) == "sent"
    assert calls[0][0] == 73421
    assert "بازبینی دستی" in calls[0][1]
    assert "همین پیوند" in calls[0][1]
    assert "اگر رسید رو فرستادی" in calls[0][1]
    assert "اگر نه" in calls[0][1]

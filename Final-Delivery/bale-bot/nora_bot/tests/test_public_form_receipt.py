"""Public-form receipt review remains in the shared workflow inbox."""
# ruff: noqa: INP001
from __future__ import annotations

import sys
from pathlib import Path


BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

import payments  # noqa: E402
import shared_workflows  # noqa: E402


FORM_ID = "123e4567-e89b-12d3-a456-426614174000"
RESPONSE_ID = "123e4567-e89b-12d3-a456-426614174001"


def test_public_form_receipt_manager_card_has_web_context_without_a_fake_amount():
    lines = shared_workflows._task_lines({
        "id": "123e4567-e89b-12d3-a456-426614174088",
        "kind": "receipt_review",
        "bale_user_id": "73421",
        "payload": {
            "registration_source": "public_form",
            "event_title": "کارگاه فرهنگ ایرانی",
            "ref_code": "F123E4567E",
            "form_id": FORM_ID,
            "form_response_id": RESPONSE_ID,
        },
    })

    assert lines[0] == "🧾 بررسی فیش ثبت‌نام فرم وب"
    assert any("رویداد: کارگاه فرهنگ ایرانی" in line for line in lines)
    assert any("کد پیگیری: F123E4567E" in line for line in lines)
    assert not any("مبلغ:" in line for line in lines)


def test_public_form_projection_never_writes_legacy_sqlite_receipt_tables(monkeypatch):
    executed = []
    actions = []
    monkeypatch.setattr(
        payments,
        "db_execute",
        lambda *args, **kwargs: executed.append((args, kwargs)) or None,
    )
    monkeypatch.setattr(
        payments, "log_action", lambda *args, **kwargs: actions.append((args, kwargs))
    )
    task = {
        "id": "123e4567-e89b-12d3-a456-426614174088",
        "kind": "receipt_review",
        "status": "rejected",
        "bale_user_id": "73421",
        "review_reason": "نامعتبر",
        "payload": {
            "registration_source": "public_form",
            "form_id": FORM_ID,
            "form_response_id": RESPONSE_ID,
        },
    }

    assert payments.apply_shared_review_projection(task) is None
    assert executed == []
    assert actions and actions[0][0][1] == "public_form_receipt_rejected"

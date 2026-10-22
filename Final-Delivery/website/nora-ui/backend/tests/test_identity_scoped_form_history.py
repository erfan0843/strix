"""یک حساب منطقی، یک سابقه: خواندن سوابق فرم در وب و ربات پس از پیوند هویت بله.

این آزمون‌ها مرزهای دسترسی را می‌سنجند، نه فقط شکل پاسخ:

- حساب پیوندشده در هر دو رابط همان مجموعهٔ سوابق را می‌بیند (نه نصفِ آن).
- رکوردی که با هر دو کلید (`account_id` و `bot_bale_user_id`) به همان شخص اشاره دارد
  دو بار شمرده نمی‌شود.
- پیوند، هیچ رکوردی از حساب دیگر را باز نمی‌کند؛ حتی رکورد متناقضی که شناسهٔ بلهٔ این
  حساب را یده اما صریحاً مال حساب دیگری است.
- هویت بلهٔ پیوندنخورده فقط ردیف‌های legacy (بدون `account_id`) خودش را می‌بیند؛
  هیچ ردیف مالک‌داری - مال هر حسابی - از مسیر بله بدون پیوند تأییدشده خوانده نمی‌شود.
- ترتیب، صفحه‌بندی، شمارش کل، قرارداد پاسخ و مدیریت خطا تغییر نمی‌کند.
- این مسیرها فقط می‌خوانند: هیچ ردیفی ایجاد، حذف، جابه‌جا یا بازنویسی نمی‌شود.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import (  # noqa: E402
    AccountRecord,
    AccountSessionRecord,
    Base,
    FormRecord,
    FormResponseDraftRecord,
    FormResponseRecord,
    PlatformIdentityRecord,
)
from backend.security import token_digest  # noqa: E402

BOT_TOKEN = "b" * 48
PHONE_PROVIDER = "phone"
BALE_PROVIDER = "bale"
OWNER_ID = "owner-01"
SESSION_PREFIX = "scope-session-"
CSRF_PREFIX = "scope-csrf-"


# ---------------------------------------------------------------------------
# ساخت دادهٔ آزمون
# ---------------------------------------------------------------------------

@pytest.fixture
def scope_env():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None,
        owner_id=OWNER_ID,
        owner_username="",
        owner_password_hash="",
        cookie_secure=False,
        bot_service_token=BOT_TOKEN,
    )
    client = TestClient(create_app(settings, engine=engine))
    with client:
        yield client, engine
    engine.dispose()


def seed_account(engine, account_id: str, *, bale_user_id: str | None = None) -> str:
    """حساب تأییدشده با شماره + نشست؛ در صورت نیاز هویت بلهٔ پیوندشده."""
    with Session(engine) as db:
        db.add(AccountRecord(id=account_id))
        db.add(
            PlatformIdentityRecord(
                id=str(uuid.uuid4()),
                account_id=account_id,
                provider=PHONE_PROVIDER,
                provider_user_id=token_digest("verified-phone:" + account_id),
            )
        )
        if bale_user_id is not None:
            db.add(
                PlatformIdentityRecord(
                    id=str(uuid.uuid4()),
                    account_id=account_id,
                    provider=BALE_PROVIDER,
                    provider_user_id=bale_user_id,
                )
            )
        db.add(
            AccountSessionRecord(
                id=str(uuid.uuid4()),
                account_id=account_id,
                auth_provider=PHONE_PROVIDER,
                token_hash=token_digest(SESSION_PREFIX + account_id),
                csrf_hash=token_digest(CSRF_PREFIX + account_id),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
            )
        )
        db.commit()
    return account_id


def web_client(client: TestClient, account_id: str) -> TestClient:
    """کلاینتی که با نشست همان حساب وارد شده است (کوکی‌ها روی همان اپ)."""
    browser = TestClient(client.app)
    settings = client.app.state.settings
    browser.cookies.set(settings.account_cookie_name, SESSION_PREFIX + account_id, path="/")
    browser.cookies.set(settings.account_csrf_cookie_name, CSRF_PREFIX + account_id, path="/")
    return browser


def bot_headers(token: str = BOT_TOKEN) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


def seed_form(engine, form_id: str, *, model: str = "registration", title: str = "ثبت نام کارگاه") -> str:
    with Session(engine) as db:
        db.add(
            FormRecord(
                id=form_id,
                owner_id=OWNER_ID,
                title=title,
                model=model,
                need="reg",
                status="published",
                version=1,
                settings={},
            )
        )
        db.commit()
    return form_id


def seed_response(
    engine,
    *,
    form_id: str,
    status: str = "accepted",
    account_id: str | None = None,
    bale_user_id: str | None = None,
    created_at: datetime | None = None,
    answers: dict | None = None,
) -> str:
    """یک پاسخ ثبت‌شده با کلیدهای مالکیت مشخص؛ هیچ منطق کسب‌وکاری اجرا نمی‌شود."""
    response_id = str(uuid.uuid4())
    draft_id = str(uuid.uuid4())
    moment = created_at or datetime.now(timezone.utc)
    with Session(engine) as db:
        db.add(
            FormResponseDraftRecord(
                id=draft_id,
                form_id=form_id,
                account_id=account_id,
                form_version=1,
                token_hash=uuid.uuid4().hex + uuid.uuid4().hex,
                bot_bale_user_id=bale_user_id,
                answers=answers or {"full-name": "آزمایش"},
                companions=[],
                expires_at=moment + timedelta(days=1),
                created_at=moment,
                updated_at=moment,
            )
        )
        db.add(
            FormResponseRecord(
                id=response_id,
                form_id=form_id,
                draft_id=draft_id,
                form_version=1,
                status=status,
                answers=answers or {"full-name": "آزمایش"},
                companions=[],
                form_snapshot={"name": "ثبت نام کارگاه", "version": 1},
                created_at=moment,
                updated_at=moment,
            )
        )
        db.commit()
    return response_id


def web_history(client: TestClient, query: str = "") -> dict:
    response = client.get("/api/account/registrations" + query)
    assert response.status_code == 200, response.text
    return response.json()


def bot_history(client: TestClient, bale_user_id: str, page: int = 0) -> dict:
    response = client.get(
        "/api/bot/forms/mine",
        params={"bale_user_id": bale_user_id, "page": page},
        headers=bot_headers(),
    )
    assert response.status_code == 200, response.text
    return response.json()


def ids_of(history: dict) -> set[str]:
    return {item["id"] for item in history["items"]}


# ---------------------------------------------------------------------------
# ۱ و ۲ — حساب پیوندشده در هر دو رابط همان مجموعه را می‌بیند
# ---------------------------------------------------------------------------

def test_linked_account_reads_its_own_and_its_bale_records_in_both_interfaces(scope_env):
    client, engine = scope_env
    seed_account(engine, "acct-a", bale_user_id="900001")
    seed_form(engine, "form-reg")
    from_web = seed_response(engine, form_id="form-reg", account_id="acct-a")
    from_bale = seed_response(engine, form_id="form-reg", bale_user_id="900001")

    web = web_history(web_client(client, "acct-a"))
    assert web["total"] == 2
    assert ids_of(web) == {from_web, from_bale}

    bot = bot_history(client, "900001")
    assert bot["total"] == 2
    assert ids_of(bot) == {from_web, from_bale}


def test_bot_response_detail_opens_every_record_the_bot_lists(scope_env):
    """اگر ربات رکوردی را فهرست می‌کند، باز کردن همان رکورد هم باید مجاز باشد."""
    client, engine = scope_env
    seed_account(engine, "acct-a", bale_user_id="900001")
    seed_form(engine, "form-reg")
    from_web = seed_response(engine, form_id="form-reg", account_id="acct-a")
    from_bale = seed_response(engine, form_id="form-reg", bale_user_id="900001")

    listed = bot_history(client, "900001")
    assert ids_of(listed) == {from_web, from_bale}
    for response_id in (from_web, from_bale):
        detail = client.get(
            f"/api/bot/forms/responses/{response_id}",
            params={"bale_user_id": "900001"},
            headers=bot_headers(),
        )
        assert detail.status_code == 200, (response_id, detail.text)
        assert detail.json()["response"]["id"] == response_id


# ---------------------------------------------------------------------------
# ۳ — ردیف مشترک (هر دو کلید) دوباره شمرده نمی‌شود
# ---------------------------------------------------------------------------

def test_record_linked_through_both_keys_is_counted_once(scope_env):
    client, engine = scope_env
    seed_account(engine, "acct-a", bale_user_id="900001")
    seed_form(engine, "form-reg")
    account_only = seed_response(engine, form_id="form-reg", account_id="acct-a")
    # همان شخص: پاسخ وب که بعداً بلیتش در بله دریافت شده و هر دو کلید را دارد.
    both_keys = seed_response(
        engine, form_id="form-reg", account_id="acct-a", bale_user_id="900001"
    )
    bale_only = seed_response(engine, form_id="form-reg", bale_user_id="900001")

    web = web_history(web_client(client, "acct-a"))
    bot = bot_history(client, "900001")

    for history in (web, bot):
        returned = [item["id"] for item in history["items"]]
        assert len(returned) == len(set(returned)), "شناسهٔ تکراری در نتیجه"
        assert history["total"] == 3
        assert set(returned) == {account_only, both_keys, bale_only}


# ---------------------------------------------------------------------------
# ۴ — پیوند، رکورد حساب دیگر را باز نمی‌کند
# ---------------------------------------------------------------------------

def test_linking_never_reveals_another_accounts_records(scope_env):
    client, engine = scope_env
    seed_account(engine, "acct-a", bale_user_id="900001")
    seed_account(engine, "acct-b", bale_user_id="900002")
    seed_form(engine, "form-reg")

    own = seed_response(engine, form_id="form-reg", account_id="acct-a")
    other_account = seed_response(engine, form_id="form-reg", account_id="acct-b")
    other_bale = seed_response(engine, form_id="form-reg", bale_user_id="900002")
    # رکورد متناقض: صریحاً مال acct-b است اما شناسهٔ بلهٔ acct-a را یده است.
    contradictory = seed_response(
        engine, form_id="form-reg", account_id="acct-b", bale_user_id="900001"
    )

    web_a = web_history(web_client(client, "acct-a"))
    assert ids_of(web_a) == {own}
    assert other_account not in ids_of(web_a)
    assert other_bale not in ids_of(web_a)
    assert contradictory not in ids_of(web_a), "رکورد حساب دیگر از راه پیوند دیده شد"

    # حساب b سوابق خودش و هویت بلهٔ پیوندشدهٔ خودش را می‌بیند — از جمله رکورد متناقض.
    web_b = web_history(web_client(client, "acct-b"))
    assert ids_of(web_b) == {other_account, other_bale, contradictory}
    assert own not in ids_of(web_b)

    # رباتِ پیوندشدهٔ acct-a فقط رکوردهای همان حساب را می‌بیند. رکورد متناقض
    # (`account_id=acct-b` + کلید بلهٔ ۹۰۰۰۰۱) مالک صریح دارد، پس از مسیر بلهٔ A نمی‌آید.
    bot_a = bot_history(client, "900001")
    assert ids_of(bot_a) == {own}
    assert bot_a["total"] == 1
    assert other_account not in ids_of(bot_a)
    assert other_bale not in ids_of(bot_a)
    assert contradictory not in ids_of(bot_a), "مالکیت صریح حساب دیگر نادیده گرفته شد"
    detail = client.get(
        f"/api/bot/forms/responses/{contradictory}",
        params={"bale_user_id": "900001"},
        headers=bot_headers(),
    )
    assert detail.status_code == 404


def test_explicit_account_owner_wins_over_a_stale_bale_tag(scope_env):
    """`account_id` مالکیت صریح است: برچسب بلهٔ جامانده دسترسی نمی‌سازد.

    این همان حالتی است که در ممیزی «متناقض» نامیده شد: ردیفی که صریحاً مال حساب B
    است اما کلید بلهٔ کاربر A را هم یدک می‌کشد. قرارداد داده می‌گوید `account_id`
    حرف آخر را می‌زند؛ پس A آن را نه در فهرست، نه در شمارش و نه در جزئیات نمی‌بیند.
    در مقابل، ردیف legacy که هیچ `account_id` ندارد تنها با همان کلید بله دیده می‌شود.
    """
    client, engine = scope_env
    seed_account(engine, "acct-a", bale_user_id="900001")
    seed_account(engine, "acct-b")
    seed_form(engine, "form-reg")

    owned_by_b = seed_response(engine, form_id="form-reg", account_id="acct-b")
    stale_tag_on_b = seed_response(
        engine, form_id="form-reg", account_id="acct-b", bale_user_id="900001"
    )
    legacy_untagged = seed_response(engine, form_id="form-reg", bale_user_id="900001")

    bot = bot_history(client, "900001")
    assert ids_of(bot) == {legacy_untagged}
    assert bot["total"] == 1
    assert owned_by_b not in ids_of(bot)
    assert stale_tag_on_b not in ids_of(bot)

    for hidden in (owned_by_b, stale_tag_on_b):
        detail = client.get(
            f"/api/bot/forms/responses/{hidden}",
            params={"bale_user_id": "900001"},
            headers=bot_headers(),
        )
        assert detail.status_code == 404

    # صاحب صریح هر دو ردیف، همچنان در وب می‌بیندشان.
    web_b = web_history(web_client(client, "acct-b"))
    assert ids_of(web_b) == {owned_by_b, stale_tag_on_b}


def test_list_count_and_detail_share_one_boundary_for_contradictory_rows(scope_env):
    """فهرست، شمارش کل و جزئیات باید یک مرز داشته باشند، نه سه مرز جدا."""
    client, engine = scope_env
    seed_account(engine, "acct-a", bale_user_id="900001")
    seed_account(engine, "acct-b", bale_user_id="900002")
    seed_form(engine, "form-reg")
    visible = seed_response(engine, form_id="form-reg", bale_user_id="900001")
    hidden = seed_response(
        engine, form_id="form-reg", account_id="acct-b", bale_user_id="900001"
    )

    bot = bot_history(client, "900001")
    assert bot["total"] == len(bot["items"]) == 1
    assert ids_of(bot) == {visible}
    listed_id = bot["items"][0]["id"]
    ok_detail = client.get(
        f"/api/bot/forms/responses/{listed_id}",
        params={"bale_user_id": "900001"},
        headers=bot_headers(),
    )
    assert ok_detail.status_code == 200
    hidden_detail = client.get(
        f"/api/bot/forms/responses/{hidden}",
        params={"bale_user_id": "900001"},
        headers=bot_headers(),
    )
    assert hidden_detail.status_code == 404

    # همان ردیف پنهان برای حساب صاحبش، در وب دیده می‌شود؛ ردیف کاربر A نه.
    web_b = web_history(web_client(client, "acct-b"))
    assert web_b["total"] == 1
    assert ids_of(web_b) == {hidden}
    assert visible not in ids_of(web_b)


# ---------------------------------------------------------------------------
# ۵ — هویت بلهٔ پیوندنخورده دسترسی تازه نمی‌گیرد
# ---------------------------------------------------------------------------

def test_unlinked_bale_identity_cannot_read_phone_account_records(scope_env):
    client, engine = scope_env
    seed_account(engine, "acct-a")  # بدون هویت بله، ولی سابقه دارد
    seed_form(engine, "form-reg")
    account_record = seed_response(engine, form_id="form-reg", account_id="acct-a")
    own_bale_record = seed_response(engine, form_id="form-reg", bale_user_id="900009")

    bot = bot_history(client, "900009")
    assert ids_of(bot) == {own_bale_record}
    assert bot["total"] == 1
    assert account_record not in ids_of(bot)

    detail = client.get(
        f"/api/bot/forms/responses/{account_record}",
        params={"bale_user_id": "900009"},
        headers=bot_headers(),
    )
    assert detail.status_code == 404

    # و وب همان حساب، همچنان فقط سابقهٔ خودش را می‌بیند.
    web = web_history(web_client(client, "acct-a"))
    assert ids_of(web) == {account_record}


def test_unlinked_bale_identity_never_reaches_a_row_owned_by_any_account(scope_env):
    """هویت بلهٔ پیوندنخورده فقط ردیف‌های legacy (بدون مالک) خودش را می‌بیند.

    ردیفی که صریحاً `account_id=B` دارد ولی برچسب بلهٔ U را هم یدک می‌کشد، از
    مسیر ربات برای U دیده نمی‌شود؛ U هیچ حسابی را اثبات نکرده است، پس هیچ ردیف
    مالک‌داری - مال هر حسابی که باشد - از این مسیر خوانده نمی‌شود. فهرست، شمارش و
    جزئیات یک مرز دارند و ردیف برای مالک واقعی‌اش (B) در وب دست‌نخورده می‌ماند.
    """
    client, engine = scope_env
    seed_account(engine, "acct-b")
    seed_form(engine, "form-reg")
    legacy_only = seed_response(engine, form_id="form-reg", bale_user_id="900010")
    owned_by_b_with_u_tag = seed_response(
        engine, form_id="form-reg", account_id="acct-b", bale_user_id="900010"
    )

    bot = bot_history(client, "900010")
    assert ids_of(bot) == {legacy_only}
    assert bot["total"] == len(bot["items"]) == 1

    hidden = client.get(
        f"/api/bot/forms/responses/{owned_by_b_with_u_tag}",
        params={"bale_user_id": "900010"},
        headers=bot_headers(),
    )
    assert hidden.status_code == 404
    shown = client.get(
        f"/api/bot/forms/responses/{legacy_only}",
        params={"bale_user_id": "900010"},
        headers=bot_headers(),
    )
    assert shown.status_code == 200

    web_b = web_history(web_client(client, "acct-b"))
    assert ids_of(web_b) == {owned_by_b_with_u_tag}
    assert web_b["total"] == 1

    # هیچ ردیفی برای «حل تناقض» جابه‌جا یا بازنویسی نشده است.
    with Session(engine) as db:
        row = db.get(FormResponseDraftRecord, db.scalar(
            select(FormResponseRecord.draft_id).where(FormResponseRecord.id == owned_by_b_with_u_tag)
        ))
        assert row is not None
        assert row.account_id == "acct-b"
        assert row.bot_bale_user_id == "900010"


# ---------------------------------------------------------------------------
# ۶ — حالت خالی، صفحه‌بندی، ترتیب، فیلتر وضعیت و قرارداد پاسخ
# ---------------------------------------------------------------------------

def test_empty_state_pagination_order_and_status_contract(scope_env):
    client, engine = scope_env
    seed_account(engine, "acct-empty")
    seed_account(engine, "acct-a", bale_user_id="900001")
    seed_form(engine, "form-reg")
    seed_form(engine, "form-survey", model="survey", title="نظرسنجی")

    empty_web = web_history(web_client(client, "acct-empty"))
    assert empty_web == {
        "source": "shared_server_database",
        "items": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
        "has_more": False,
    }
    empty_bot = bot_history(client, "900001")
    assert empty_bot == {
        "source": "shared_server_database",
        "items": [],
        "total": 0,
        "page": 0,
        "pages": 0,
        "page_size": 6,
    }

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    created = []
    for index in range(8):
        account_id = "acct-a" if index % 2 == 0 else None
        bale_user_id = None if index % 2 == 0 else "900001"
        created.append(
            seed_response(
                engine,
                form_id="form-reg",
                account_id=account_id,
                bale_user_id=bale_user_id,
                status="waitlisted" if index == 0 else "accepted",
                created_at=base + timedelta(minutes=index),
            )
        )

    bot_first = bot_history(client, "900001", page=0)
    assert bot_first["total"] == 8
    assert bot_first["pages"] == 2
    assert bot_first["page_size"] == 6
    assert len(bot_first["items"]) == 6
    assert [item["id"] for item in bot_first["items"]] == list(reversed(created[-6:]))

    bot_second = bot_history(client, "900001", page=1)
    assert [item["id"] for item in bot_second["items"]] == list(reversed(created[:2]))

    # فیلتر وضعیت در قرارداد فعلی هر دو وضعیت مجاز را می‌پذیرد.
    assert {item["status"] for item in bot_first["items"]} <= {"accepted", "waitlisted"}

    web_first = web_history(web_client(client, "acct-a"), "?limit=3&offset=0")
    assert web_first["total"] == 8  # ۴ رکورد حساب + ۴ رکورد بلهٔ پیوندشده
    assert web_first["has_more"] is True
    assert [item["id"] for item in web_first["items"]] == list(reversed(created[-3:]))
    web_last = web_history(web_client(client, "acct-a"), "?limit=3&offset=6")
    assert [item["id"] for item in web_last["items"]] == list(reversed(created[:2]))
    assert web_last["has_more"] is False

    # قرارداد پاسخ وب: هیچ فیلد حساس/اضافه‌ای برنگردد.
    item = web_first["items"][0]
    assert not {"answers", "account_id", "bot_bale_user_id", "registrant_mobile"} & set(item)
    assert set(item) == {
        "id", "form_name", "event_title", "event_date", "event_time", "status",
        "payment_status", "receipt_uploaded", "ticket_checked_in", "ticket_type",
        "created_at",
        "event_id",  # فاز ۹.۳: کلید اتصال «رویدادهای من» به آرشیو (شناسهٔ رویداد؛ نه داده حساس، نه مبنای دسترسی)
    }
    assert isinstance(item["event_id"], str)

    # مدل فرم در قرارداد وب محفوظ است: نظرسنجی در «ثبت‌نام‌های من» نمی‌آید.
    seed_response(engine, form_id="form-survey", account_id="acct-a")
    assert web_history(web_client(client, "acct-a"), "?limit=100")["total"] == 8


# ---------------------------------------------------------------------------
# ۷ — خطاها و درخواست‌های غیرمجاز
# ---------------------------------------------------------------------------

def test_unauthorized_and_invalid_requests_are_unchanged(scope_env):
    client, engine = scope_env
    seed_account(engine, "acct-a", bale_user_id="900001")
    seed_form(engine, "form-reg")
    record = seed_response(engine, form_id="form-reg", account_id="acct-a")

    anonymous = TestClient(client.app)
    assert anonymous.get("/api/account/registrations").status_code == 401

    assert client.get(
        "/api/bot/forms/mine", params={"bale_user_id": "900001"}
    ).status_code == 401
    assert client.get(
        "/api/bot/forms/mine",
        params={"bale_user_id": "900001"},
        headers=bot_headers("wrong-token"),
    ).status_code == 401
    assert client.get(
        "/api/bot/forms/mine", params={"bale_user_id": "not-a-number"}, headers=bot_headers()
    ).status_code == 422
    assert client.get(
        "/api/bot/forms/responses/../../etc/passwd",
        params={"bale_user_id": "900001"},
        headers=bot_headers(),
    ).status_code in (404, 422)
    assert client.get(
        "/api/bot/forms/responses/not-a-response-id",
        params={"bale_user_id": "900001"},
        headers=bot_headers(),
    ).status_code == 422
    assert client.get(
        "/api/bot/forms/responses/" + str(uuid.uuid4()),
        params={"bale_user_id": "900001"},
        headers=bot_headers(),
    ).status_code == 404

    # شناسهٔ حسابِ ارسالی کلاینت هیچ‌وقت دامنهٔ دسترسی را باز نمی‌کند.
    other = web_history(web_client(client, "acct-a"), "?account_id=acct-b")
    assert ids_of(other) == {record}


# ---------------------------------------------------------------------------
# ۸ — این مسیرها فقط می‌خوانند
# ---------------------------------------------------------------------------

def _snapshot(engine) -> dict:
    with Session(engine) as db:
        return {
            "accounts": db.scalar(select(func.count()).select_from(AccountRecord)),
            "identities": db.scalar(select(func.count()).select_from(PlatformIdentityRecord)),
            "drafts": db.scalar(select(func.count()).select_from(FormResponseDraftRecord)),
            "responses": db.scalar(select(func.count()).select_from(FormResponseRecord)),
            "draft_owner": sorted(
                (row.id, row.account_id, row.bot_bale_user_id, row.updated_at)
                for row in db.scalars(select(FormResponseDraftRecord))
            ),
            "response_owner": sorted(
                (row.id, row.draft_id, row.status, row.updated_at)
                for row in db.scalars(select(FormResponseRecord))
            ),
        }


def test_read_paths_never_create_move_or_rewrite_rows(scope_env):
    client, engine = scope_env
    seed_account(engine, "acct-a", bale_user_id="900001")
    seed_account(engine, "acct-b")
    seed_form(engine, "form-reg")
    seed_response(engine, form_id="form-reg", account_id="acct-a")
    seed_response(engine, form_id="form-reg", bale_user_id="900001")
    seed_response(engine, form_id="form-reg", account_id="acct-b")

    before = _snapshot(engine)
    for _ in range(3):
        web_history(web_client(client, "acct-a"))
        bot_history(client, "900001")
        bot_history(client, "900001", page=1)
        client.get(
            "/api/bot/forms/responses/" + next(iter(ids_of(bot_history(client, "900001")))),
            params={"bale_user_id": "900001"},
            headers=bot_headers(),
        )
    assert _snapshot(engine) == before

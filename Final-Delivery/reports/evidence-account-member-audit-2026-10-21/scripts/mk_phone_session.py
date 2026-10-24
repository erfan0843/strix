"""Local test helper: create (or reuse) a verified-phone account in the preview DB and mint a session.
Prints JSON {account_id, session, csrf, created}. Test data only; never run against a live DB."""
import json, os, sys, uuid
from datetime import datetime, timedelta, timezone
sys.path.insert(0, '/home/user/strix/Final-Delivery/website/nora-ui')
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.accounts import get_or_create_phone_account, phone_account_exists
from backend.models import AccountSessionRecord, AccountProfileRecord
from backend.security import new_token, token_digest

phone = sys.argv[1] if len(sys.argv) > 1 else '09120000001'
with_profile = len(sys.argv) > 2 and sys.argv[2] == 'profile'
pepper = os.environ['NORA_OTP_PEPPER']
engine = create_engine(os.environ['NORA_DATABASE_URL'])
with Session(engine) as db:
    existed = phone_account_exists(db, phone, pepper=pepper)
    account = get_or_create_phone_account(db, phone, pepper=pepper)
    if with_profile and db.get(AccountProfileRecord, account.id) is None:
        db.add(AccountProfileRecord(account_id=account.id, fields={'fullName': 'عضو آزمایشی'}, updated_at=datetime.now(timezone.utc)))
    raw_session, raw_csrf = new_token(), new_token()
    db.add(AccountSessionRecord(id=str(uuid.uuid4()), account_id=account.id, auth_provider='phone',
                                token_hash=token_digest(raw_session), csrf_hash=token_digest(raw_csrf),
                                expires_at=datetime.now(timezone.utc) + timedelta(hours=2)))
    db.commit()
    print(json.dumps({'account_id': account.id, 'session': raw_session, 'csrf': raw_csrf, 'created': not existed}))

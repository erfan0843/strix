"""Local test helper: insert an OTP challenge into the preview DB exactly as the server would after
sending a code, so the browser can exercise the REAL /api/auth/phone-otp/verify endpoint while only
the Bale/Safir delivery step is bypassed. Prints JSON {challenge_id, code}. Test data only."""
import json, os, sys, uuid
from datetime import datetime, timedelta, timezone
sys.path.insert(0, '/home/user/strix/Final-Delivery/website/nora-ui')
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.models import PhoneOTPChallengeRecord
from backend.otp import normalize_iran_phone, otp_digest, phone_digest

phone = normalize_iran_phone(sys.argv[1] if len(sys.argv) > 1 else '09120000002')
code = sys.argv[2] if len(sys.argv) > 2 else '482913'
pepper = os.environ['NORA_OTP_PEPPER']
engine = create_engine(os.environ['NORA_DATABASE_URL'])
challenge_id = str(uuid.uuid4())
now = datetime.now(timezone.utc)
with Session(engine) as db:
    db.add(PhoneOTPChallengeRecord(id=challenge_id, phone_hash=phone_digest(pepper, phone),
                                   code_hash=otp_digest(pepper, challenge_id, code),
                                   expires_at=now + timedelta(seconds=180), attempts=0, max_attempts=5, created_at=now))
    db.commit()
print(json.dumps({'challenge_id': challenge_id, 'code': code, 'phone': phone}))

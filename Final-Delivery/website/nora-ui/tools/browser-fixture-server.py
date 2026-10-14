"""Temporary QA server: synthetic isolated fixtures; NO external providers."""
import json
import os
import sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
from uuid import uuid4
UI_ROOT = Path(__file__).resolve().parents[1]
if str(UI_ROOT) not in sys.path:
    sys.path.insert(0, str(UI_ROOT))

import uvicorn
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from backend.app import create_app
from backend.config import Settings
from backend.models import Base,AccountRecord,AccountSessionRecord,OwnerSessionRecord,FormRecord,FormResponseDraftRecord,FormResponseRecord
from backend.security import token_digest

engine=create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
Base.metadata.create_all(engine)
cfg=Settings(database_url=None,owner_id='isolated-qa-owner',owner_username='qa-owner',owner_password_hash=None,cookie_secure=False)
now=datetime.now(timezone.utc);member_token='FAKE_QA_MEMBER_SESSION_ONLY_'+uuid4().hex;owner_token='FAKE_QA_OWNER_SESSION_ONLY_'+uuid4().hex
member_id,other_id,form_id,draft_id,response_id=[str(uuid4()) for _ in range(5)]
with Session(engine) as db:
 db.add_all([AccountRecord(id=member_id),AccountRecord(id=other_id)])
 db.flush()
 db.add(AccountSessionRecord(id=str(uuid4()),account_id=member_id,auth_provider='phone',token_hash=token_digest(member_token),csrf_hash=token_digest('FAKE_QA_CSRF_ONLY'),expires_at=now+timedelta(hours=1)))
 db.add(OwnerSessionRecord(id=str(uuid4()),owner_id=cfg.owner_id,token_hash=token_digest(owner_token),csrf_hash=token_digest('FAKE_QA_OWNER_CSRF_ONLY'),expires_at=now+timedelta(hours=1)))
 db.add(FormRecord(id=form_id,owner_id=cfg.owner_id,title='فرم آزمون ممیزی — دادهٔ واقعی نیست',model='registration',need='registration',status='published',settings={}))
 db.flush()
 db.add(FormResponseDraftRecord(id=draft_id,form_id=form_id,account_id=member_id,form_version=1,token_hash='c'*64,answers={},companions=[],expires_at=now+timedelta(hours=1)))
 db.flush()
 db.add(FormResponseRecord(id=response_id,form_id=form_id,draft_id=draft_id,form_version=1,status='accepted',answers={},companions=[],form_snapshot={'name':'ثبت‌نام آزمون ممیزی — دادهٔ واقعی نیست','event':{'title':'رویداد آزمون ممیزی — دادهٔ واقعی نیست'}}))
 db.commit()
fixture_path = Path(os.getenv('NORA_QA_FIXTURE_FILE', str(UI_ROOT / '.local' / 'qa' / 'fixture.json')))
fixture_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
descriptor = os.open(fixture_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o600)
with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
    json.dump({'member_cookie_name':cfg.account_cookie_name,'member_cookie':member_token,'owner_cookie_name':cfg.cookie_name,'owner_cookie':owner_token,'form_id':form_id,'response_id':response_id}, output)

app=create_app(cfg,engine=engine)
try:
 uvicorn.run(app,host='0.0.0.0',port=int(os.getenv('NORA_QA_PORT','8001')),access_log=False)
finally:
 engine.dispose()

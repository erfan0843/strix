"""اجرای آزمون‌های API گواهی/رسانه/کارتابل روی PostgreSQL یک‌بارمصرف (فقط محیط آزمون).
موتور SQLite داخل ماژول‌های آزمون با موتور PostgreSQL جایگزین می‌شود؛ پیش از هر برنامه، طرح با metadata ساخته و پس از آن حذف می‌شود."""
import importlib, os, sys, traceback
ROOT = "/home/user/strix/Final-Delivery/website/nora-ui"
sys.path.insert(0, ROOT); sys.path.insert(0, ROOT + "/backend/tests")
os.chdir(ROOT + "/backend")
import sqlalchemy as sa
from backend.models import Base
URL = os.environ["NORA_TEST_POSTGRES_URL"]
def pg_engine(*_a, **_k):
    eng = sa.create_engine(URL)
    with eng.begin() as c:
        Base.metadata.drop_all(c)
    return eng
results = []
for modname in ("test_workflows_api", "test_certificates_api", "test_public_media_api"):
    mod = importlib.import_module(modname)
    mod.create_engine = pg_engine
    for name in sorted(n for n in dir(mod) if n.startswith("test_")):
        fn = getattr(mod, name)
        if fn.__module__ != modname: continue
        if fn.__code__.co_argcount: results.append((modname, name, "SKIP(fixture)")); continue
        try:
            fn(); results.append((modname, name, "PASS"))
        except Exception as exc:
            results.append((modname, name, "FAIL: " + repr(exc)[:200])); traceback.print_exc()
for r in results: print(*r)
print("summary:", sum(1 for r in results if r[2]=="PASS"), "passed,", sum(1 for r in results if r[2].startswith("FAIL")), "failed,", sum(1 for r in results if r[2].startswith("SKIP")), "skipped")

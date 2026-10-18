"""Real-server check (isolated preview DB only): stored non-public partner rows vs owner-panel saves.

Usage: nonpublic_check.py inject   -> write flagged rows directly into site_content (simulates legacy/direct DB data)
       nonpublic_check.py verify   -> report public API / owner view / stored ids, then replay a panel-style save
       nonpublic_check.py stored   -> print stored partner ids only
"""
import json, sqlite3, sys
from owner_api import call, login

DB = "/tmp/nora-preview/nora-preview.db"
NON_PUBLIC = [
    {"id": "qa-np-private", "n": "QA نهاد خصوصی (دادهٔ تست)", "privacy": "private"},
    {"id": "qa-np-hidden", "n": "QA نهاد پنهان (دادهٔ تست)", "hidden": True},
    {"id": "qa-np-paused", "n": "QA نهاد متوقف (دادهٔ تست)", "status": "paused"},
    {"id": "qa-np-pending", "n": "QA نهاد منتظر (دادهٔ تست)", "pend": True},
]
NP_IDS = [r["id"] for r in NON_PUBLIC]


def stored():
    c = sqlite3.connect(DB)
    version, raw = c.execute("select version, content from site_content where id='public'").fetchone()
    content = json.loads(raw)
    c.close()
    return version, content


def stored_ids():
    return [r.get("id") for r in stored()[1].get("partners", [])]


def inject():
    c = sqlite3.connect(DB)
    version, raw = c.execute("select version, content from site_content where id='public'").fetchone()
    content = json.loads(raw)
    rows = [r for r in content.get("partners", []) if r.get("id") not in NP_IDS] + NON_PUBLIC
    content["partners"] = rows
    c.execute("update site_content set content=? where id='public'", (json.dumps(content, ensure_ascii=False),))
    c.commit(); c.close()
    print("injected non-public rows; stored ids:", stored_ids())


def verify(label):
    ok = True
    st, pub = call("GET", "/api/public/site-content")
    pub_ids = [r.get("id") for r in pub["content"]["partners"]]
    leak = [i for i in NP_IDS if i in pub_ids]
    print(f"[{label}] public API partner ids: {pub_ids}")
    print(f"[{label}] public API leaks non-public ids: {leak}  ->", "FAIL" if leak else "PASS")
    ok &= not leak
    login()
    st, own = call("GET", "/api/owner/site-content")
    own_ids = [r.get("id") for r in own["content"]["partners"]]
    own_leak = [i for i in NP_IDS if i in own_ids]
    print(f"[{label}] owner view partner ids: {own_ids} (version {own['version']}) non-public shown: {own_leak} ->", "FAIL" if own_leak else "PASS")
    ok &= not own_leak
    for pid in NP_IDS:
        st, _ = call("GET", f"/partner.html?id={pid}")
        print(f"[{label}] GET /partner.html?id={pid} -> {st}", "PASS" if st == 404 else "FAIL")
        ok &= st == 404
    before_version, before = stored()
    others_before = {k: before.get(k) for k in ("events", "people", "articles", "banners", "library", "cooperation")}
    # panel-style save: resend exactly what the owner view returned (plus one edit), with expected_version
    rows = [dict(r) for r in own["content"]["partners"]]
    if rows:
        rows[0] = {**rows[0], "s": (rows[0].get("s") or "") + " (ویرایش QA)"}
    st, res = call("PATCH", "/api/owner/site-content", {"content": {"partners": rows}, "expected_version": own["version"]})
    print(f"[{label}] panel-style PATCH partners -> {st}")
    ok &= st == 200
    after_version, after = stored()
    kept = [i for i in NP_IDS if i in [r.get("id") for r in after.get("partners", [])]]
    lost = [i for i in NP_IDS if i not in kept]
    print(f"[{label}] stored non-public rows after save: kept={kept} lost={lost} ->", "FAIL" if lost else "PASS")
    ok &= not lost
    same_others = all(after.get(k) == v for k, v in others_before.items())
    print(f"[{label}] other categories unchanged ->", "PASS" if same_others else "FAIL")
    ok &= same_others
    st, pub2 = call("GET", "/api/public/site-content")
    pub2_ids = [r.get("id") for r in pub2["content"]["partners"]]
    leak2 = [i for i in NP_IDS if i in pub2_ids]
    print(f"[{label}] public API after save: {pub2_ids} leaks: {leak2} ->", "FAIL" if leak2 else "PASS")
    ok &= not leak2
    print(f"[{label}] RESULT:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "inject":
        inject()
    elif cmd == "stored":
        print("stored partner ids:", stored_ids())
    else:
        sys.exit(0 if verify(sys.argv[2] if len(sys.argv) > 2 else "verify") else 1)

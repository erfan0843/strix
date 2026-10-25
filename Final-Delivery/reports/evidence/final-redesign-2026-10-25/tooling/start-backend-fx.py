#!<local>
"""Fixture backend: args <port> <ui-root>. Loads preview-fixture.env (DB = nora-live.db, restored from the fixture) and execs uvicorn."""
import os, sys
port, ui_root = sys.argv[1], sys.argv[2]
for line in open("<local>", encoding="utf-8"):
    line = line.rstrip("\n")
    if not line or line.startswith("#") or "=" not in line: continue
    k, v = line.split("=", 1); os.environ[k.strip()] = v.strip().strip('"').strip("'")
os.environ.setdefault("NORA_FRAME_ANCESTORS", "'self' https://*.e2b.app https://*.arena.ai")
os.environ.setdefault("NORA_COOKIE_SECURE", "false"); os.environ.setdefault("NORA_COOKIE_SAMESITE", "lax")
os.chdir(ui_root)
os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", port, "--proxy-headers", "--forwarded-allow-ips=*"])

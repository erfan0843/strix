#!<local>
"""Load preview.env (values may contain spaces) and exec uvicorn for the test backend on :8001."""
import os, sys
env_path = "<local>"
for line in open(env_path, encoding="utf-8"):
    line = line.rstrip("\n")
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ[k.strip()] = v.strip().strip('"').strip("'")
os.environ.setdefault("NORA_FRAME_ANCESTORS", "'self' https://*.e2b.app https://*.arena.ai")
os.environ.setdefault("NORA_COOKIE_SECURE", "false")
os.environ.setdefault("NORA_COOKIE_SAMESITE", "lax")
os.chdir("<local>")
os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8001",
                          "--proxy-headers", "--forwarded-allow-ips=*"])

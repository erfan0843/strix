"""Optional PostgreSQL migration regression on a newly-created disposable server.

Requires the development-only package pgserver==0.1.4 (native Linux/macOS).
Never reads a production DSN; the child receives only this new Unix-socket URL.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main() -> int:
    try:
        import pgserver
        from sqlalchemy.engine import make_url
    except ImportError:
        print("پیش‌نیاز اختیاری نصب نیست: python -m pip install pgserver==0.1.4", file=sys.stderr)
        return 2
    if os.name == "nt":
        print("در Windows از PostgreSQL لوکال disposable یا Docker استفاده کنید؛ این wrapper فقط Unix socket دارد.", file=sys.stderr)
        return 2
    server = None
    try:
        with tempfile.TemporaryDirectory(prefix="nora-local-postgres-qa-") as temp:
            server = pgserver.get_server(Path(temp), cleanup_mode="stop")
            url = make_url(server.get_uri(database="postgres")).set(drivername="postgresql+psycopg")
            env = os.environ.copy()
            env["NORA_TEST_POSTGRES_URL"] = url.render_as_string(hide_password=False)
            print("آزمون PostgreSQL موقت با Unix socket؛ schemaهای rollback-only، بدون دیتابیس اصلی.", flush=True)
            script = Path(__file__).with_name("run-python-tests.py")
            try:
                return subprocess.run([sys.executable, str(script), "backend"], env=env, check=False).returncode
            finally:
                # pgserver 0.1.4 exposes atexit cleanup rather than a context manager.
                # Stop the test-owned server before TemporaryDirectory removes PGDATA.
                server._cleanup()
                server = None
    finally:
        if server is not None:
            server._cleanup()


if __name__ == "__main__":
    raise SystemExit(main())

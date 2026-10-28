#!/usr/bin/env python3
"""Test-environment launcher: the real phone-OTP login path with a *fake* SMS channel.

Why: the regular-user login (login.html → /api/auth/phone-otp/request → /verify) can only be
exercised in a browser if a code reaches the tester. Production delivers it through Bale Safir
(``backend.otp.send_safir_otp``). This launcher starts the same ``backend.app`` with that single
function replaced by a sink that appends the code to a local file, so the whole path — captcha,
throttles, challenge rows, hashing, session cookie, account creation — runs unchanged and no
message ever leaves the machine. Nothing in ``backend/`` changes; production never imports this.

Guards (all fail closed):
  * ``NORA_OTP_SINK_FILE`` must be set — the only place codes go; keep it outside Git.
  * ``SAFIR_API_KEY`` must be a *placeholder* prefixed ``test-`` (``SAFIR_BOT_ID`` any decimal id);
    a real-looking key is refused so this can't be pointed at a production configuration by accident.
  * ``NORA_DATABASE_URL`` must point at a test database (name/path containing ``test`` or ``preview``).

Usage (from ``nora-ui``):
  set -a && . <preview.env> && set +a
  SAFIR_API_KEY=test-safir-key-not-real-0000000000 SAFIR_BOT_ID=100000001 \\
  NORA_OTP_PEPPER=<≥32 random chars, test only> NORA_OTP_SINK_FILE=/tmp/nora-otp-sink.jsonl \\
  python tools/otp-sink-preview.py --port 8004
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _refuse(message: str) -> None:
    print(f"otp-sink-preview: refused — {message}", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8004)
    args = parser.parse_args()

    sink = os.environ.get("NORA_OTP_SINK_FILE", "").strip()
    if not sink:
        _refuse("NORA_OTP_SINK_FILE is not set")
    if not os.environ.get("SAFIR_API_KEY", "").strip().startswith("test-"):
        _refuse("SAFIR_API_KEY must be a placeholder starting with 'test-' (never a real credential)")
    database_url = os.environ.get("NORA_DATABASE_URL", "").strip().lower()
    if not database_url or not any(marker in database_url for marker in ("test", "preview", "memory")):
        _refuse("NORA_DATABASE_URL must name a test/preview database")

    sink_path = Path(sink)
    sink_path.parent.mkdir(parents=True, exist_ok=True)

    import backend.app as app_module  # noqa: E402  (after sys.path)

    def sink_send(**kwargs) -> bool:
        # Same signature the app uses; the code never leaves this machine.
        record = {"at": time.time(), "phone": str(kwargs.get("phone", "")), "code": str(kwargs.get("code", ""))}
        with sink_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True

    app_module.send_safir_otp = sink_send  # type: ignore[assignment]
    print(
        "otp-sink-preview: TEST MODE — OTP codes are written to "
        f"{sink_path} and NO SMS/Bale message is sent", file=sys.stderr,
    )

    import uvicorn  # noqa: E402

    uvicorn.run(app_module.app, host=args.host, port=args.port, proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()

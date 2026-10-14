"""Portable Nora test entry point with isolated backend/bot import namespaces."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

UI_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = UI_ROOT.parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="اجرای جداگانهٔ تست‌های Python نورا؛ بدون پیام یا پرداخت واقعی")
    parser.add_argument("component", choices=["backend", "bot", "types", "storage", "all"])
    args = parser.parse_args()
    env = os.environ.copy()
    # No real delivery key is required or inherited by the local regression run.
    for name in ["BOT_TOKEN", "NORA_BALE_BOT_TOKEN", "NORA_BOT_SERVICE_TOKEN", "SAFIR_API_KEY",
                 "NORA_FORM_PAYMENT_BOT_TOKEN", "NORA_FORM_PAYMENT_PROVIDER_TOKEN",
                 "NORA_FORM_PAYMENT_WEBHOOK_SECRET", "NORA_SHARED_API_URL"]:
        env[name] = ""
    env["PYTHONPATH"] = os.pathsep.join([str(UI_ROOT), str(REPO_ROOT), str(REPO_ROOT / "nora_bot")])
    jobs = {
        "backend": (UI_ROOT, ["-m", "pytest", "-q", "backend/tests"]),
        "bot": (REPO_ROOT / "nora_bot", ["-m", "pytest", "-q", "tests"]),
        "types": (UI_ROOT, ["-m", "mypy", "--config-file", "backend/mypy.ini", "backend"]),
        "storage": (REPO_ROOT / "nora_bot", ["tests/test_storage_guard.py"]),
    }
    failed = 0
    for name in jobs if args.component == "all" else [args.component]:
        cwd, command = jobs[name]
        print(f"\n=== Nora {name} ===", flush=True)
        result = subprocess.run([sys.executable, *command], cwd=cwd, env=env, check=False)
        if result.returncode:
            failed += 1
            print(f"FAIL {name}: exit {result.returncode}", flush=True)
        else:
            print(f"PASS {name}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

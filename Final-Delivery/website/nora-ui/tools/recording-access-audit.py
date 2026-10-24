#!/usr/bin/env python3
"""Read-only integrity audit of the archive purchase chain (phase 9.5 §3).

    NORA_DATABASE_URL=... python tools/recording-access-audit.py [--json] [--fail-on error|warning]

Walks purchase forms → responses/payments → ``recording_orders`` → ``recording_access`` and
prints every inconsistency (ids only, no personal data).  It never writes to the database;
fixing is an operator decision made through the panel / existing endpoints.
Exit code: 0 clean, 2 when findings at or above ``--fail-on`` exist (default ``error``).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from backend import integrity  # noqa: E402

RANK = {"info": 0, "warning": 1, "error": 2}


def database_url() -> str:
    url = os.getenv("NORA_DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("NORA_DATABASE_URL is required (same value as the server)")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    parser.add_argument("--fail-on", choices=("info", "warning", "error"), default="error")
    args = parser.parse_args(argv)
    engine = create_engine(database_url(), pool_pre_ping=True)
    try:
        with Session(engine) as db:
            report = integrity.run(db, datetime.now(timezone.utc))
            db.rollback()  # belt and braces: nothing was written
    finally:
        engine.dispose()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"scanned: {report['scanned']}")
        print(f"severity: {report['severity']}")
        for code, count in report["counts"].items():
            print(f"  {integrity.SEVERITY[code]:7} {code}: {count}")
        if not report["findings"]:
            print("  clean — no inconsistencies")
    threshold = RANK[args.fail_on]
    hit = any(RANK[f["severity"]] >= threshold for f in report["findings"])
    return 2 if hit else 0


if __name__ == "__main__":
    raise SystemExit(main())

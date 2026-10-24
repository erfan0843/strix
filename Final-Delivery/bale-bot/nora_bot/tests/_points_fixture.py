"""کمک‌تست مشترک دفترکل امتیاز — فقط برای اسکریپت‌ها/تست‌های آفلاین.

به‌جای ``UPDATE users SET total_points=…`` (که نگهبان پایگاه آن را رد می‌کند)
موجودی آزمایشی را از همان مسیر رسمی (``points_ledger.post_points``) می‌سازد.
"""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def ensure_test_env() -> None:
    """متغیرهای محیطی حداقلی برای import ایمن ماژول‌های ربات (بدون شبکه)."""
    if os.environ.get("DB_PATH"):
        return
    tmp = tempfile.mkdtemp(prefix="nora_pl_")
    os.environ.update({
        "BOT_TOKEN": os.environ.get("BOT_TOKEN") or "1095412158:TEST_TOKEN_FOR_UNITTEST",
        "SUPER_ADMIN_ID": os.environ.get("SUPER_ADMIN_ID") or "100000001",
        "DB_PATH": str(Path(tmp) / "t.db"),
        "BACKUP_DIR": str(Path(tmp) / "backups"),
        "IMPORT_DIR": str(Path(tmp) / "imports"),
        "FILES_DIR": str(Path(tmp) / "files"),
        "PROFILES_DIR": str(Path(tmp) / "files/profiles"),
        "EVENTS_DIR": str(Path(tmp) / "files/events"),
        "LOG_DIR": str(Path(tmp) / "logs"),
    })


def set_balance(bale_user_id: int, value: int, *, reason: str = "fixture: موجودی آزمایشی") -> int:
    """موجودی کاربر آزمایشی را به ``value`` می‌رساند (ردیف manual_adjust با دلیل)."""
    import points_ledger as pl  # noqa: PLC0415
    from database import db_execute  # noqa: PLC0415

    row = db_execute("SELECT COALESCE(total_points,0) AS tp FROM users WHERE bale_user_id=?",
                     (int(bale_user_id),), fetch="one")
    if not row:
        raise RuntimeError("fixture: user missing")
    current = int(row["tp"])
    if current != 0 and pl.last_entry(int(bale_user_id)) is None:
        pl.post_opening_balance(int(bale_user_id), reason="fixture: افتتاحیهٔ آزمایشی")
    delta = int(value) - current
    if delta == 0:
        return current
    res = pl.post_points(int(bale_user_id), delta, entry_type="manual_adjust", source="admin_manual",
                         ref_key=f"manual:fixture-{uuid.uuid4()}", reason=reason,
                         actor_kind="admin", actor_id=int(os.environ.get("SUPER_ADMIN_ID") or 0) or None,
                         allow_negative=True)
    return res.balance_after

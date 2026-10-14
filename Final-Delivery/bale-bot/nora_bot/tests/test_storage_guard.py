"""اجرای ورودی ربات بدون API نباید پایگاه SQLite بسازد."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="nora-bot-storage-guard-") as temp:
        isolated_root = Path(temp) / "bot"
        isolated_root.mkdir()
        for source in ROOT.glob("*.py"):
            shutil.copy2(source, isolated_root / source.name)

        db_path = isolated_root / "nora.db"
        env = os.environ.copy()
        env["NORA_BOT_ALLOW_LEGACY_SQLITE"] = ""
        env.pop("DB_PATH", None)
        env.pop("FILES_DIR", None)
        env.pop("BACKUP_DIR", None)
        env.pop("LOG_DIR", None)
        env.pop("IMPORT_DIR", None)
        env.pop("PROFILES_DIR", None)
        env.pop("EVENTS_DIR", None)
        env.update({"BOT_TOKEN": "0:test", "SUPER_ADMIN_ID": "1", "PYTHONDONTWRITEBYTECODE": "1"})

        result = subprocess.run(
            [sys.executable, str(isolated_root / "main.py")],
            cwd=isolated_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 2, result.stdout + result.stderr
        assert "پایگاه جداگانه" in result.stdout, result.stdout
        assert not db_path.exists(), f"پایگاه SQLite ساخته شد: {db_path}"

    print("✅ main.py پیش از ساخت پایگاه SQLite متوقف می‌شود")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

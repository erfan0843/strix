"""قرارداد استقرار ربات: قالب‌های systemd و نمونهٔ محیط باید با رفتار واقعی کد یکی باشند.

این آزمون‌ها عمداً «متن» را با «رفتار» مقایسه می‌کنند، نه صرفاً وجود فایل را:
- نمونهٔ `bale-bot.env.example` باید نشانی‌ای بدهد که کلاینت واقعی می‌پذیرد.
- کد خروجِ عمدیِ گارد باید همان کدی باشد که unit از ری‌استارت بی‌پایان مستثنا می‌کند.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

BOT_ROOT = Path(__file__).resolve().parents[1]
DELIVERY_ROOT = Path(__file__).resolve().parents[3]
DEPLOYMENT_ROOT = DELIVERY_ROOT / "deployment"

if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

import config  # noqa: E402

GUARD_VARIABLE = "NORA_BOT_ALLOW_LEGACY_SQLITE"


def _env_sample_value(name: str) -> str:
    """آخرین مقدارِ فعالِ یک کلید در نمونهٔ محیط ربات."""
    text = (DEPLOYMENT_ROOT / "bale-bot.env.example").read_text(encoding="utf-8")
    values = [
        line.split("=", 1)[1].strip()
        for line in text.splitlines()
        if line.strip().startswith(name + "=")
    ]
    assert values, f"{name} در نمونهٔ محیط استقرار نیست"
    return values[-1]


def test_deployment_env_sample_passes_the_real_client_url_contract():
    """نمونهٔ استقرار نباید نشانی‌ای بدهد که shared_api رد می‌کند.

    رگرسیون واقعی: نمونه پیش‌تر `https://lifeline1.ir/api` داشت؛ کلاینت خودش
    `/api` را اضافه می‌کند و `_api_base` هر مسیری را رد می‌کند، پس ربات روی
    سرور با `shared_api_url_invalid` بالا نمی‌آمد.
    """
    sample = _env_sample_value("NORA_SHARED_API_URL")
    assert sample, "نمونهٔ استقرار باید یک نشانی نمونه بدهد"
    assert config.shared_api_url_error(sample) == "", (
        f"نمونهٔ استقرار {sample!r} را می‌دهد ولی کلاینت آن را رد می‌کند"
    )


def _env_example_paragraph(name: str) -> str:
    """پاراگرافِ (بلوکِ جداشده با خط خالی) نمونهٔ محیط که کلید در آن است."""
    text = (BOT_ROOT / ".env.example").read_text(encoding="utf-8")
    for block in text.split("\n\n"):
        if any(line.strip().startswith(name + "=") for line in block.splitlines()):
            return block
    raise AssertionError(f"پاراگراف {name} در .env.example نیست")


def test_bot_env_example_documents_that_the_base_is_origin_only():
    """نمونهٔ محیطِ خود ربات هم باید همین قرارداد را روشن بگوید."""
    block = _env_example_paragraph("NORA_SHARED_API_URL")
    assert "/api" in block, "باید صریح بگوید مسیر /api را ربات اضافه می‌کند"


def test_check_config_rejects_base_url_with_a_path(monkeypatch):
    """پیکربندی نادرست باید در همان بررسیِ راه‌اندازی گرفته شود، نه وسط کار."""
    monkeypatch.setattr(config, "BOT_TOKEN", "123456789:test")
    monkeypatch.setattr(config, "SUPER_ADMIN_ID", "1")
    monkeypatch.setattr(config, "SHARED_API_TOKEN", "t" * 48)
    monkeypatch.setattr(config, "NORA_WEBAPP_URL_INVALID", False)

    monkeypatch.setattr(config, "SHARED_API_URL", "https://nora.example")
    assert config.check_config() == []

    monkeypatch.setattr(config, "SHARED_API_URL", "https://nora.example/api")
    errors = config.check_config()
    assert len(errors) == 1
    assert "/api" in errors[0]

    monkeypatch.setattr(config, "SHARED_API_URL", "http://nora.example")
    assert "NORA_SHARED_API_URL" in config.check_config()[0]


def test_shared_api_and_config_agree_on_the_same_url_rules():
    """یک قاعده، دو مصرف‌کننده؛ نباید از هم دور بیفتند."""
    for value, expected in [
        ("https://nora.example", ""),
        ("https://nora.example/", ""),
        ("http://127.0.0.1:8000", ""),
        ("https://nora.example/api", "shared_api_url_invalid"),
        ("http://nora.example", "shared_api_url_invalid"),
        ("https://user:pw@nora.example", "shared_api_url_invalid"),
        ("https://nora.example?x=1", "shared_api_url_invalid"),
        ("", "shared_api_url_missing"),
    ]:
        assert config.shared_api_url_error(value) == expected, value


def _guard_exit_code() -> int:
    """کد خروجی که main.py در حالت گارد برمی‌گرداند."""
    source = (BOT_ROOT / "main.py").read_text(encoding="utf-8")
    guard = re.search(
        rf'if os\.getenv\("{GUARD_VARIABLE}"\) != "1":(.{{0,600}}?)return (\d+)',
        source,
        re.S,
    )
    assert guard, "گارد اجرای legacy در main.py پیدا نشد"
    return int(guard.group(2))


def test_systemd_unit_prevents_restart_loop_on_the_intentional_exit_code():
    """کد خروج عمدی گارد نباید systemd را به ری‌استارت بی‌پایان بکشاند.

    unit با `Restart=on-failure` هر کد غیرصفر را شکست می‌شمارد؛ پس کد خروج
    گارد باید صریحاً از ری‌استارت مستثنا شود.
    """
    code = _guard_exit_code()
    assert code != 0, "گارد باید با کد غیرصفر متوقف شود"
    unit = (DEPLOYMENT_ROOT / "nora-bot.service").read_text(encoding="utf-8")
    prevented = re.search(r"^RestartPreventExitStatus=(.+)$", unit, re.M)
    assert prevented, "unit باید RestartPreventExitStatus داشته باشد"
    assert str(code) in prevented.group(1).split()
    assert re.search(r"^Restart=on-failure$", unit, re.M)


def test_docs_tell_the_operator_about_the_guard_and_the_override():
    """راهنما نباید رفتار پیش‌فرض را پنهان کند."""
    docs = (DELIVERY_ROOT / "docs" / "02-استقرار-روی-دامنه.fa.md").read_text(encoding="utf-8")
    for expected in [
        GUARD_VARIABLE,                 # نام متغیر گارد
        "RestartPreventExitStatus",     # چرا ری‌استارت بی‌پایان نمی‌شود
        "systemctl status nora-bot",    # بررسی وضعیت سرویس
        "journalctl -u nora-bot",       # بررسی خطاهای راه‌اندازی
        "pg_dump",                      # پشتیبان پایگاه وب
        "sqlite3",                      # پشتیبان و بازیابی SQLite ربات
        "shared_api_url_invalid",       # قرارداد نشانی پایه API
    ]:
        assert expected in docs, expected


def _isolated_bot_dir(temp: Path) -> Path:
    isolated = temp / "bot"
    isolated.mkdir()
    for source in BOT_ROOT.glob("*.py"):
        shutil.copy2(source, isolated / source.name)
    return isolated


def _run_bot(isolated: Path, extra_env: dict[str, str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    for name in ["DB_PATH", "FILES_DIR", "BACKUP_DIR", "LOG_DIR", "IMPORT_DIR",
                 "PROFILES_DIR", "EVENTS_DIR"]:
        env.pop(name, None)
    env.update({
        "BOT_TOKEN": "",
        "SUPER_ADMIN_ID": "",
        "PYTHONDONTWRITEBYTECODE": "1",
        "NORA_SHARED_API_URL": "",
    })
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(isolated / "main.py")],
        cwd=isolated, env=env, capture_output=True, text=True, check=False,
    )


def test_enabling_the_override_opens_the_local_sqlite_as_documented():
    """روشن‌کردن صریح حالت legacy یعنی ربات SQLite محلی را باز و می‌سازد.

    ماژول‌های قدیمی ربات هنگام import پایگاه را باز می‌کنند؛ پس این رفتار
    عمدی و بخشی از «پذیرش جدایی داده‌ها» است و مستند استقرار باید آن را
    بگوید. آزمون آن را ثابت نگه می‌دارد تا تصادفی نشود.
    """
    with tempfile.TemporaryDirectory(prefix="nora-bot-contract-") as temp:
        isolated = _isolated_bot_dir(Path(temp))
        db_path = isolated / "nora.db"
        assert not db_path.exists()

        _run_bot(isolated, {GUARD_VARIABLE: "1"})
        assert db_path.exists(), "در حالت legacy، ربات باید پایگاه محلی را باز کند"

        # و مستندات باید همین جدایی داده را صریح گفته باشند.
        docs = (DELIVERY_ROOT / "docs" / "02-استقرار-روی-دامنه.fa.md").read_text(encoding="utf-8")
        assert "پذیرش جدایی داده‌ها" in docs
        assert "پشتیبان‌گیری باید" in docs


def test_guard_stops_before_sqlite_and_the_override_is_explicit():
    """پیش‌فرض امن می‌ماند و فقط با تنظیم صریح متغیر، گارد رد می‌شود."""
    code = _guard_exit_code()
    with tempfile.TemporaryDirectory(prefix="nora-bot-contract-") as temp:
        isolated = _isolated_bot_dir(Path(temp))
        db_path = isolated / "nora.db"

        stopped = _run_bot(isolated, {GUARD_VARIABLE: ""})
        assert stopped.returncode == code, stopped.stdout + stopped.stderr
        assert not db_path.exists(), "گارد باید پیش از ساخت SQLite متوقف شود"

        # با تنظیم صریح، گارد دیگر متوقف نمی‌کند؛ توقف‌های بعدی (پیکربندی ناقص)
        # نباید کد خروجِ عمدی گارد را بدهند.
        allowed = _run_bot(isolated, {GUARD_VARIABLE: "1"})
        assert allowed.returncode != code, allowed.stdout + allowed.stderr
        assert "پایگاه جداگانه" not in allowed.stdout


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

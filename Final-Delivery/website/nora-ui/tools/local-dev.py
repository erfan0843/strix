"""Safe, developer-only Nora startup; no production DB or external providers.

Run from any directory: python docs/fa/nora-ui/tools/local-dev.py init|migrate|serve|check
Private state stays under UI_ROOT/.local and .env.local. Nothing is seeded unless
using the separately labelled browser fixture server.
"""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import sys

UI_ROOT = Path(__file__).resolve().parents[1]
STATE_ROOT = UI_ROOT / ".local"
ENV_FILE = UI_ROOT / ".env.local"
EXTERNAL_KEYS = (
    "NORA_BALE_BOT_TOKEN", "NORA_BALE_BOT_USERNAME", "NORA_BOT_SERVICE_TOKEN",
    "NORA_OWNER_BALE_USER_ID", "NORA_FORM_PAYMENT_BOT_TOKEN",
    "NORA_FORM_PAYMENT_PROVIDER_TOKEN", "NORA_FORM_PAYMENT_WEBHOOK_SECRET",
    "NORA_FORM_PAYMENT_WEBHOOK_URL", "SAFIR_API_KEY", "SAFIR_BOT_ID",
)
# Local-only random secret for captcha/OTP HMAC. It is generated here, never copied from a provider.
LOCAL_SECRET_KEYS = ("NORA_OTP_PEPPER",)


class LocalSetupError(ValueError):
    """Static, safe-to-display setup guidance without an environment value."""


def _ensure_local_secrets(values: dict) -> None:
    """Fill empty local-only secrets with a random value stored in the private .env.local."""
    import re
    import secrets

    missing = [name for name in LOCAL_SECRET_KEYS if not values.get(name)]
    if not missing:
        return
    text = ENV_FILE.read_text(encoding="utf-8")
    for name in missing:
        value = secrets.token_urlsafe(32)
        values[name] = value
        pattern = rf"^{name}=.*$"
        line = f'{name}="{value}"'
        if re.search(pattern, text, flags=re.M):
            text = re.sub(pattern, line, text, count=1, flags=re.M)
        else:
            text = text.rstrip("\n") + "\n" + line + "\n"
    ENV_FILE.write_text(text, encoding="utf-8")


def prepare_environment() -> Path:
    from dotenv import dotenv_values
    from sqlalchemy.engine import make_url

    if not ENV_FILE.is_file():
        raise LocalSetupError("تنظیم محلی وجود ندارد؛ ابتدا فرمان init را اجرا کنید.")
    values = dotenv_values(ENV_FILE)
    _ensure_local_secrets(values)
    if any(values.get(name) for name in EXTERNAL_KEYS):
        raise LocalSetupError("این launcher فقط برای لوکال است؛ کلید سرویس خارجی را از .env.local بردارید.")
    url = make_url(values.get("NORA_DATABASE_URL") or "")
    if url.drivername != "sqlite+pysqlite" or not url.database:
        raise LocalSetupError("launcher محلی فقط SQLite داخل پوشهٔ .local همین رابط را می‌پذیرد.")
    database = Path(url.database).resolve()
    if not database.is_relative_to(STATE_ROOT.resolve()):
        raise LocalSetupError("مسیر دیتابیس خارج از پوشهٔ .local است؛ هیچ migration اجرا نشد.")
    # Explicitly blank provider configuration inherited from a shell/IDE as well.
    for name in EXTERNAL_KEYS:
        os.environ[name] = ""
    for name, value in values.items():
        if value is not None:
            os.environ[name] = value
    # Localhost HTTP must work for cookies; never publish a fabricated SEO origin.
    os.environ["NORA_COOKIE_SECURE"] = "false"
    os.environ["NORA_PUBLIC_BASE_URL"] = ""
    for name in tuple(os.environ):
        if name.startswith("NORA_SEO_BUSINESS_"):
            os.environ[name] = ""
    if str(UI_ROOT) not in sys.path:
        sys.path.insert(0, str(UI_ROOT))
    return database


def migrate() -> None:
    database = prepare_environment()
    from alembic import command
    from alembic.config import Config
    command.upgrade(Config(str(UI_ROOT / "backend" / "alembic.ini")), "head")
    print(f"مهاجرت محلی کامل شد: {database.name}؛ هیچ دیتابیس خارجی استفاده نشد.")


def secrets_token() -> str:
    import secrets

    return secrets.token_urlsafe(32)


def initialize(with_owner: bool) -> None:
    if ENV_FILE.exists():
        raise LocalSetupError(".env.local از قبل وجود دارد؛ overwrite نمی‌شود. برای ادامه migrate یا serve را اجرا کنید.")
    database = STATE_ROOT / "nora-dev.sqlite3"
    if database.exists():
        raise LocalSetupError("فایل دیتابیس از قبل وجود دارد؛ دادهٔ موجود overwrite نمی‌شود.")
    if str(UI_ROOT) not in sys.path:
        sys.path.insert(0, str(UI_ROOT))
    password_hash = ""
    if with_owner:
        from backend.security import hash_password
        password = getpass.getpass("گذرواژهٔ مالک فقط برای توسعهٔ محلی (حداقل ۱۲ نویسه): ")
        confirm = getpass.getpass("تکرار گذرواژه: ")
        if password != confirm or len(password) < 12:
            raise LocalSetupError("گذرواژه‌ها یکسان نیستند یا کمتر از ۱۲ نویسه‌اند؛ فایلی نوشته نشد.")
        password_hash = hash_password(password)
    STATE_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    from sqlalchemy.engine import URL
    database_url = URL.create("sqlite+pysqlite", database=str(database.resolve())).render_as_string(hide_password=False)
    settings = {
        "NORA_DATABASE_URL": database_url,
        "NORA_OWNER_ID": "local-owner",
        "NORA_OWNER_USERNAME": "local-owner" if with_owner else "",
        "NORA_OWNER_PASSWORD_HASH": password_hash,
        "NORA_COOKIE_SECURE": "false",
        "NORA_PUBLIC_BASE_URL": "",
        **{name: "" for name in EXTERNAL_KEYS},
        **{name: secrets_token() for name in LOCAL_SECRET_KEYS},
    }
    content = "# Private local development only; do not commit or publish.\n"
    content += "\n".join(f'{name}="{value}"' for name, value in settings.items()) + "\n"
    descriptor = os.open(ENV_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(content)
    migrate()
    print(".env.local خصوصی ساخته شد؛ هیچ رمز یا hash در خروجی چاپ نمی‌شود.")
    print("اجرای بعدی: python docs/fa/nora-ui/tools/local-dev.py serve")
    if not with_owner:
        print("ورود مالک فعال نشده است؛ برای آزمون نقش‌ها از سرور fixture جدا استفاده کنید.")


def check() -> None:
    database = prepare_environment()
    if not database.is_file():
        raise LocalSetupError("فایل دیتابیس موجود نیست؛ فرمان migrate را اجرا کنید.")
    from sqlalchemy import create_engine, text
    engine = create_engine(os.environ["NORA_DATABASE_URL"])
    try:
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        print(f"Python {sys.version.split()[0]}؛ دیتابیس محلی موجود؛ revision: {revision}")
        print("ارائه‌دهندگان خارجی خاموش؛ cookie برای HTTP لوکال؛ SEO domain تنظیم نشده.")
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="راه‌اندازی امن نورا برای توسعهٔ محلی")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="ساخت تنظیم خصوصی و دیتابیس خالی، بدون overwrite")
    init.add_argument("--owner", action="store_true", help="دریافت گذرواژه با getpass، بدون چاپ یا نمونهٔ محرمانه")
    sub.add_parser("migrate", help="اجرای Alembic فقط روی دیتابیس محلی مجاز")
    sub.add_parser("check", help="بررسی تنظیم و revision؛ بدون چاپ secret")
    serve = sub.add_parser("serve", help="اجرای UI و API واقعی در یک فرایند")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "init":
            initialize(args.owner)
        elif args.command == "migrate":
            migrate()
        elif args.command == "check":
            check()
        else:
            check()
            import uvicorn
            uvicorn.run("backend.app:app", host=args.host, port=args.port, reload=args.reload,
                        app_dir=str(UI_ROOT), reload_dirs=[str(UI_ROOT)] if args.reload else None,
                        access_log=False)
    except LocalSetupError as error:
        print(str(error), file=sys.stderr)
        return 2
    except (ValueError, ImportError) as error:
        # No environment values or exception URL/driver credentials are echoed.
        print(f"خطای آماده‌سازی ({type(error).__name__}). تنظیم/پیش‌نیاز را طبق راهنمای لوکال بررسی کنید.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

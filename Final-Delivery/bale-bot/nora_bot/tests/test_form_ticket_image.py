"""Date/time formatting and raster output for shared-form ticket JPEGs."""
from __future__ import annotations

import sys
from pathlib import Path

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

import form_ticket_image as renderer  # noqa: E402


def test_ticket_date_uses_the_event_date_and_never_guesses_a_missing_year():
    assert renderer.event_date_parts("2026-11-13") == {
        "weekday": "جمعه",
        "day": "۲۲",
        "month_year": "آبان ۱۴۰۵",
    }
    assert renderer.event_date_parts("جمعه ۲۲ آبان ۱۴۰۵") == {
        "weekday": "جمعه",
        "day": "۲۲",
        "month_year": "آبان ۱۴۰۵",
    }
    assert renderer.event_date_parts("جمعه ۲۲ آبان") is None
    assert renderer.event_date_parts("۱۴۰۵/۰۸/۳۱") is None


def test_ticket_times_are_validated_and_persian_formatted():
    assert renderer.event_times("۱۶:۳۰ تا ۱۹:۰۰") == ["۱۶:۳۰", "۱۹:۰۰"]
    assert renderer.event_times("8:05") == ["۰۸:۰۵"]
    assert renderer.event_times("۲۴:۰۰ تا ۱۹:۷۰") == []


def test_shared_form_ticket_is_a_high_quality_jpeg(tmp_path):
    from PIL import Image  # noqa: PLC0415

    output = tmp_path / "ticket.jpg"
    result = renderer.build_shared_form_ticket_image(
        {
            "event_title": "کارگاه فرهنگ ایرانی",
            "name": "لیلا رضایی",
            "ticket_type_name": "ورودی ویژه",
            "serial": "NORA-123E4567E89B12D3A456",
            "qr_data": "https://ble.ir/nora?start=ftv_123e4567-e89b-12d3-a456-426614174001",
            "event_date": "2026-11-13",
            "event_time": "۱۶:۳۰ تا ۱۹:۰۰",
        },
        out_path=output,
    )
    assert result == str(output)
    with Image.open(output) as image:
        assert image.format == "JPEG"
        assert image.size == (1200, 656)
    assert output.stat().st_size < 1_000_000


def test_explicit_organization_is_used_without_reading_bot_settings(tmp_path, monkeypatch):
    """The web service passes its own organization name; the renderer must not
    import the bot's config/database (which would open the bot SQLite file and
    load the bot .env inside the web process)."""
    import builtins  # noqa: PLC0415

    real_import = builtins.__import__
    touched: list[str] = []

    def guarded_import(name, *args, **kwargs):
        if name in {"config", "database"}:
            touched.append(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    renderer._font.cache_clear()
    captured: list[str] = []
    original_draw_brand = renderer._draw_brand

    def spy_draw_brand(image, draw, organization, month_year):
        captured.append(organization)
        return original_draw_brand(image, draw, organization, month_year)

    monkeypatch.setattr(renderer, "_draw_brand", spy_draw_brand)
    output = tmp_path / "ticket.jpg"
    result = renderer.build_shared_form_ticket_image(
        {
            "event_title": "کارگاه فرهنگ ایرانی",
            "name": "لیلا رضایی",
            "serial": "NORA-123E4567E89B12D3A456",
            "qr_data": "https://ble.ir/nora?start=ftv_123e4567-e89b-12d3-a456-426614174001",
            "event_date": "2026-11-13",
            "organization": "  نام سازمان وب  ",
        },
        out_path=output,
    )
    assert result == str(output)
    assert captured == ["نام سازمان وب"]
    assert "database" not in touched

"""Dedicated JPEG renderer for public shared-form registration tickets.

This deliberately does not read legacy SQLite ticket settings or response
records. It consumes only the small, validated payload returned by the shared
forms API. The generic configurable renderer in ``ticket.py`` remains intact.
"""
from __future__ import annotations

import logging
import re
import tempfile
import unicodedata
import uuid
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any


log = logging.getLogger(__name__)
WIDTH, HEIGHT = 600, 328
OUTPUT_SIZE = (WIDTH * 2, HEIGHT * 2)
ACCENT = (228, 193, 122, 255)
INK = (255, 248, 233, 255)
MUTED = (239, 235, 223, 220)
_MONTHS = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)
_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _safe_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    clean = "".join(
        char for char in value
        if char in {"\u200c", "\u200d"} or unicodedata.category(char) not in {"Cc", "Cs"}
    )
    return " ".join(clean.split())[:limit]


def _ascii_digits(value: str) -> str:
    return value.translate(_FA_TO_EN).replace("ي", "ی").replace("ك", "ک")


def event_date_parts(value: Any) -> dict[str, str] | None:
    """Parse a complete Jalali/Gregorian event date; never invent a year."""
    raw = _safe_text(value, 120)
    if not raw:
        return None
    import jalali  # noqa: PLC0415

    normalized = _ascii_digits(raw)
    parsed = jalali.parse(normalized)
    if parsed:
        jy, jm, jd = parsed[:3]
    else:
        months = "|".join(re.escape(month) for month in sorted(_MONTHS, key=len, reverse=True))
        match = re.search(rf"(?<!\d)(\d{{1,2}})\s+({months})\s+(\d{{4}})(?!\d)", normalized)
        if match:
            jd, month_name, jy = int(match.group(1)), match.group(2), int(match.group(3))
            jm = _MONTHS.index(month_name) + 1
        else:
            reverse = re.search(rf"(?<!\d)(\d{{4}})\s+({months})\s+(\d{{1,2}})(?!\d)", normalized)
            if not reverse:
                return None
            jy, month_name, jd = int(reverse.group(1)), reverse.group(2), int(reverse.group(3))
            jm = _MONTHS.index(month_name) + 1

    jalali_date = f"{jy:04d}/{jm:02d}/{jd:02d}"
    if not jalali.valid(jalali_date):
        return None
    try:
        gy, gm, gd = jalali.j2g(jy, jm, jd)
        weekday = jalali.WEEKDAYS[(date(gy, gm, gd).weekday() + 2) % 7]
    except (ValueError, TypeError):
        return None
    return {
        "weekday": weekday,
        "day": jalali.fa(str(jd)),
        "month_year": f"{_MONTHS[jm - 1]} {jalali.fa(str(jy))}",
    }


def event_times(value: Any) -> list[str]:
    """Return up to two valid 24-hour times in Persian numerals."""
    raw = _ascii_digits(_safe_text(value, 120))
    if not raw:
        return []
    import jalali  # noqa: PLC0415

    result: list[str] = []
    for match in re.finditer(r"(?<!\d)(\d{1,2})\s*[:：](\d{2})(?!\d)", raw):
        hour, minute = int(match.group(1)), int(match.group(2))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            continue
        formatted = jalali.fa(f"{hour:02d}:{minute:02d}")
        if formatted not in result:
            result.append(formatted)
        if len(result) == 2:
            break
    return result


def _raqm_available() -> bool:
    try:
        from PIL import features  # noqa: PLC0415

        return bool(features.check("raqm"))
    except Exception:
        return False


@lru_cache(maxsize=48)
def _font(size: int, bold: bool = False):
    from PIL import ImageFont  # noqa: PLC0415

    paths: list[Path] = []
    try:
        from config import FILES_DIR  # noqa: PLC0415

        font_dir = Path(FILES_DIR) / "fonts"
        if bold:
            paths.extend([font_dir / "Vazirmatn-Bold.ttf", font_dir / "Vazir-Bold.ttf"])
        paths.extend([font_dir / "Vazirmatn-Regular.ttf", font_dir / "Vazirmatn-Medium.ttf", font_dir / "Vazir.ttf"])
    except Exception:
        pass
    bundled = Path(__file__).resolve().parent / "files" / "fonts"
    if bold:
        paths.extend([bundled / "Vazirmatn-Bold.ttf", bundled / "Vazir-Bold.ttf"])
    paths.extend([bundled / "Vazirmatn-Regular.ttf", bundled / "Vazirmatn-Medium.ttf", bundled / "Vazir.ttf"])
    try:
        layout = ImageFont.Layout.RAQM if _raqm_available() else ImageFont.Layout.BASIC
    except Exception:
        layout = None
    for path in paths:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), max(1, int(size)), layout_engine=layout)
            except Exception:
                try:
                    return ImageFont.truetype(str(path), max(1, int(size)))
                except Exception:
                    continue
    try:
        return ImageFont.load_default(size=max(1, int(size)))
    except TypeError:
        return ImageFont.load_default()


def _display_text(text: str, rtl: bool) -> str:
    if not rtl or _raqm_available():
        return text
    try:
        import arabic_reshaper  # noqa: PLC0415
        from bidi.algorithm import get_display  # noqa: PLC0415

        return get_display(arabic_reshaper.reshape(text))
    except ImportError:
        return text


def _text_kwargs(rtl: bool) -> dict[str, str]:
    if _raqm_available():
        return {"direction": "rtl" if rtl else "ltr", "language": "fa" if rtl else "en"}
    return {}


def _measure(draw, text: str, font, *, rtl: bool = True) -> tuple[int, int, tuple[int, int, int, int]]:
    shown = _display_text(text, rtl)
    try:
        bounds = draw.textbbox((0, 0), shown, font=font, **_text_kwargs(rtl))
    except Exception:
        bounds = draw.textbbox((0, 0), shown, font=font)
    return max(0, bounds[2] - bounds[0]), max(0, bounds[3] - bounds[1]), bounds


def _draw_text(draw, text: str, x: float, y: float, font, fill, *, align: str = "right", rtl: bool = True) -> None:
    if not text:
        return
    shown = _display_text(text, rtl)
    width, _height, bounds = _measure(draw, text, font, rtl=rtl)
    left = x - width if align == "right" else x - width / 2 if align == "center" else x
    point = (left - bounds[0], y - bounds[1])
    try:
        draw.text(point, shown, font=font, fill=fill, **_text_kwargs(rtl))
    except Exception:
        draw.text(point, shown, font=font, fill=fill)


def _fit_one_line(draw, text: str, maximum: int, start: int, minimum: int, *, bold: bool = False, rtl: bool = True):
    for size in range(start, minimum - 1, -1):
        font = _font(size, bold)
        if _measure(draw, text, font, rtl=rtl)[0] <= maximum:
            return text, font
    font = _font(minimum, bold)
    shortened = text
    while shortened and _measure(draw, shortened + "…", font, rtl=rtl)[0] > maximum:
        shortened = shortened[:-1]
    return (shortened + "…") if shortened != text else text, font


def _wrap_lines(draw, text: str, font, maximum: int, max_lines: int = 2) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or _measure(draw, candidate, font)[0] <= maximum:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) <= max_lines:
        return lines
    lines = lines[:max_lines]
    tail = lines[-1]
    while tail and _measure(draw, tail + "…", font)[0] > maximum:
        tail = tail[:-1]
    lines[-1] = tail.rstrip() + "…"
    return lines


def _draw_sparkle(draw, cx: int, cy: int, radius: int, color) -> None:
    draw.polygon(
        [(cx, cy - radius), (cx + radius // 3, cy - radius // 3),
         (cx + radius, cy), (cx + radius // 3, cy + radius // 3),
         (cx, cy + radius), (cx - radius // 3, cy + radius // 3),
         (cx - radius, cy), (cx - radius // 3, cy - radius // 3)],
        fill=color,
    )
    draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=(255, 243, 212, 255))


def _diamond(draw, cx: int, cy: int, rx: int, ry: int, fill, outline=None, width: int = 1) -> None:
    points = [(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)]
    draw.polygon(points, fill=fill)
    if outline:
        draw.line(points + [points[0]], fill=outline, width=width, joint="curve")


def _carpet_background():
    from PIL import Image, ImageDraw  # noqa: PLC0415

    image = Image.new("RGBA", (WIDTH, HEIGHT), (16, 25, 42, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    for y in range(HEIGHT):
        t = y / max(1, HEIGHT - 1)
        color = (int(22 - 8 * t), int(33 - 10 * t), int(52 - 8 * t), 255)
        draw.line((0, y, WIDTH, y), fill=color)

    art = Image.new("RGBA", (232, 308), (102, 23, 49, 255))
    art_draw = ImageDraw.Draw(art, "RGBA")
    for y in range(308):
        t = y / 307
        color = (int(122 - 48 * t), int(30 - 9 * t), int(59 - 15 * t), 255)
        art_draw.line((0, y, 231, y), fill=color)
    art_draw.rounded_rectangle((3, 3, 228, 304), radius=15, outline=(235, 199, 126, 215), width=2)
    art_draw.rounded_rectangle((10, 10, 221, 297), radius=12, outline=(216, 168, 96, 175), width=1)

    # A restrained repeat around the medallion, kept dark enough behind text/QR.
    for x in (20, 54, 88, 122, 156, 190, 212):
        for y in (24, 58, 92, 126, 160, 194, 228, 262, 286):
            _diamond(art_draw, x, y, 6, 9, (36, 55, 78, 210), (224, 191, 120, 205), 1)
            art_draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=(245, 218, 159, 230))

    # Persian-carpet style central toranj.
    _diamond(art_draw, 116, 154, 79, 104, (25, 49, 75, 240), (237, 203, 132, 255), 4)
    _diamond(art_draw, 116, 154, 64, 86, (139, 40, 62, 245), (223, 181, 111, 255), 3)
    _diamond(art_draw, 116, 154, 48, 68, (202, 158, 82, 255), (245, 222, 161, 255), 2)
    _diamond(art_draw, 116, 154, 34, 50, (35, 62, 89, 255), (231, 197, 129, 255), 2)
    _diamond(art_draw, 116, 154, 20, 31, (223, 191, 121, 255), (249, 229, 176, 255), 1)
    art_draw.ellipse((107, 145, 125, 163), fill=(133, 38, 58, 255), outline=(255, 225, 154, 255), width=2)
    for angle_points in (
        (116, 116), (116, 192), (78, 154), (154, 154),
        (89, 127), (143, 127), (89, 181), (143, 181),
    ):
        art_draw.ellipse((angle_points[0] - 3, angle_points[1] - 3,
                          angle_points[0] + 3, angle_points[1] + 3), fill=(245, 213, 139, 255))

    mask = Image.new("L", art.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 231, 307), radius=17, fill=255)
    image.paste(art, (10, 10), mask)

    # Deep glass-dark gradient toward the information side, just like the gallery.
    shade = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shade_draw = ImageDraw.Draw(shade, "RGBA")
    for x in range(170, WIDTH):
        t = (x - 170) / (WIDTH - 170)
        alpha = int(28 + 218 * (t ** 1.45))
        shade_draw.line((x, 0, x, HEIGHT), fill=(9, 17, 31, alpha))
    for y in range(230, HEIGHT):
        t = (y - 230) / max(1, HEIGHT - 230)
        shade_draw.line((0, y, WIDTH, y), fill=(5, 10, 18, int(10 + 65 * t)))
    image = Image.alpha_composite(image, shade)
    ImageDraw.Draw(image, "RGBA").rounded_rectangle(
        (1, 1, WIDTH - 2, HEIGHT - 2), radius=24,
        outline=(255, 255, 255, 150), width=1,
    )
    return image


def _glass(image, box: tuple[int, int, int, int], radius: int = 14, fill_alpha: int = 37) -> None:
    from PIL import Image, ImageDraw  # noqa: PLC0415

    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    x0, y0, x1, y1 = box
    draw.rounded_rectangle((x0 + 1, y0 + 3, x1 + 1, y1 + 3), radius=radius, fill=(0, 0, 0, 34))
    draw.rounded_rectangle(box, radius=radius, fill=(255, 255, 255, fill_alpha), outline=(255, 255, 255, 150), width=1)
    draw.line((x0 + radius, y0 + 1, x1 - radius, y0 + 1), fill=(255, 255, 255, 105), width=1)
    image.alpha_composite(layer)


def _draw_brand(image, draw, organization: str, month_year: str) -> None:
    from PIL import Image, ImageDraw  # noqa: PLC0415

    # Brand mark on the right, institution name and the dynamic event month/year beside it.
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay = ImageDraw.Draw(layer, "RGBA")
    icon_box = (552, 15, 582, 45)
    overlay.rounded_rectangle(icon_box, radius=10, fill=(255, 255, 255, 37), outline=(ACCENT[0], ACCENT[1], ACCENT[2], 195), width=1)
    image.alpha_composite(layer)
    _draw_sparkle(draw, 567, 30, 9, ACCENT)

    text_right = 542
    org_max = 190 if month_year else 310
    org, org_font = _fit_one_line(draw, organization, org_max, 11, 8, bold=True)
    org_width = _measure(draw, org, org_font)[0]
    org_left = text_right - org_width
    _draw_text(draw, org, text_right, 21, org_font, INK, align="right")
    if month_year:
        badge, badge_font = _fit_one_line(draw, month_year, 78, 8, 7, bold=True)
        badge_width = min(88, _measure(draw, badge, badge_font)[0] + 14)
        bx1 = org_left - 7
        bx0 = bx1 - badge_width
        badge_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        badge_draw = ImageDraw.Draw(badge_layer, "RGBA")
        badge_draw.rounded_rectangle((bx0, 17, bx1, 39), radius=8,
                                     fill=(255, 255, 255, 32), outline=(255, 255, 255, 84), width=1)
        image.alpha_composite(badge_layer)
        _draw_text(draw, badge, (bx0 + bx1) / 2, 23, badge_font, ACCENT, align="center")


def _draw_schedule(image, draw, date_parts: dict[str, str] | None, times: list[str]) -> None:
    if not date_parts and not times:
        return
    y0, y1 = 174, 242
    if date_parts and times:
        date_box = (434, y0, 582, y1)
        time_box = (230, y0, 425, y1)
    else:
        full_box = (230, y0, 582, y1)
        date_box = full_box if date_parts else None
        time_box = full_box if times else None

    if date_box:
        _glass(image, date_box)
        x0, _top, x1, _bottom = date_box
        if date_parts and times:
            day_box = (x0 + 11, 190, x0 + 46, 225)
            draw.rounded_rectangle(day_box, radius=9, fill=ACCENT)
            day_text, day_font = _fit_one_line(draw, date_parts["day"], 31, 19, 15, bold=True)
            _draw_text(draw, day_text, (day_box[0] + day_box[2]) / 2, 197, day_font,
                       (32, 33, 39, 255), align="center")
            divider_x = x0 + 56
            draw.line((divider_x, 188, divider_x, 228), fill=(255, 255, 255, 95), width=1)
            weekday, weekday_font = _fit_one_line(draw, date_parts["weekday"], x1 - divider_x - 9, 12, 9, bold=True)
            _draw_text(draw, weekday, x1 - 10, 199, weekday_font, ACCENT, align="right")
        else:
            day_box = (x0 + 20, 190, x0 + 58, 228)
            draw.rounded_rectangle(day_box, radius=10, fill=ACCENT)
            day_text, day_font = _fit_one_line(draw, date_parts["day"], 34, 21, 16, bold=True)
            _draw_text(draw, day_text, (day_box[0] + day_box[2]) / 2, 197, day_font,
                       (32, 33, 39, 255), align="center")
            weekday, weekday_font = _fit_one_line(draw, date_parts["weekday"], x1 - x0 - 94, 14, 10, bold=True)
            _draw_text(draw, weekday, x0 + 78, 201, weekday_font, ACCENT, align="left")

    if time_box:
        _glass(image, time_box)
        x0, _top, x1, _bottom = time_box
        label, label_font = _fit_one_line(draw, "ساعت", 44, 9, 8)
        _draw_text(draw, label, x1 - 12, 181, label_font, MUTED, align="right")
        if len(times) >= 2:
            _draw_text(draw, times[0], x1 - 36, 207, _font(13, True), INK, align="center", rtl=False)
            _draw_text(draw, times[1], x0 + 36, 207, _font(13, True), INK, align="center", rtl=False)
            rail_left, rail_right = x0 + 67, x1 - 67
            draw.line((rail_left, 216, rail_right, 216), fill=(255, 255, 255, 135), width=1)
            draw.ellipse((rail_left - 2, 213, rail_left + 4, 219), outline=ACCENT, width=1)
            draw.ellipse((rail_right - 4, 213, rail_right + 2, 219), outline=ACCENT, width=1)
        else:
            _draw_text(draw, times[0], (x0 + x1) / 2, 204, _font(14, True), INK, align="center", rtl=False)


def _make_qr(payload: str):
    import qrcode  # noqa: PLC0415
    from qrcode.constants import ERROR_CORRECT_Q  # noqa: PLC0415

    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_Q, box_size=8, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.make_image(fill_color="#10131a", back_color="#ffffff").convert("RGB")


def _draw_qr_panel(image, draw, payload: str, serial: str) -> None:
    from PIL import Image  # noqa: PLC0415

    box = (15, 161, 131, 315)
    _glass(image, box, radius=18, fill_alpha=174)
    plate = (29, 172, 117, 260)
    draw.rounded_rectangle(plate, radius=10, fill=(255, 255, 255, 250), outline=(255, 255, 255, 255), width=1)
    qr = _make_qr(payload)
    qr = qr.resize((82, 82), Image.Resampling.NEAREST)
    image.alpha_composite(qr.convert("RGBA"), (32, 175))
    safe_serial = _safe_text(serial, 40)
    code, font = _fit_one_line(draw, safe_serial, 98, 7, 5, bold=True, rtl=False)
    _draw_text(draw, code, 73, 269, font, (24, 36, 58, 255), align="center", rtl=False)


def _font_paths_for_org() -> str:
    try:
        from config import org_name  # noqa: PLC0415

        name = org_name()
        if isinstance(name, str) and name.strip():
            return _safe_text(name, 80)
    except Exception:
        pass
    return "مؤسسهٔ خط‌زندگی"


def _output_path(out_path: str | Path | None) -> Path:
    if out_path:
        return Path(out_path)
    try:
        from config import FILES_DIR  # noqa: PLC0415

        directory = Path(FILES_DIR) / "tickets"
    except Exception:
        directory = Path(tempfile.gettempdir())
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"shared-form-ticket-{uuid.uuid4().hex}.jpg"


def build_shared_form_ticket_image(data: dict[str, Any], out_path: str | Path | None = None) -> str | None:
    """Render a crisp, high-contrast, approximately 1200×656 JPEG for Bale."""
    try:
        from PIL import Image, ImageDraw  # noqa: PLC0415

        payload = _safe_text(data.get("qr_data"), 500)
        serial = _safe_text(data.get("serial"), 40)
        if not payload or not serial:
            return None
        title = _safe_text(data.get("event_title") or "بلیت ثبت‌نام", 160) or "بلیت ثبت‌نام"
        name = _safe_text(data.get("name"), 120)
        ticket_type = _safe_text(data.get("ticket_type_name"), 80)
        date_parts = event_date_parts(data.get("event_date"))
        times = event_times(data.get("event_time"))
        month_year = date_parts["month_year"] if date_parts else ""
        # An explicit organization name (e.g. from the web service) wins; the bot keeps reading its own settings.
        organization = _safe_text(data.get("organization"), 80) or _font_paths_for_org()

        image = _carpet_background()
        draw = ImageDraw.Draw(image, "RGBA")
        _draw_brand(image, draw, organization, month_year)

        title_font = _font(28, True)
        lines = _wrap_lines(draw, title, title_font, 348, 2)
        for index, line in enumerate(lines):
            _draw_text(draw, line, 581, 62 + index * 35, title_font, INK, align="right")

        _draw_schedule(image, draw, date_parts, times)
        draw.line((230, 257, 582, 257), fill=(255, 255, 255, 77), width=1)
        if name:
            shown_name, name_font = _fit_one_line(draw, name, 345, 14, 10, bold=False)
            _draw_text(draw, shown_name, 581, 270, name_font, INK, align="right")
        if ticket_type:
            type_text, type_font = _fit_one_line(
                draw, f"مدل بلیت: {ticket_type}", 345, 12, 8, bold=True
            )
            _draw_text(draw, type_text, 581, 298, type_font, ACCENT, align="right")
        _draw_qr_panel(image, draw, payload, serial)

        output = image.resize(OUTPUT_SIZE, Image.Resampling.LANCZOS).convert("RGB")
        target = _output_path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        output.save(target, "JPEG", quality=93, optimize=True, progressive=True, subsampling=0)
        return str(target)
    except Exception:
        log.exception("Unable to render the shared form ticket as JPEG")
        return None

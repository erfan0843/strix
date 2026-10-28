"""فاز ۹.۵ §۷.۴ — PDF واقعی گواهی روی مسیر واقعی مرکز صدور (ابزار ``tools/certificate-pdf-check.py``).

* بدون جایگزینی ``certgen.generate``: قالب وردِ فارسی واقعی → ``certcenter.build_one`` → فایل‌ها.
* بدون شبکه و بدون پایگاه عملیاتی (ابزار در زیرفرایند و پوشهٔ موقت اجرا می‌شود).
* بدون LibreOffice فقط PDF جایگزین (تصویری) ساخته می‌شود؛ بررسی «لایهٔ متن» با
  ``skipif`` کنار گذاشته می‌شود و وضعیت صادقانه «نیازمند staging» می‌ماند.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT.parent / "tools" / "certificate-pdf-check.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _points_fixture import ensure_test_env  # noqa: E402

ensure_test_env()

import certgen  # noqa: E402

LIBREOFFICE = bool(certgen.libreoffice_bin())


def _run_tool() -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(TOOL), "--json"], capture_output=True, timeout=600, check=False, cwd=str(ROOT.parent))
    assert proc.stdout, proc.stderr.decode("utf-8", "replace")[-2000:]
    return proc.returncode, json.loads(proc.stdout.decode("utf-8"))


def test_real_certificate_path_produces_valid_pdf_offline():
    code, report = _run_tool()
    assert report["offline"] is True
    checks = {c["check"]: c for c in report["checks"]}
    failed = [name for name, c in checks.items() if not c["ok"] and not c.get("skipped")]
    assert failed == [], json.dumps([checks[n] for n in failed], ensure_ascii=False)
    # مسیر واقعی: scan قالب، نوع «پایان محتوای ضبط‌شده»، ردیف source=recording، PDF معتبر، PNG غیرخالی
    for name in ("template_scan_real_docx", "issue_kind_recording_completion", "build_one_real_generate",
                 "certificate_row_source_recording", "docx_persian_substitution", "pdf_structure_valid",
                 "png_rendered_non_blank", "retry_is_idempotent", "revoke_sets_flag_and_syncs_mirror",
                 "restore_clears_flag_and_syncs_mirror", "revoke_never_deletes_rows", "revoke_restore_audited",
                 "no_bale_delivery_to_holder"):
        assert checks[name]["ok"], checks[name]
    assert report["pdf"]["pages"] == 1 and report["pdf"]["valid_header"] and report["pdf"]["eof_marker"]
    assert report["versions"]["python_docx"] and report["versions"]["pillow"]
    if LIBREOFFICE:
        assert code == 0 and report["engine"] == "office"
    else:
        # صادقانه: بدون LibreOffice فقط PDF تصویری؛ ابزار با کد ۲ (نیازمند staging) پایان می‌یابد
        assert code == 2 and report["engine"] == "builtin_image"
        assert checks["pdf_has_text_layer_office_engine"].get("skipped") is True


@pytest.mark.skipif(not LIBREOFFICE, reason="LibreOffice (soffice) not installed: text-layer PDF requires staging/CI with LibreOffice")
def test_libreoffice_engine_emits_text_layer_pdf_with_persian_name():
    code, report = _run_tool()
    checks = {c["check"]: c for c in report["checks"]}
    assert code == 0, report["summary"]
    assert report["engine"] == "office" and report["pdf"]["has_font"] and report["pdf"]["has_text_operator"]
    assert checks["pdf_has_text_layer_office_engine"]["ok"]
    if shutil.which("pdftotext"):
        assert checks["pdf_text_contains_persian_name"]["ok"], checks["pdf_text_contains_persian_name"]
    assert report["versions"]["libreoffice_version"], "LibreOffice version must be recorded for the evidence"

"""آزمون ایستا: هیچ ماژولی جز points_ledger.py مستقیماً users.total_points را نمی‌نویسد.

همچنین: فرم ویرایش پروفایل امتیاز ندارد و مسیرهای مردهٔ قدیمی (refund_points،
پاداش کلیک تبلیغ) فعال نشده‌اند.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _points_fixture import ensure_test_env  # noqa: E402

ensure_test_env()

U1 = 7001001


# ───────────────────────── static guard ─────────────────────────
_UPDATE_USERS_POINTS = re.compile(r"(?is)update\s+users\s+set\b.*?\btotal_points\s*=")
_INSERT_USERS_POINTS = re.compile(r"(?is)insert\s+(?:or\s+\w+\s+)?into\s+users\b.*?\btotal_points\b")
_ALLOWED = {"points_ledger.py"}


def _string_literals(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value
        elif isinstance(node, ast.JoinedStr):
            yield node.lineno, "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))


def test_no_module_writes_total_points_outside_points_ledger():
    offenders = []
    for path in sorted(ROOT.glob("*.py")):
        if path.name in _ALLOWED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for lineno, text in _string_literals(tree):
            if _UPDATE_USERS_POINTS.search(text) or _INSERT_USERS_POINTS.search(text):
                offenders.append(f"{path.name}:{lineno}")
    assert offenders == [], offenders


def test_profile_editor_no_longer_exposes_total_points():
    import admin
    assert "total_points" not in admin.PROFILE_EDIT_MAP
    source = (ROOT / "admin.py").read_text(encoding="utf-8")
    assert "STATE_POINTS_ADJUST" in source and "POINTS_MANUAL_ADJUST_MAX" in source


def test_dead_paths_stay_dead():
    import payments
    src = (ROOT / "payments.py").read_text(encoding="utf-8")
    assert "refund_points(" not in src.replace("def refund_points(", "")
    assert not re.search(r"(?s)def refund_points.*?total_points", src.split("def _do_points_payment")[0][-1200:])
    ads = (ROOT / "ads.py").read_text(encoding="utf-8")
    assert "post_points" not in ads  # پاداش کلیک تبلیغ عمداً فعال نشده
    assert payments.refund_points(U1, 5) is False



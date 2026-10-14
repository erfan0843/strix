"""Keep executable, legacy test harnesses out of pytest import collection.

A number of phase checks are standalone Python scripts with process-level
``sys.exit`` and environment/database setup at module scope. Importing them
from pytest executes their harnesses (and can make accidental network calls).
They remain runnable directly; pytest collects the function-based tests.
"""
from __future__ import annotations

import re
from pathlib import Path


_TEST_FUNCTION = re.compile(r"(?m)^\s*(?:async\s+)?def\s+test_[A-Za-z0-9_]*\s*\(")
_PROCESS_EXIT = re.compile(r"\bsys\.exit\s*\(")


def pytest_ignore_collect(collection_path, config):
    """Do not import standalone ``test_*.py`` scripts as pytest modules."""
    path = Path(str(collection_path))
    if path.parent.resolve() != Path(__file__).resolve().parent:
        return None
    if path.suffix != ".py" or not path.name.startswith("test_"):
        return None
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if _PROCESS_EXIT.search(source) and not _TEST_FUNCTION.search(source):
        return True
    return None

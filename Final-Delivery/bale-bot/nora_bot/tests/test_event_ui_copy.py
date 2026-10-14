"""Public-facing bot event labels stay clear of retired UI terminology."""

from __future__ import annotations

import ast
from pathlib import Path


BOT_ROOT = Path(__file__).resolve().parents[1]


def _event_types():
    tree = ast.parse((BOT_ROOT / "events.py").read_text(encoding="utf-8"))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "EVENT_TYPES"
            for target in node.targets
        )
    )
    return ast.literal_eval(assignment.value)


def test_event_type_labels_avoid_retired_session_wording():
    event_types = _event_types()
    assert event_types["expert"]["name"] == "رویداد تخصصی"
    assert all("نشست" not in event_type["name"] for event_type in event_types.values())

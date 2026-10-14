from __future__ import annotations

import ast
import os
import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from nora_bot.privacy import redact_log_text, user_error_message


ROOT = Path(__file__).resolve().parents[1]
FAKE_TOKEN = "99999:" + "FAKE_TEST_ONLY_" * 3


@pytest.mark.parametrize("text", [
    "https://bale.invalid/bot" + FAKE_TOKEN + "/sendMessage",
    "https://bale.invalid/bot" + FAKE_TOKEN.replace(":", "%3A") + "/sendMessage",
    'Authorization: Bearer FAKE_TEST_BEARER_VALUE',
    'service_token="FAKE_TEST_SERVICE_VALUE"',
    'password=FAKE_TEST_PASSWORD_VALUE',
    'nora_account_session=FAKE_TEST_SESSION_VALUE',
    'nora_account_csrf=FAKE_TEST_CSRF_VALUE',
    'تماس آزمون: 09000000000 و qa@example.invalid',
])
def test_logs_redact_token_formats_credentials_and_common_contact_data(text):
    output = redact_log_text(text)
    assert "[REDACTED]" in output
    for private in (FAKE_TOKEN, "FAKE_TEST_BEARER_VALUE", "FAKE_TEST_SERVICE_VALUE",
                    "FAKE_TEST_PASSWORD_VALUE", "FAKE_TEST_SESSION_VALUE",
                    "FAKE_TEST_CSRF_VALUE", "09000000000", "qa@example.invalid"):
        assert private not in output


def test_known_environment_secrets_are_also_redacted(monkeypatch):
    monkeypatch.setenv("NORA_BOT_SERVICE_TOKEN", "qa-value-with+reserved/slashes")
    output = redact_log_text("خطا: qa-value-with+reserved/slashes و qa-value-with%2Breserved%2Fslashes")
    assert output == "خطا: [REDACTED] و [REDACTED]"


def test_ordinary_operation_names_and_version_ids_are_not_translated_or_removed():
    text = "sendMessage code=transport_unavailable revision=0022_web_account_registration_history"
    assert redact_log_text(text) == text


def test_console_and_file_logs_use_the_same_redacted_text(tmp_path, capsys):
    # Execute just the real logger function, without importing/creating legacy storage.
    tree = ast.parse((ROOT / "database.py").read_text())
    log_function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "log")
    namespace = {"os": os, "Path": Path, "datetime": datetime, "LOG_DIR": tmp_path,
                 "redact_log_text": redact_log_text}
    exec(compile(ast.Module(body=[log_function], type_ignores=[]), "database.log", "exec"), namespace)
    namespace["log"]("خطای آزمون: " + FAKE_TOKEN)
    console = capsys.readouterr().out
    stored = next(tmp_path.glob("bot_*.log")).read_text()
    assert console == stored
    assert FAKE_TOKEN not in console and "[REDACTED]" in console
    assert not (tmp_path / "nora.db").exists()
    if os.name == "posix":
        assert next(tmp_path.glob("bot_*.log")).stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("exception", [
    requests.exceptions.ConnectionError("request URL contains " + FAKE_TOKEN),
    requests.exceptions.Timeout("request URL contains " + FAKE_TOKEN),
])
def test_transport_failure_is_localized_and_never_echoes_provider_credentials(monkeypatch, exception):
    config = SimpleNamespace(API_URL="https://bale.invalid/bot" + FAKE_TOKEN,
                             FILE_URL="https://bale.invalid/file", AUTO_REACT_EMOJI="", NORA_WEBAPP_URL="")
    logs = []
    monkeypatch.setitem(sys.modules, "config", config)
    monkeypatch.setitem(sys.modules, "database", SimpleNamespace(log=logs.append, get_setting=lambda *args: "0"))
    spec = importlib.util.spec_from_file_location("nora_transport_privacy_qa", ROOT / "bale_api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    def fail_without_network(*args, **kwargs):
        calls.append("local-failure")
        raise exception
    monkeypatch.setattr(module._session, "post", fail_without_network)
    result = module._raw_call("sendMessage", retries=0)
    assert calls == ["local-failure"]
    assert result["ok"] is False
    assert result["error_code"] in {"transport_unavailable", "timeout"}
    assert "دوباره تلاش کن" in result["description"]
    assert FAKE_TOKEN not in str(result) + str(logs)


def test_user_exception_message_never_discloses_exception_internals():
    assert user_error_message(RuntimeError("private provider URL " + FAKE_TOKEN)) == "درخواست انجام نشد؛ دوباره تلاش کن."


def test_chat_exception_sinks_use_the_safe_message_helper():
    for path in ROOT.glob("*.py"):
        tree = ast.parse(path.read_text())
        for handler in ast.walk(tree):
            if not isinstance(handler, ast.ExceptHandler) or not handler.name:
                continue
            for call in ast.walk(handler):
                if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "send"):
                    continue
                for argument in call.args:
                    if not isinstance(argument, ast.JoinedStr):
                        continue
                    for part in argument.values:
                        if not isinstance(part, ast.FormattedValue):
                            continue
                        value = part.value
                        if not any(isinstance(node, ast.Name) and node.id == handler.name for node in ast.walk(value)):
                            continue
                        assert isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "user_error_message", (path.name, call.lineno)

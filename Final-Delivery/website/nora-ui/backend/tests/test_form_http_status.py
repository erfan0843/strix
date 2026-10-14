"""Public form HTTP semantics, with disposable data and no delivery providers."""
from __future__ import annotations

from uuid import uuid4
import json
import re

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app import _form_dict, create_app
from backend.config import Settings
from backend.models import Base, FormRecord


def bootstrap(html, section):
    match = re.search(r'<script\b[^>]*id="nora-public-' + section + r'-data"[^>]*>(.*?)</script>', html, re.S)
    assert match is not None
    raw = match.group(1).strip()
    return None if raw.startswith("<!--nora-public-") else json.loads(raw)


def test_unconfigured_form_resource_is_service_unavailable_not_soft_404():
    app = create_app(Settings(database_url=None, owner_id="http-qa", owner_username="http-qa-owner", owner_password_hash=None))
    with TestClient(app) as client:
        response = client.get(f"/form.html?fid={uuid4()}")
    assert response.status_code == 503
    assert bootstrap(response.text, "error") == "unavailable"
    assert "no-store" in response.headers["cache-control"]
    assert "noindex" in response.headers["x-robots-tag"]
    assert 'lang="fa"' in response.text and 'dir="rtl"' in response.text


@pytest.mark.parametrize("status,expected", [(None, 404), ("draft", 404), ("paused", 200)])
def test_missing_and_unpublished_forms_have_real_404_while_closed_resources_remain_valid(status, expected):
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    form_id = str(uuid4())
    try:
        if status is not None:
            with Session(engine) as db:
                db.add(FormRecord(id=form_id, owner_id="http-qa", title="فرم آزمون وضعیت HTTP",
                                  model="registration", need="registration", settings={}, status=status))
                db.commit()
        app = create_app(Settings(database_url=None, owner_id="http-qa", owner_username="http-qa-owner", owner_password_hash=None), engine=engine)
        with TestClient(app) as client:
            response = client.get(f"/form.html?fid={form_id}")
        assert response.status_code == expected
        assert "no-store" in response.headers["cache-control"]
        assert "noindex" in response.headers["x-robots-tag"]
        assert bootstrap(response.text, "form") is None
        assert "فرم آزمون وضعیت HTTP" not in response.text  # never expose an unpublished title
    finally:
        engine.dispose()


def test_base_and_explicit_preview_interfaces_remain_available_without_leaking_a_form():
    with TestClient(create_app(Settings(database_url=None, owner_id="http-qa", owner_username="http-qa-owner", owner_password_hash=None))) as client:
        assert client.get("/form.html").status_code == 200
        response = client.get(f"/form.html?fid={uuid4()}&preview=1")
    assert response.status_code == 200
    assert "noindex" in response.headers["x-robots-tag"]
    assert bootstrap(response.text, "form") is None


def test_concurrently_missing_form_is_404_not_a_null_dereference():
    with pytest.raises(HTTPException) as error:
        _form_dict(None)
    assert error.value.status_code == 404
    assert error.value.detail == "form_not_found"

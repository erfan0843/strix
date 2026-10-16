from __future__ import annotations

from test_phone_otp_auth import CODE, ORIGIN, PHONE, make_client, request_code, verify_code


def _signed_in(monkeypatch):
    client, engine, _sends = make_client(monkeypatch=monkeypatch)
    body = request_code(client).json()
    assert verify_code(client, body["challenge_id"], CODE).status_code == 200
    return client, engine


def _write_headers(client):
    return {**ORIGIN, "X-CSRF-Token": client.cookies.get("nora_account_csrf")}


def test_profile_is_empty_for_new_account_and_saves_only_whitelisted_fields(monkeypatch):
    client, _engine = _signed_in(monkeypatch)
    try:
        empty = client.get("/api/account/profile")
        assert empty.status_code == 200
        assert empty.json()["saved"] is False
        assert empty.json()["fields"]["fullName"] == ""
        assert PHONE not in empty.text

        saved = client.put(
            "/api/account/profile",
            json={"fullName": "  علی رضایی  ", "city": "تهران", "phone": "09000000000", "role": "owner"},
            headers=_write_headers(client),
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["fields"]["fullName"] == "علی رضایی"
        assert "phone" not in saved.json()["fields"] and "role" not in saved.json()["fields"]

        again = client.get("/api/account/profile").json()
        assert again["saved"] is True and again["fields"]["city"] == "تهران"
    finally:
        client.close()


def test_profile_rejects_markup_long_values_and_non_object_payloads(monkeypatch):
    client, _engine = _signed_in(monkeypatch)
    try:
        assert client.put("/api/account/profile", json={"fullName": "x" * 121}, headers=_write_headers(client)).status_code == 422
        assert client.put("/api/account/profile", json={"fullName": 5}, headers=_write_headers(client)).status_code == 422
        assert client.put("/api/account/profile", json=["x"], headers=_write_headers(client)).status_code == 422
        stored = client.put("/api/account/profile", json={"fullName": "<b>سارا</b>"}, headers=_write_headers(client))
        assert stored.json()["fields"]["fullName"] == "bسارا/b"
    finally:
        client.close()


def test_profile_requires_session_and_csrf(monkeypatch):
    client, _engine, _sends = make_client(monkeypatch=monkeypatch)
    try:
        assert client.get("/api/account/profile").status_code == 401
        assert client.put("/api/account/profile", json={"fullName": "x"}, headers=ORIGIN).status_code in {401, 403}
    finally:
        client.close()

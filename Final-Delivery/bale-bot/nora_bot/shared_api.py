"""Client for the shared Nora backend.

The bot is a delivery/workflow client, not a second source of truth. In
particular, this module never falls back to the bot's legacy SQLite database.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

import config
import requests


_ALLOWED_ROLES = {"owner", "manager", "club-supervisor"}
_USER_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
_FORM_ID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z"
)
_FORM_SESSION_KEY = re.compile(r"[A-Za-z0-9_-]{32,128}\Z")


class SharedAPIError(RuntimeError):
    """A failed or invalid response from the canonical Nora API."""

    def __init__(self, status: int, code: str, detail: object = None):
        super().__init__(code)
        self.status = status
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class SharedIdentity:
    bale_user_id: int
    account_id: str | None
    role: str | None
    permissions: frozenset[str]

    @property
    def is_admin(self) -> bool:
        return self.role in _ALLOWED_ROLES

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


def _api_base() -> str:
    base = config.SHARED_API_URL
    token = config.SHARED_API_TOKEN
    if not base or not token:
        raise SharedAPIError(503, "shared_api_not_configured")
    if len(token) < 32:
        raise SharedAPIError(503, "shared_api_token_too_short")

    parsed = urlsplit(base)
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    secure_scheme = parsed.scheme == "https"
    local_http = parsed.scheme == "http" and (parsed.hostname or "").lower() in local_hosts
    if (not (secure_scheme or local_http) or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise SharedAPIError(503, "shared_api_url_invalid")
    return base.rstrip("/")


def _api_endpoint() -> str:
    """Backward-compatible identity endpoint, validated like every API URL."""
    return _api_base() + "/api/bot/identity"


def _validated_user_id(bale_user_id: int | str) -> str:
    if isinstance(bale_user_id, bool) or not isinstance(bale_user_id, (int, str)):
        raise SharedAPIError(422, "invalid_bale_user_id")
    raw_user_id = str(bale_user_id)
    if not _USER_ID.fullmatch(raw_user_id):
        raise SharedAPIError(422, "invalid_bale_user_id")
    return raw_user_id


def _request_json(method: str, path: str, *, payload=None, params=None) -> dict:
    """Authenticated server-to-server request. Errors never fall back locally."""
    base = _api_base()
    timeout = config.SHARED_API_TIMEOUT_SECONDS
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 30:
        raise SharedAPIError(503, "shared_api_timeout_invalid")
    headers = {
        "Accept": "application/json",
        "Authorization": "Bearer " + config.SHARED_API_TOKEN,
    }
    try:
        if method in {"POST", "PATCH", "DELETE"}:
            request_method = {
                "POST": requests.post,
                "PATCH": requests.patch,
                "DELETE": requests.delete,
            }[method]
            response = request_method(
                base + path,
                json=payload,
                params=params,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
            )
        elif method == "GET":
            response = requests.get(
                base + path,
                params=params,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
            )
        else:
            raise SharedAPIError(500, "shared_api_method_not_supported")
    except requests.RequestException:
        raise SharedAPIError(0, "shared_api_unreachable") from None

    if response.status_code < 200 or response.status_code >= 300:
        code = "shared_api_request_failed"
        detail = None
        try:
            result = response.json()
            detail = result.get("detail") if isinstance(result, dict) else None
            if isinstance(detail, str) and detail:
                code = detail[:80]
            elif isinstance(detail, dict):
                detail_code = detail.get("code")
                errors = detail.get("errors")
                if isinstance(detail_code, str) and detail_code:
                    code = detail_code[:80]
                elif isinstance(errors, list) and errors:
                    code = "answer_validation_failed"
        except (ValueError, TypeError):
            pass
        raise SharedAPIError(response.status_code, code, detail)
    try:
        result = response.json()
    except (ValueError, TypeError):
        raise SharedAPIError(502, "shared_api_invalid_response") from None
    if not isinstance(result, dict):
        raise SharedAPIError(502, "shared_api_invalid_response")
    return result


def get_identity(bale_user_id: int | str) -> SharedIdentity:
    """Resolve a Bale update's user through the backend role/account store.

    The caller must pass the ID taken from a verified Bale update. Transport is
    authenticated with the server-to-server token; client-supplied roles are
    never accepted, and API errors fail closed.
    """
    raw_user_id = _validated_user_id(bale_user_id)
    payload = _request_json(
        "POST", "/api/bot/identity", payload={"bale_user_id": raw_user_id}
    )
    if payload.get("bale_user_id") != raw_user_id:
        raise SharedAPIError(502, "shared_api_identity_mismatch")

    role = payload.get("role")
    if role is not None and role not in _ALLOWED_ROLES:
        raise SharedAPIError(502, "shared_api_invalid_role")
    raw_permissions = payload.get("permissions")
    if (not isinstance(raw_permissions, list)
            or any(not isinstance(permission, str) or not permission for permission in raw_permissions)
            or (role is None and raw_permissions)):
        raise SharedAPIError(502, "shared_api_invalid_permissions")

    account_id = payload.get("account_id")
    if account_id is not None and (not isinstance(account_id, str) or not account_id):
        raise SharedAPIError(502, "shared_api_invalid_account")
    return SharedIdentity(
        bale_user_id=int(raw_user_id),
        account_id=account_id,
        role=role,
        permissions=frozenset(raw_permissions),
    )


def require_owner_identity(bale_user_id: int | str) -> SharedIdentity:
    """Require the configured bot operator to be the canonical server owner.

    The bot still has legacy local-only features. Do not initialize its local
    admin database until its configured super-admin is confirmed as the owner
    in the shared role store.
    """
    identity = get_identity(bale_user_id)
    if identity.role != "owner":
        raise SharedAPIError(403, "shared_owner_identity_required")
    return identity


_REPORT_PERIODS = frozenset({"today", "yesterday", "7d", "30d", "90d", "365d", "year", "all"})
_REPORT_KEYS = {
    "source", "period", "generated_at", "forms", "responses", "accounts",
    "reviews", "notifications", "cooperation_requests", "coverage",
}


def _report_count_map(value: object) -> bool:
    return (isinstance(value, dict)
            and all(isinstance(key, str) and key and type(count) is int and count >= 0
                    for key, count in value.items()))


def _validate_report_summary(value: object, expected_period: str) -> dict:
    if not isinstance(value, dict) or set(value) != _REPORT_KEYS:
        raise SharedAPIError(502, "shared_api_invalid_report")
    if (value.get("source") != "shared_server_database"
            or value.get("period") != expected_period
            or not isinstance(value.get("generated_at"), str)):
        raise SharedAPIError(502, "shared_api_invalid_report")

    forms = value.get("forms")
    responses = value.get("responses")
    accounts = value.get("accounts")
    reviews = value.get("reviews")
    notifications = value.get("notifications")
    if (not isinstance(forms, dict) or set(forms) != {"total", "created_in_period", "by_status"}
            or type(forms.get("total")) is not int or forms["total"] < 0
            or type(forms.get("created_in_period")) is not int or forms["created_in_period"] < 0
            or not _report_count_map(forms.get("by_status"))):
        raise SharedAPIError(502, "shared_api_invalid_report")
    if (not isinstance(responses, dict) or set(responses) != {"total", "by_status"}
            or type(responses.get("total")) is not int or responses["total"] < 0
            or not _report_count_map(responses.get("by_status"))):
        raise SharedAPIError(502, "shared_api_invalid_report")
    if (not isinstance(accounts, dict) or set(accounts) != {"total", "by_role"}
            or (accounts["total"] is not None
                and (type(accounts["total"]) is not int or accounts["total"] < 0))
            or (accounts["by_role"] is not None and not _report_count_map(accounts["by_role"]))):
        raise SharedAPIError(502, "shared_api_invalid_report")
    if (not isinstance(reviews, dict) or set(reviews) != {"total", "by_kind"}
            or type(reviews.get("total")) is not int or reviews["total"] < 0
            or not isinstance(reviews.get("by_kind"), dict)
            or any(kind not in {"profile_review", "receipt_review"} or not _report_count_map(counts)
                   for kind, counts in reviews["by_kind"].items())):
        raise SharedAPIError(502, "shared_api_invalid_report")
    if (not isinstance(notifications, dict) or set(notifications) != {"total", "by_delivery_status"}
            or type(notifications.get("total")) is not int or notifications["total"] < 0
            or not _report_count_map(notifications.get("by_delivery_status"))):
        raise SharedAPIError(502, "shared_api_invalid_report")
    cooperation = value.get("cooperation_requests")
    if cooperation is not None and (
        not isinstance(cooperation, dict) or set(cooperation) != {"total", "by_status"}
        or type(cooperation.get("total")) is not int or cooperation["total"] < 0
        or not _report_count_map(cooperation.get("by_status"))
    ):
        raise SharedAPIError(502, "shared_api_invalid_report")
    coverage = value.get("coverage")
    if (not isinstance(coverage, dict)
            or any(not isinstance(key, str) or not isinstance(item, str) for key, item in coverage.items())):
        raise SharedAPIError(502, "shared_api_invalid_report")
    return value


def get_report_summary(bale_user_id: int | str, period: str = "30d") -> dict:
    """Fetch an aggregate report; the server verifies rp_view for this Bale ID."""
    raw_user_id = _validated_user_id(bale_user_id)
    if not isinstance(period, str) or period not in _REPORT_PERIODS:
        raise SharedAPIError(422, "invalid_report_period")
    result = _request_json(
        "POST",
        "/api/bot/reports/summary",
        payload={"bale_user_id": raw_user_id, "period": period},
    )
    return _validate_report_summary(result, period)


def _valid_catalog_text(value: object, max_length: int) -> bool:
    """Allow Persian joiners while rejecting controls and misleading format marks."""
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        return False
    return all(
        (category := unicodedata.category(char)) not in {"Cc", "Cs"}
        and (category != "Cf" or char in {"\u200c", "\u200d"})
        for char in value
    )


def _valid_optional_catalog_text(value: object, max_length: int) -> bool:
    return value == "" or _valid_catalog_text(value, max_length)


def list_public_forms() -> list[dict]:
    """Fetch the public, currently open form catalog from the shared database."""
    result = _request_json("GET", "/api/bot/forms/public")
    items = result.get("items")
    if (
        set(result) != {"source", "items"}
        or result.get("source") != "shared_server_database"
        or not isinstance(items, list)
        or len(items) > 100
    ):
        raise SharedAPIError(502, "shared_api_invalid_public_forms")

    expected_keys = {"id", "name", "model", "need", "version"}
    form_id_pattern = re.compile(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z"
    )
    validated: list[dict] = []
    seen_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != expected_keys:
            raise SharedAPIError(502, "shared_api_invalid_public_form")
        form_id = item.get("id")
        name = item.get("name")
        model = item.get("model")
        need = item.get("need")
        version = item.get("version")
        if (
            not isinstance(form_id, str)
            or not form_id_pattern.fullmatch(form_id)
            or form_id in seen_ids
            or not _valid_catalog_text(name, 160)
            or not _valid_catalog_text(model, 40)
            or not _valid_catalog_text(need, 40)
            or type(version) is not int
            or version < 1
        ):
            raise SharedAPIError(502, "shared_api_invalid_public_form")
        seen_ids.add(form_id)
        validated.append({
            "id": form_id,
            "name": name,
            "model": model,
            "need": need,
            "version": version,
        })
    return validated


_PUBLIC_FIELD_TYPES = frozenset({
    "text", "area", "number", "amount", "mobile", "nid", "email", "fullname",
    "date", "time", "datetime", "slot", "choice", "multi", "dropdown", "select",
    "yesno", "imgchoice", "rating", "scale", "bars", "province", "address", "gender",
    "edu", "job", "uni", "marital", "terms", "location",
})


def _validated_form_id(form_id: str) -> str:
    if not isinstance(form_id, str) or not _FORM_ID.fullmatch(form_id):
        raise SharedAPIError(422, "invalid_public_form_id")
    return form_id


def _validated_form_session(bale_user_id: int | str, form_id: str, session_key: str) -> tuple[str, str]:
    user_id = _validated_user_id(bale_user_id)
    form_id = _validated_form_id(form_id)
    if not isinstance(session_key, str) or not _FORM_SESSION_KEY.fullmatch(session_key):
        raise SharedAPIError(422, "invalid_bot_form_session_key")
    return user_id, form_id


def _validate_bot_form_state(value: object, expected_form_id: str) -> dict:
    expected_keys = {"source", "form", "draft", "visible_field_ids"}
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise SharedAPIError(502, "shared_api_invalid_bot_form_state")
    form = value.get("form")
    draft = value.get("draft")
    if (value.get("source") != "shared_server_database"
            or not isinstance(form, dict)
            or form.get("id") != expected_form_id
            or form.get("status") != "published"
            or not _valid_catalog_text(form.get("name"), 160)
            or not _valid_catalog_text(form.get("model"), 40)
            or type(form.get("version")) is not int or form["version"] < 1
            or not isinstance(draft, dict)
            or set(draft) != {"answers", "submitted", "status", "form_version"}
            or type(draft.get("submitted")) is not bool
            or type(draft.get("form_version")) is not int or draft["form_version"] < 1
            or not isinstance(draft.get("status"), str)
            or draft["status"] not in {"draft", "accepted", "waitlisted"}):
        raise SharedAPIError(502, "shared_api_invalid_bot_form_state")

    fields = form.get("fields")
    if not isinstance(fields, list) or not 1 <= len(fields) <= 30:
        raise SharedAPIError(502, "shared_api_invalid_bot_form_fields")
    field_ids: set[str] = set()
    for field in fields:
        if not isinstance(field, dict):
            raise SharedAPIError(502, "shared_api_invalid_bot_form_field")
        field_id, field_type, label = field.get("id"), field.get("t"), field.get("l")
        if (not isinstance(field_id, str) or not 1 <= len(field_id) <= 80 or field_id in field_ids
                or not isinstance(field_type, str) or field_type not in _PUBLIC_FIELD_TYPES
                or not _valid_catalog_text(label, 160)):
            raise SharedAPIError(502, "shared_api_invalid_bot_form_field")
        field_ids.add(field_id)
        for option_key in ("opts", "options"):
            options = field.get(option_key)
            if options is None:
                continue
            if not isinstance(options, list) or len(options) > 100:
                raise SharedAPIError(502, "shared_api_invalid_bot_form_options")
            for option in options:
                option_label = option.get("l") if isinstance(option, dict) else option
                if not _valid_catalog_text(option_label, 120):
                    raise SharedAPIError(502, "shared_api_invalid_bot_form_options")

    answers = draft.get("answers")
    if not isinstance(answers, dict) or set(answers) - field_ids:
        raise SharedAPIError(502, "shared_api_invalid_bot_form_answers")
    for answer in answers.values():
        values = answer if isinstance(answer, list) else [answer]
        if (not isinstance(values, list) or len(values) > 100
                or any(not isinstance(item, str) or len(item) > 4000
                       or any(ord(char) == 0 or 0xD800 <= ord(char) <= 0xDFFF for char in item)
                       for item in values)):
            raise SharedAPIError(502, "shared_api_invalid_bot_form_answers")
    if (draft["submitted"] != (draft["status"] in {"accepted", "waitlisted"})):
        raise SharedAPIError(502, "shared_api_invalid_bot_form_state")

    visible = value.get("visible_field_ids")
    if (not isinstance(visible, list) or len(visible) > len(fields)
            or any(not isinstance(item, str) or item not in field_ids for item in visible)
            or len(visible) != len(set(visible))):
        raise SharedAPIError(502, "shared_api_invalid_bot_form_visibility")
    return value


def _validate_bot_form_history(value: object, requested_page: int) -> dict:
    expected_keys = {"source", "items", "total", "page", "pages", "page_size"}
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise SharedAPIError(502, "shared_api_invalid_bot_form_history")
    total, page, pages, page_size = (
        value.get("total"), value.get("page"), value.get("pages"), value.get("page_size")
    )
    if (
        value.get("source") != "shared_server_database"
        or type(total) is not int
        or total < 0
        or type(page) is not int
        or type(pages) is not int
        or type(page_size) is not int
        or not 1 <= page_size <= 100
    ):
        raise SharedAPIError(502, "shared_api_invalid_bot_form_history")
    if pages != (total + page_size - 1) // page_size:
        raise SharedAPIError(502, "shared_api_invalid_bot_form_history")
    if (
        page != min(requested_page, max(0, pages - 1))
        or not 0 <= page < max(1, pages)
    ):
        raise SharedAPIError(502, "shared_api_invalid_bot_form_history")
    items = value.get("items")
    expected_item_count = min(page_size, max(0, total - page * page_size))
    if not isinstance(items, list) or len(items) != expected_item_count:
        raise SharedAPIError(502, "shared_api_invalid_bot_form_history")
    expected_item_keys = {
        "id", "form_id", "form_name", "status", "form_version", "answer_count", "created_at"
    }
    seen_ids: set[str] = set()
    for item in items:
        if (
            not isinstance(item, dict)
            or set(item) != expected_item_keys
            or not isinstance(item.get("id"), str)
            or not _FORM_ID.fullmatch(item["id"])
            or item["id"] in seen_ids
            or not isinstance(item.get("form_id"), str)
            or not _FORM_ID.fullmatch(item["form_id"])
            or not _valid_catalog_text(item.get("form_name"), 160)
            or not isinstance(item.get("status"), str)
            or item["status"] not in {"accepted", "waitlisted"}
            or type(item.get("form_version")) is not int
            or item["form_version"] < 1
            or type(item.get("answer_count")) is not int
            or not 0 <= item["answer_count"] <= 30
            or not _valid_catalog_text(item.get("created_at"), 40)
        ):
            raise SharedAPIError(502, "shared_api_invalid_bot_form_history_item")
        seen_ids.add(item["id"])
    return value


def _validate_bot_admin_form_catalog(value: object, requested_page: int) -> dict:
    expected_keys = {"source", "items", "total", "page", "pages", "page_size"}
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise SharedAPIError(502, "shared_api_invalid_bot_admin_forms")
    total, page, pages, page_size = (
        value.get("total"), value.get("page"), value.get("pages"), value.get("page_size")
    )
    if (
        value.get("source") != "shared_server_database"
        or type(total) is not int
        or total < 0
        or type(page) is not int
        or type(pages) is not int
        or type(page_size) is not int
        or not 1 <= page_size <= 100
        or pages != (total + page_size - 1) // page_size
        or page != min(requested_page, max(0, pages - 1))
        or not 0 <= page < max(1, pages)
    ):
        raise SharedAPIError(502, "shared_api_invalid_bot_admin_forms")
    items = value.get("items")
    expected_count = min(page_size, max(0, total - page * page_size))
    if not isinstance(items, list) or len(items) != expected_count:
        raise SharedAPIError(502, "shared_api_invalid_bot_admin_forms")
    expected_item_keys = {"id", "name", "status", "version", "response_count"}
    seen_ids: set[str] = set()
    for item in items:
        if (
            not isinstance(item, dict)
            or set(item) != expected_item_keys
            or not isinstance(item.get("id"), str)
            or not _FORM_ID.fullmatch(item["id"])
            or item["id"] in seen_ids
            or not _valid_catalog_text(item.get("name"), 160)
            or not isinstance(item.get("status"), str)
            or item["status"] not in {"draft", "published", "paused", "archived"}
            or type(item.get("version")) is not int
            or item["version"] < 1
            or type(item.get("response_count")) is not int
            or item["response_count"] < 0
        ):
            raise SharedAPIError(502, "shared_api_invalid_bot_admin_form_item")
        seen_ids.add(item["id"])
    return value


def _validate_bot_form_response_detail(value: object, expected_response_id: str) -> dict:
    if not isinstance(value, dict) or set(value) != {"source", "response"}:
        raise SharedAPIError(502, "shared_api_invalid_bot_form_response")
    response = value.get("response")
    expected_response_keys = {
        "id", "form_id", "status", "form_version", "created_at", "form_snapshot", "answers"
    }
    if (
        value.get("source") != "shared_server_database"
        or not isinstance(response, dict)
        or set(response) != expected_response_keys
        or response.get("id") != expected_response_id
        or not isinstance(response.get("form_id"), str)
        or not _FORM_ID.fullmatch(response["form_id"])
        or not isinstance(response.get("status"), str)
        or response["status"] not in {"accepted", "waitlisted"}
        or type(response.get("form_version")) is not int
        or response["form_version"] < 1
        or not _valid_catalog_text(response.get("created_at"), 40)
    ):
        raise SharedAPIError(502, "shared_api_invalid_bot_form_response")
    snapshot = response.get("form_snapshot")
    required_snapshot_keys = {"id", "name", "model", "need", "version", "fields"}
    allowed_snapshot_keys = required_snapshot_keys | {
        "receipt_review_required", "event", "ticket_type",
    }
    if (
        not isinstance(snapshot, dict)
        or not required_snapshot_keys <= set(snapshot)
        or set(snapshot) - allowed_snapshot_keys
        or snapshot.get("id") != response["form_id"]
        or not _valid_catalog_text(snapshot.get("name"), 160)
        or not _valid_catalog_text(snapshot.get("model"), 40)
        or not _valid_catalog_text(snapshot.get("need"), 40)
        or type(snapshot.get("version")) is not int
        or snapshot["version"] != response["form_version"]
        or (
            "receipt_review_required" in snapshot
            and type(snapshot["receipt_review_required"]) is not bool
        )
        or (
            "ticket_type" in snapshot
            and not _valid_form_ticket_type(snapshot["ticket_type"])
        )
    ):
        raise SharedAPIError(502, "shared_api_invalid_bot_form_snapshot")
    event = snapshot.get("event")
    if "event" in snapshot and (
        not isinstance(event, dict)
        or set(event) - {"title", "date", "time"}
        or not _valid_catalog_text(event.get("title"), 160)
        or not _valid_optional_catalog_text(event.get("date", ""), 120)
        or not _valid_optional_catalog_text(event.get("time", ""), 120)
    ):
        raise SharedAPIError(502, "shared_api_invalid_bot_form_snapshot")
    fields = snapshot.get("fields")
    if not isinstance(fields, list) or not 1 <= len(fields) <= 30:
        raise SharedAPIError(502, "shared_api_invalid_bot_form_snapshot")
    field_ids: set[str] = set()
    for field in fields:
        if (
            not isinstance(field, dict)
            or set(field) != {"id", "type", "label"}
            or not isinstance(field.get("id"), str)
            or not 1 <= len(field["id"]) <= 80
            or field["id"] in field_ids
            or not isinstance(field.get("type"), str)
            or field["type"] not in _PUBLIC_FIELD_TYPES
            or not _valid_catalog_text(field.get("label"), 160)
        ):
            raise SharedAPIError(502, "shared_api_invalid_bot_form_snapshot_field")
        field_ids.add(field["id"])
    answers = response.get("answers")
    if not isinstance(answers, dict) or set(answers) - field_ids:
        raise SharedAPIError(502, "shared_api_invalid_bot_form_response_answers")
    for answer in answers.values():
        values = answer if isinstance(answer, list) else [answer]
        if (
            len(values) > 100
            or any(
                not isinstance(item, str)
                or len(item) > 4000
                or any(ord(char) == 0 or 0xD800 <= ord(char) <= 0xDFFF for char in item)
                for item in values
            )
        ):
            raise SharedAPIError(502, "shared_api_invalid_bot_form_response_answers")
    return value


def _bot_form_identity_payload(
    bale_user_id: int | str, form_id: str, session_key: str
) -> tuple[dict[str, str], str]:
    user_id, form_id = _validated_form_session(bale_user_id, form_id, session_key)
    return {"bale_user_id": user_id, "session_key": session_key}, form_id


def start_bot_form_draft(
    bale_user_id: int | str, form_id: str, session_key: str
) -> dict:
    """Create or idempotently recover the server draft for one conversation attempt."""
    payload, form_id = _bot_form_identity_payload(bale_user_id, form_id, session_key)
    result = _request_json("POST", f"/api/bot/forms/{form_id}/draft", payload=payload)
    return _validate_bot_form_state(result, form_id)


def get_bot_form_draft(
    bale_user_id: int | str, form_id: str, session_key: str
) -> dict:
    """Read a draft without returning any bot-local copy of its answers."""
    payload, form_id = _bot_form_identity_payload(bale_user_id, form_id, session_key)
    result = _request_json(
        "POST", f"/api/bot/forms/{form_id}/draft/state", payload=payload
    )
    return _validate_bot_form_state(result, form_id)


def save_bot_form_answer(
    bale_user_id: int | str,
    form_id: str,
    session_key: str,
    field_id: str,
    value: object = None,
    *,
    remove: bool = False,
) -> dict:
    """Upsert or remove one answer in the canonical server-side draft."""
    payload, form_id = _bot_form_identity_payload(bale_user_id, form_id, session_key)
    if not isinstance(field_id, str) or not 1 <= len(field_id) <= 80:
        raise SharedAPIError(422, "invalid_bot_form_field_id")
    payload["field_id"] = field_id
    if remove:
        payload["remove"] = True
    else:
        if not isinstance(value, (str, list)):
            raise SharedAPIError(422, "invalid_bot_form_answer")
        payload["value"] = value
    result = _request_json(
        "PATCH", f"/api/bot/forms/{form_id}/draft", payload=payload
    )
    return _validate_bot_form_state(result, form_id)


def delete_bot_form_draft(
    bale_user_id: int | str, form_id: str, session_key: str
) -> dict:
    payload, form_id = _bot_form_identity_payload(bale_user_id, form_id, session_key)
    result = _request_json(
        "DELETE", f"/api/bot/forms/{form_id}/draft", payload=payload
    )
    if (set(result) != {"deleted", "submitted"}
            or type(result.get("deleted")) is not bool
            or type(result.get("submitted")) is not bool):
        raise SharedAPIError(502, "shared_api_invalid_bot_form_delete")
    return result


def submit_bot_form_response(
    bale_user_id: int | str, form_id: str, session_key: str
) -> dict:
    payload, form_id = _bot_form_identity_payload(bale_user_id, form_id, session_key)
    result = _request_json(
        "POST", f"/api/bot/forms/{form_id}/responses", payload=payload
    )
    if (set(result) != {"accepted", "already_submitted", "response_id", "status", "form_version"}
            or result.get("accepted") is not True
            or type(result.get("already_submitted")) is not bool
            or not isinstance(result.get("response_id"), str)
            or not _FORM_ID.fullmatch(result["response_id"])
            or not isinstance(result.get("status"), str)
            or result["status"] not in {"accepted", "waitlisted"}
            or type(result.get("form_version")) is not int
            or result["form_version"] < 1):
        raise SharedAPIError(502, "shared_api_invalid_bot_form_response")
    return result


_TICKET_SERIAL = re.compile(r"NORA-[A-F0-9]{20}\Z")
_TICKET_CLAIM_TOKEN = re.compile(r"[A-Za-z0-9_-]{48}\Z")


def _valid_form_ticket_type(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"id", "name"}
        and isinstance(value.get("id"), str)
        and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value["id"]))
        and _valid_catalog_text(value.get("name"), 80)
    )


def _validate_form_ticket(value: object, *, admin: bool = False, checkin: bool = False) -> dict:
    expected = {
        "source", "response_id", "form_id", "serial", "form_title",
        "event_title", "event_date", "event_time", "participant_name",
        "issued_at", "receipt_required", "receipt_submitted", "checked_in", "checked_in_at",
    }
    if admin:
        expected.add("checked_in_by_bale_user_id")
    if checkin:
        expected.add("already_checked_in")
    if isinstance(value, dict) and "ticket_type" in value:
        expected.add("ticket_type")
    if not isinstance(value, dict) or set(value) != expected:
        raise SharedAPIError(502, "shared_api_invalid_form_ticket")
    if (
        value.get("source") != "shared_server_database"
        or not isinstance(value.get("response_id"), str)
        or not _FORM_ID.fullmatch(value["response_id"])
        or not isinstance(value.get("form_id"), str)
        or not _FORM_ID.fullmatch(value["form_id"])
        or not isinstance(value.get("serial"), str)
        or not _TICKET_SERIAL.fullmatch(value["serial"])
        or not _valid_catalog_text(value.get("form_title"), 160)
        or not _valid_catalog_text(value.get("event_title"), 160)
        or not _valid_optional_catalog_text(value.get("event_date"), 120)
        or not _valid_optional_catalog_text(value.get("event_time"), 120)
        or not _valid_catalog_text(value.get("participant_name"), 120)
        or not _valid_catalog_text(value.get("issued_at"), 64)
        or type(value.get("receipt_required")) is not bool
        or type(value.get("receipt_submitted")) is not bool
        or type(value.get("checked_in")) is not bool
        or (value.get("checked_in_at") is not None
            and not _valid_catalog_text(value.get("checked_in_at"), 64))
        or (value["checked_in"] != (value.get("checked_in_at") is not None))
    ):
        raise SharedAPIError(502, "shared_api_invalid_form_ticket")
    if "ticket_type" in value and not _valid_form_ticket_type(value["ticket_type"]):
        raise SharedAPIError(502, "shared_api_invalid_form_ticket")
    if admin:
        checked_by = value.get("checked_in_by_bale_user_id")
        if checked_by is not None and (
            not isinstance(checked_by, str) or not _USER_ID.fullmatch(checked_by)
        ):
            raise SharedAPIError(502, "shared_api_invalid_form_ticket")
        if value["checked_in"] != (checked_by is not None):
            raise SharedAPIError(502, "shared_api_invalid_form_ticket")
    if checkin and (
        type(value.get("already_checked_in")) is not bool
        or not value["checked_in"]
    ):
        raise SharedAPIError(502, "shared_api_invalid_form_ticket")
    return value


def get_bot_form_ticket(
    bale_user_id: int | str, form_id: str, response_id: str
) -> dict:
    """Fetch only this user's accepted registration ticket from the canonical API."""
    user_id = _validated_user_id(bale_user_id)
    form_id = _validated_form_id(form_id)
    response_id = _validated_form_id(response_id)
    result = _request_json(
        "POST",
        f"/api/bot/forms/{form_id}/responses/{response_id}/ticket",
        payload={"bale_user_id": user_id},
    )
    return _validate_form_ticket(result)


def claim_bot_form_ticket(bale_user_id: int | str, token: str) -> dict:
    """Redeem an opaque public-form handoff token for the authenticated Bale user."""
    user_id = _validated_user_id(bale_user_id)
    if not isinstance(token, str) or not _TICKET_CLAIM_TOKEN.fullmatch(token):
        raise SharedAPIError(422, "invalid_ticket_claim_token")
    result = _request_json(
        "POST",
        "/api/bot/form-tickets/claim",
        payload={"bale_user_id": user_id, "token": token},
    )
    return _validate_form_ticket(result)


def verify_bot_form_ticket(bale_user_id: int | str, response_id: str) -> dict:
    """Verify a shared-form ticket; server permissions gate attendee details."""
    user_id = _validated_user_id(bale_user_id)
    response_id = _validated_form_id(response_id)
    result = _request_json(
        "POST",
        f"/api/bot/form-tickets/{response_id}/verify",
        payload={"bale_user_id": user_id},
    )
    return _validate_form_ticket(result, admin=True)


def check_in_bot_form_ticket(bale_user_id: int | str, response_id: str) -> dict:
    """Mark an accepted ticket as used once, using the shared server database."""
    user_id = _validated_user_id(bale_user_id)
    response_id = _validated_form_id(response_id)
    result = _request_json(
        "POST",
        f"/api/bot/form-tickets/{response_id}/check-in",
        payload={"bale_user_id": user_id},
    )
    return _validate_form_ticket(result, admin=True, checkin=True)


def list_my_bot_form_responses(bale_user_id: int | str, page: int = 0) -> dict:
    """Fetch one server-backed page of this Bale user's submitted bot forms."""
    raw_user_id = _validated_user_id(bale_user_id)
    if type(page) is not int or not 0 <= page <= 100_000:
        raise SharedAPIError(422, "invalid_bot_form_history_page")
    result = _request_json(
        "GET",
        "/api/bot/forms/mine",
        params={"bale_user_id": raw_user_id, "page": page},
    )
    return _validate_bot_form_history(result, page)


def get_my_bot_form_response(bale_user_id: int | str, response_id: str) -> dict:
    """Read one submitted response only when its server-side Bale owner matches."""
    raw_user_id = _validated_user_id(bale_user_id)
    if not isinstance(response_id, str) or not _FORM_ID.fullmatch(response_id):
        raise SharedAPIError(422, "invalid_bot_form_response_id")
    result = _request_json(
        "GET",
        f"/api/bot/forms/responses/{response_id}",
        params={"bale_user_id": raw_user_id},
    )
    return _validate_bot_form_response_detail(result, response_id)


def list_bot_admin_forms(bale_user_id: int | str, page: int = 0) -> dict:
    """List shared forms for a Bale identity with the server-side fm_responses permission."""
    raw_user_id = _validated_user_id(bale_user_id)
    if type(page) is not int or not 0 <= page <= 100_000:
        raise SharedAPIError(422, "invalid_bot_admin_forms_page")
    result = _request_json(
        "GET",
        "/api/bot/admin/forms",
        params={"bale_user_id": raw_user_id, "page": page},
    )
    return _validate_bot_admin_form_catalog(result, page)


def list_bot_admin_form_responses(
    bale_user_id: int | str, form_id: str, page: int = 0
) -> dict:
    """Read one shared form's responses after server-side fm_responses authorization."""
    raw_user_id = _validated_user_id(bale_user_id)
    form_id = _validated_form_id(form_id)
    if type(page) is not int or not 0 <= page <= 100_000:
        raise SharedAPIError(422, "invalid_bot_admin_response_page")
    result = _request_json(
        "GET",
        f"/api/bot/admin/forms/{form_id}/responses",
        params={"bale_user_id": raw_user_id, "page": page},
    )
    return _validate_bot_form_history(result, page)


def get_bot_admin_form_response(bale_user_id: int | str, response_id: str) -> dict:
    """Read response details for a form manager, not from the bot's local SQLite."""
    raw_user_id = _validated_user_id(bale_user_id)
    if not isinstance(response_id, str) or not _FORM_ID.fullmatch(response_id):
        raise SharedAPIError(422, "invalid_bot_admin_response_id")
    result = _request_json(
        "GET",
        f"/api/bot/admin/responses/{response_id}",
        params={"bale_user_id": raw_user_id},
    )
    return _validate_bot_form_response_detail(result, response_id)


def has_permission(bale_user_id: int | str, permission: str) -> bool:
    """Fail-closed convenience check; no role cache or local permission fallback."""
    if not isinstance(permission, str) or not permission:
        return False
    return get_identity(bale_user_id).has_permission(permission)


def _validate_task(value: object) -> dict:
    if not isinstance(value, dict):
        raise SharedAPIError(502, "shared_api_invalid_workflow")
    if (not isinstance(value.get("id"), str)
            or not re.fullmatch(r"[0-9a-fA-F-]{36}", value["id"])
            or value.get("kind") not in {"profile_review", "receipt_review"}
            or value.get("status") not in {"pending", "approved", "rejected", "superseded"}
            or ("projection_status" in value and value.get("projection_status") not in {"pending", "applied", "failed"})
            or not isinstance(value.get("payload"), dict)
            or isinstance(value.get("version"), bool)
            or not isinstance(value.get("version"), int)
            or value["version"] < 1):
        raise SharedAPIError(502, "shared_api_invalid_workflow")
    return value


def upload_private_file(
    bale_user_id: int | str,
    content: bytes,
    filename: str,
    idempotency_key: str,
) -> str:
    """Upload an attachment to private storage shared by the bot and website."""
    raw_user_id = _validated_user_id(bale_user_id)
    if not isinstance(content, bytes) or not content or len(content) > 8 * 1024 * 1024:
        raise SharedAPIError(422, "invalid_private_file")
    if content.startswith(b"\xff\xd8\xff"):
        content_type = "image/jpeg"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        content_type = "image/png"
    elif len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        content_type = "image/webp"
    elif content.startswith(b"%PDF-"):
        content_type = "application/pdf"
    else:
        raise SharedAPIError(415, "unsupported_private_file_type")
    if not isinstance(filename, str) or not filename or len(filename) > 120:
        raise SharedAPIError(422, "invalid_private_file_name")
    if not isinstance(idempotency_key, str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,120}", idempotency_key):
        raise SharedAPIError(422, "invalid_idempotency_key")
    base = _api_base()
    timeout = config.SHARED_API_TIMEOUT_SECONDS
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 30:
        raise SharedAPIError(503, "shared_api_timeout_invalid")
    try:
        response = requests.post(
            base + "/api/bot/files",
            data=content,
            headers={
                "Accept": "application/json",
                "Authorization": "Bearer " + config.SHARED_API_TOKEN,
                "Content-Type": content_type,
                "X-Bale-User-Id": raw_user_id,
                "X-File-Name": filename,
                "Idempotency-Key": idempotency_key,
            },
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.RequestException:
        raise SharedAPIError(0, "shared_api_unreachable") from None
    if response.status_code < 200 or response.status_code >= 300:
        code = "shared_api_request_failed"
        try:
            body = response.json()
            detail = body.get("detail") if isinstance(body, dict) else None
            if isinstance(detail, str) and detail:
                code = detail[:80]
        except (ValueError, TypeError):
            pass
        raise SharedAPIError(response.status_code, code)
    try:
        result = response.json()
    except (ValueError, TypeError):
        raise SharedAPIError(502, "shared_api_invalid_file_response") from None
    file_id = result.get("id") if isinstance(result, dict) else None
    if (not isinstance(file_id, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", file_id)
            or result.get("content_type") != content_type or result.get("size") != len(content)):
        raise SharedAPIError(502, "shared_api_invalid_file_response")
    return file_id


def download_private_file(file_id: str) -> tuple[bytes, str]:
    if not isinstance(file_id, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", file_id):
        raise SharedAPIError(422, "invalid_private_file_id")
    base = _api_base()
    timeout = config.SHARED_API_TIMEOUT_SECONDS
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 30:
        raise SharedAPIError(503, "shared_api_timeout_invalid")
    try:
        response = requests.get(
            base + "/api/bot/files/" + file_id,
            headers={"Accept": "application/octet-stream", "Authorization": "Bearer " + config.SHARED_API_TOKEN},
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.RequestException:
        raise SharedAPIError(0, "shared_api_unreachable") from None
    if response.status_code < 200 or response.status_code >= 300:
        code = "shared_api_request_failed"
        try:
            body = response.json()
            detail = body.get("detail") if isinstance(body, dict) else None
            if isinstance(detail, str) and detail:
                code = detail[:80]
        except (ValueError, TypeError):
            pass
        raise SharedAPIError(response.status_code, code)
    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    content = response.content
    if (content_type not in {"image/jpeg", "image/png", "image/webp", "application/pdf"}
            or not content or len(content) > 8 * 1024 * 1024):
        raise SharedAPIError(502, "shared_api_invalid_private_file")
    return content, content_type


def list_private_files(bale_user_id: int | str) -> list[dict]:
    """List only the private attachments belonging to the verified Bale account."""
    raw_user_id = _validated_user_id(bale_user_id)
    result = _request_json(
        "GET", "/api/bot/files", params={"bale_user_id": raw_user_id}
    )
    items = result.get("items")
    if not isinstance(items, list) or len(items) > 100:
        raise SharedAPIError(502, "shared_api_invalid_private_files")
    allowed_types = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            raise SharedAPIError(502, "shared_api_invalid_private_file")
        file_id = item.get("id")
        name = item.get("file_name")
        content_type = item.get("content_type")
        size = item.get("content_size")
        created_at = item.get("created_at")
        if (not isinstance(file_id, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", file_id)
                or not isinstance(name, str) or not name or len(name) > 180
                or any(ord(char) < 32 for char in name)
                or content_type not in allowed_types
                or isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 8 * 1024 * 1024
                or not isinstance(created_at, str)):
            raise SharedAPIError(502, "shared_api_invalid_private_file")
        normalized.append({
            "id": file_id,
            "file_name": name,
            "content_type": content_type,
            "content_size": size,
            "created_at": created_at,
        })
    return normalized


def download_content_file(delivery_id: str) -> tuple[bytes, str, str]:
    """Fetch one owner-published public asset for delivery through Bale."""
    if not isinstance(delivery_id, str) or not re.fullmatch(r"[0-9a-f]{32}", delivery_id):
        raise SharedAPIError(422, "invalid_content_delivery_id")
    base = _api_base()
    timeout = config.SHARED_API_TIMEOUT_SECONDS
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 30:
        raise SharedAPIError(503, "shared_api_timeout_invalid")
    try:
        response = requests.get(
            base + "/api/bot/content-files/" + delivery_id,
            headers={"Accept": "application/octet-stream", "Authorization": "Bearer " + config.SHARED_API_TOKEN},
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.RequestException:
        raise SharedAPIError(0, "shared_api_unreachable") from None
    if response.status_code < 200 or response.status_code >= 300:
        code = "shared_api_request_failed"
        try:
            body = response.json()
            detail = body.get("detail") if isinstance(body, dict) else None
            if isinstance(detail, str) and detail:
                code = detail[:80]
        except (ValueError, TypeError):
            pass
        raise SharedAPIError(response.status_code, code)
    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    content = response.content
    allowed_types = {
        "application/pdf", "application/epub+zip", "application/zip", "application/x-zip-compressed",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/vnd.ms-powerpoint",
        "image/jpeg", "image/png", "image/webp", "image/gif",
    }
    if content_type not in allowed_types or not content or len(content) > 8 * 1024 * 1024:
        raise SharedAPIError(502, "shared_api_invalid_content_file")
    disposition = response.headers.get("content-disposition", "")
    tokens = [part.strip() for part in disposition.split(";")]
    encoded_token = next((part.split("=", 1)[1].strip() for part in tokens
                          if part.lower().startswith("filename*=")), "")
    plain_token = next((part.split("=", 1)[1].strip().strip('"') for part in tokens
                        if part.lower().startswith("filename=")), "")
    file_name = unquote(encoded_token[7:]) if encoded_token.lower().startswith("utf-8''") else plain_token
    file_name = file_name.replace(chr(92), "/").split("/")[-1]
    file_name = "".join(char for char in file_name if char.isprintable() and char not in {'"', "<", ">"})[:120]
    if not file_name:
        file_name = {
            "application/pdf": "attachment.pdf", "application/epub+zip": "book.epub",
            "application/zip": "attachment.zip", "application/x-zip-compressed": "attachment.zip",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "attachment.docx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": "attachment.pptx",
            "application/vnd.ms-powerpoint": "attachment.ppt",
            "image/jpeg": "attachment.jpg", "image/png": "attachment.png",
            "image/webp": "attachment.webp", "image/gif": "attachment.gif",
        }[content_type]
    return content, content_type, file_name


def submit_workflow(
    bale_user_id: int | str,
    kind: str,
    payload: dict,
    idempotency_key: str,
) -> dict:
    """Store one profile/receipt review task in the shared backend."""
    raw_user_id = _validated_user_id(bale_user_id)
    if kind not in {"profile_review", "receipt_review"} or not isinstance(payload, dict):
        raise SharedAPIError(422, "invalid_workflow_data")
    if not isinstance(idempotency_key, str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,80}", idempotency_key):
        raise SharedAPIError(422, "invalid_idempotency_key")
    result = _request_json(
        "POST",
        "/api/bot/workflows",
        payload={
            "bale_user_id": raw_user_id,
            "kind": kind,
            "payload": payload,
            "idempotency_key": idempotency_key,
        },
    )
    task = _validate_task(result.get("task"))
    if not isinstance(result.get("created"), bool):
        raise SharedAPIError(502, "shared_api_invalid_workflow")
    return {"task": task, "created": result["created"]}


def list_workflows(bale_user_id: int | str, *, limit: int = 50, offset: int = 0) -> dict:
    """Fetch pending manager work from the same queue used by the web app."""
    raw_user_id = _validated_user_id(bale_user_id)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise SharedAPIError(422, "invalid_workflow_limit")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 1_000_000:
        raise SharedAPIError(422, "invalid_workflow_offset")
    result = _request_json(
        "GET",
        "/api/bot/inbox",
        params={"bale_user_id": raw_user_id, "limit": limit, "offset": offset},
    )
    items = result.get("items")
    if not isinstance(items, list) or not isinstance(result.get("has_more"), bool):
        raise SharedAPIError(502, "shared_api_invalid_inbox")
    return {"items": [_validate_task(item) for item in items], "has_more": result["has_more"]}


def decide_workflow(
    task_id: str,
    bale_user_id: int | str,
    decision: str,
    reason: str = "",
    *,
    expected_version: int,
) -> dict:
    """Apply a version-checked task decision under the canonical server role."""
    raw_user_id = _validated_user_id(bale_user_id)
    if not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", task_id):
        raise SharedAPIError(422, "invalid_workflow_id")
    if decision not in {"approved", "rejected"} or not isinstance(reason, str) or len(reason) > 500:
        raise SharedAPIError(422, "invalid_workflow_decision")
    if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 1:
        raise SharedAPIError(422, "invalid_workflow_version")
    result = _request_json(
        "POST",
        f"/api/bot/workflows/{task_id}/decision",
        payload={
            "bale_user_id": raw_user_id,
            "decision": decision,
            "reason": reason,
            "expected_version": expected_version,
        },
    )
    if result.get("accepted") is not True:
        raise SharedAPIError(502, "shared_api_invalid_decision")
    return {"task": _validate_task(result.get("task")), "accepted": True}


def list_workflow_projections(*, limit: int = 50) -> list[dict]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise SharedAPIError(422, "invalid_workflow_limit")
    result = _request_json(
        "GET", "/api/bot/workflows/projection-pending", params={"limit": limit}
    )
    items = result.get("items")
    if not isinstance(items, list):
        raise SharedAPIError(502, "shared_api_invalid_workflows")
    tasks = [_validate_task(item) for item in items]
    if any(task.get("status") not in {"approved", "rejected"} for task in tasks):
        raise SharedAPIError(502, "shared_api_invalid_workflow_projection")
    return tasks


def mark_workflow_projection_applied(task_id: str) -> bool:
    if not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", task_id):
        raise SharedAPIError(422, "invalid_workflow_id")
    result = _request_json("POST", f"/api/bot/workflows/{task_id}/projection-applied")
    if result.get("applied") is not True:
        raise SharedAPIError(502, "shared_api_invalid_projection_ack")
    return True


def mark_workflow_projection_failed(task_id: str) -> str:
    if not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", task_id):
        raise SharedAPIError(422, "invalid_workflow_id")
    result = _request_json("POST", f"/api/bot/workflows/{task_id}/projection-failed")
    status = result.get("projection_status")
    if result.get("recorded") is not True or status not in {"pending", "failed"}:
        raise SharedAPIError(502, "shared_api_invalid_projection_ack")
    return status


def list_notifications(bale_user_id: int | str, *, limit: int = 30) -> list[dict]:
    raw_user_id = _validated_user_id(bale_user_id)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise SharedAPIError(422, "invalid_notification_limit")
    result = _request_json(
        "GET",
        "/api/bot/notifications",
        params={"bale_user_id": raw_user_id, "limit": limit},
    )
    items = result.get("items")
    if not isinstance(items, list):
        raise SharedAPIError(502, "shared_api_invalid_notifications")
    for item in items:
        if (not isinstance(item, dict)
                or not isinstance(item.get("id"), str)
                or not re.fullmatch(r"[0-9a-fA-F-]{36}", item["id"])
                or not isinstance(item.get("title"), str)
                or not isinstance(item.get("body"), str)
                or not isinstance(item.get("file_refs"), list)):
            raise SharedAPIError(502, "shared_api_invalid_notification")
    return items


def _validate_notification(item: object) -> dict:
    if (not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not re.fullmatch(r"[0-9a-fA-F-]{36}", item["id"])
            or not isinstance(item.get("bale_user_id"), str)
            or not _USER_ID.fullmatch(item["bale_user_id"])
            or not isinstance(item.get("title"), str)
            or not isinstance(item.get("body"), str)
            or not isinstance(item.get("file_refs"), list)):
        raise SharedAPIError(502, "shared_api_invalid_notification")
    return item


def list_pending_notifications(*, limit: int = 50) -> list[dict]:
    """Read the durable delivery queue for the bot's provider worker."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise SharedAPIError(422, "invalid_notification_limit")
    result = _request_json(
        "GET", "/api/bot/notifications/pending", params={"limit": limit}
    )
    items = result.get("items")
    if not isinstance(items, list):
        raise SharedAPIError(502, "shared_api_invalid_notifications")
    return [_validate_notification(item) for item in items]


def mark_notification_delivered(notification_id: str, bale_user_id: int | str) -> bool:
    raw_user_id = _validated_user_id(bale_user_id)
    if not isinstance(notification_id, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", notification_id):
        raise SharedAPIError(422, "invalid_notification_id")
    result = _request_json(
        "POST",
        f"/api/bot/notifications/{notification_id}/delivered",
        payload={"bale_user_id": raw_user_id},
    )
    if result.get("delivered") is not True:
        raise SharedAPIError(502, "shared_api_invalid_delivery_ack")
    return True


def mark_notification_failed(notification_id: str, bale_user_id: int | str) -> str:
    raw_user_id = _validated_user_id(bale_user_id)
    if not isinstance(notification_id, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", notification_id):
        raise SharedAPIError(422, "invalid_notification_id")
    result = _request_json(
        "POST",
        f"/api/bot/notifications/{notification_id}/delivery-failed",
        payload={"bale_user_id": raw_user_id},
    )
    status = result.get("delivery_status")
    if result.get("recorded") is not True or status not in {"pending", "failed"}:
        raise SharedAPIError(502, "shared_api_invalid_delivery_ack")
    return status

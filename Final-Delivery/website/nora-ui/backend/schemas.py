"""Validation for the first server-side form-definition contract."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any


MODELS = {
    "registration",
    "questionnaire",
    "survey",
    "election",
    "datacollect",
    "contest",
    "attendance",
    "exam",
    "order",
}
NEED_BY_MODEL = {
    "registration": "reg",
    "questionnaire": "other",
    "survey": "survey",
    "election": "other",
    "datacollect": "other",
    "contest": "exam",
    "attendance": "other",
    "exam": "exam",
    "order": "reg",
}
CONDITION_OPERATORS = {
    "eq", "ne", "contains", "ncontains", "starts", "nstarts", "ends", "nends",
    "gt", "gte", "lt", "lte", "empty", "nempty",
}
CONDITION_VALUE_OPERATORS = CONDITION_OPERATORS - {"empty", "nempty"}
CONDITION_NUMERIC_TYPES = {"number", "amount", "price", "rating", "scale", "bars"}
CONDITION_TEMPORAL_TYPES = {"date", "time", "datetime", "slot"}
CONDITION_CHOICE_TYPES = {"choice", "dropdown", "select", "yesno", "gender", "marital", "imgchoice"}
CONDITION_UPLOAD_TYPES = {"image", "file", "voice", "sign"}
CONDITION_NUMERIC_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte"}
CONDITION_TEXT_OPERATORS = {
    "eq", "ne", "contains", "ncontains", "starts", "nstarts", "ends", "nends", "empty", "nempty"
}
CONDITION_ORDERED_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "empty", "nempty"}
CONDITION_CHOICE_OPERATORS = {"eq", "ne", "empty", "nempty"}
CONDITION_MULTI_OPERATORS = {"contains", "ncontains", "empty", "nempty"}
CONDITION_EMPTY_OPERATORS = {"empty", "nempty"}
OPTION_FIELD_TYPES = {"choice", "dropdown", "select", "multi", "imgchoice", "gender", "marital"}
OPTION_REQUIRED_TYPES = {"choice", "dropdown", "select", "multi", "imgchoice"}
MAX_FIELD_OPTIONS = 100
MAX_OPTION_LABEL = 120
MAX_TICKET_TYPES = 20
MAX_TICKET_TYPE_NAME = 80
TICKET_TYPE_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
# Match String.prototype.trim() in the builder (control characters are rejected before trimming).
OPTION_LABEL_TRIM_CHARS = "".join(chr(codepoint) for codepoint in (
    0x0009, 0x000A, 0x000B, 0x000C, 0x000D, 0x0020, 0x00A0, 0x1680,
    *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F, 0x3000, 0xFEFF,
))
MAX_CONDITION_RULES = 10
DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
SECRET_KEY = re.compile(r"(?:token|secret|authorization|api[_-]?key|password|credential)", re.I)
SLUG_RE = re.compile(r"^[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*$")
TOP_LEVEL_KEYS = {"name", "model", "need", "slug", "ev", "fields", "settings", "expected_version", "purpose", "recording_id"}
# Phase 9.1: what a form is for. ``registration`` is every legacy behaviour; a
# ``recording_access`` form is the purchase entry of one recorded product and its
# settings (fin / payment methods / card) are the product's commercial source of truth.
PURPOSES = ("registration", "recording_access")
RECORDING_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,36}$")


class PayloadError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class NormalizedField:
    key: str
    field_type: str
    label: str
    config: dict[str, Any]


@dataclass(frozen=True)
class FormDefinition:
    title: str
    model: str
    need: str
    slug: str | None
    event_id: str | None
    settings: dict[str, Any]
    fields: list[NormalizedField]
    expected_version: int | None
    purpose: str = "registration"
    recording_id: str | None = None


def _contains_secret_key(value: Any, depth: int = 0) -> bool:
    if depth > 12:
        return True
    if isinstance(value, dict):
        for key, child in value.items():
            if SECRET_KEY.search(str(key)) or _contains_secret_key(child, depth + 1):
                return True
    elif isinstance(value, list):
        return any(_contains_secret_key(child, depth + 1) for child in value)
    return False


def _normalize_purpose(payload: dict[str, Any], model: str, settings: dict[str, Any]) -> tuple[str, str | None]:
    """Validate ``purpose``/``recording_id`` together; a purchase form must stay a plain
    one-person payment form (registration model, no tickets, no companions)."""
    purpose = payload.get("purpose", "registration")
    if not isinstance(purpose, str) or purpose not in PURPOSES:
        raise PayloadError("invalid_purpose", "Unsupported form purpose")
    recording_id = payload.get("recording_id")
    if recording_id is not None:
        if not isinstance(recording_id, str) or not RECORDING_ID_RE.fullmatch(recording_id.strip()):
            raise PayloadError("invalid_recording_reference", "Invalid recorded-product reference")
        recording_id = recording_id.strip()
    if purpose == "registration":
        if recording_id is not None:
            raise PayloadError("recording_requires_purchase_purpose", "Only purchase forms link to a recorded product")
        return purpose, None
    if recording_id is None:
        raise PayloadError("purchase_form_recording_required", "A purchase form must reference one recorded product")
    if model != "registration":
        raise PayloadError(
            "purchase_form_requires_registration_model",
            "Purchase forms use the registration model so server-side payments apply",
        )
    if "ticketing" in settings:
        raise PayloadError("ticketing_not_allowed_for_purchase", "Purchase forms never issue tickets")
    if settings.get("guestsOn") is True:
        raise PayloadError("companions_not_allowed_for_purchase", "Purchase forms are for one account only")
    return purpose, recording_id


def _normalize_ticketing_setting(value: Any, model: str) -> dict[str, Any]:
    if model != "registration":
        raise PayloadError(
            "ticketing_requires_registration",
            "Ticket models are only supported for registration forms",
        )
    if not isinstance(value, dict) or set(value) != {"mode", "types"}:
        raise PayloadError(
            "invalid_ticketing_setting",
            "Ticket settings must contain a mode and ticket type list",
        )
    mode = value.get("mode")
    if not isinstance(mode, str) or mode not in {"single", "random"}:
        raise PayloadError("invalid_ticketing_mode", "Ticket mode must be single or random")
    raw_types = value.get("types")
    if not isinstance(raw_types, list):
        raise PayloadError("invalid_ticket_types", "Ticket types must be a list")
    valid_count = (
        len(raw_types) == 1
        if mode == "single"
        else 2 <= len(raw_types) <= MAX_TICKET_TYPES
    )
    if not valid_count:
        raise PayloadError(
            "invalid_ticket_type_count",
            "Ticket mode has an invalid number of types",
        )

    types: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    for item in raw_types:
        if not isinstance(item, dict) or set(item) != {"id", "name"}:
            raise PayloadError(
                "invalid_ticket_type",
                "Each ticket type must contain only an id and name",
            )
        raw_id = item.get("id")
        if not isinstance(raw_id, str):
            raise PayloadError("invalid_ticket_type_id", "Each ticket type needs a valid id")
        ticket_id = raw_id.strip()
        if not TICKET_TYPE_ID.fullmatch(ticket_id):
            raise PayloadError(
                "invalid_ticket_type_id",
                "Ticket type ids may contain only letters, numbers, underscores, and hyphens",
            )
        if ticket_id in seen_ids:
            raise PayloadError("duplicate_ticket_type_id", "Ticket type ids must be unique")
        seen_ids.add(ticket_id)

        raw_name = item.get("name")
        if not isinstance(raw_name, str) or any(
            unicodedata.category(char) in {"Cc", "Cs"} for char in raw_name
        ):
            raise PayloadError(
                "invalid_ticket_type_name",
                "Ticket type names must be printable text",
            )
        name = " ".join(raw_name.split())
        if not 1 <= len(name) <= MAX_TICKET_TYPE_NAME:
            raise PayloadError(
                "invalid_ticket_type_name",
                "Ticket type names must contain 1 to 80 characters",
            )
        identity = unicodedata.normalize("NFKC", name).casefold()
        if identity in seen_names:
            raise PayloadError("duplicate_ticket_type_name", "Ticket type names must be unique")
        seen_names.add(identity)
        types.append({"id": ticket_id, "name": name})
    return {"mode": mode, "types": types}


def _condition_operators_for(field_type: str) -> set[str]:

    if field_type in CONDITION_NUMERIC_TYPES:
        return CONDITION_NUMERIC_OPERATORS | CONDITION_EMPTY_OPERATORS
    if field_type in CONDITION_TEMPORAL_TYPES:
        return CONDITION_ORDERED_OPERATORS
    if field_type == "multi":
        return CONDITION_MULTI_OPERATORS
    if field_type in CONDITION_CHOICE_TYPES:
        return CONDITION_CHOICE_OPERATORS
    if field_type == "terms" or field_type in CONDITION_UPLOAD_TYPES:
        return CONDITION_EMPTY_OPERATORS
    return CONDITION_TEXT_OPERATORS


def _condition_options(raw_field: dict[str, Any], field_type: str) -> set[str]:
    options = raw_field.get("opts", raw_field.get("options", []))
    if not isinstance(options, list):
        options = []
    labels = {
        str(item.get("l", "")).strip() if isinstance(item, dict) else str(item).strip()
        for item in options
    }
    fixed = {
        "gender": {"زن", "مرد"},
        "marital": {"مجرد", "متأهل"},
        "yesno": {"بله", "خیر"},
    }
    return {label for label in labels if label} or fixed.get(field_type, set())


def _valid_condition_number(value: str) -> bool:
    normalized = value.translate(DIGIT_TRANSLATION).replace("٫", ".")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", normalized):
        return False
    try:
        return math.isfinite(float(normalized))
    except ValueError:
        return False


def _valid_condition_temporal(value: str, field_type: str) -> bool:
    normalized = value.translate(DIGIT_TRANSLATION).strip()
    if field_type in {"time", "slot"}:
        match = re.fullmatch(r"(\d{1,2}):(\d{2})", normalized)
        return bool(match and 0 <= int(match.group(1)) <= 23 and 0 <= int(match.group(2)) <= 59)
    if field_type == "date":
        match = re.fullmatch(r"(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})", normalized)
    else:
        match = re.fullmatch(
            r"(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})\s*(?:ساعت\s*)?(\d{1,2}):(\d{2})",
            normalized,
        )
    if not match:
        return False
    groups = [int(part) for part in match.groups()]
    year, month, day = groups[:3]
    if not 1 <= month <= 12:
        return False
    max_day = 31 if month <= 6 else 30 if month <= 11 else (
        30 if year in {1399, 1403, 1408, 1412} else 29
    )
    if not 1 <= day <= max_day:
        return False
    if field_type != "date":
        hour, minute = groups[3:]
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            return False
    return True


def normalize_form_payload(
    payload: Any, *, max_fields: int, updating: bool = False
) -> FormDefinition:
    if not isinstance(payload, dict):
        raise PayloadError("invalid_object", "Body must be a JSON object")
    unexpected = set(payload) - TOP_LEVEL_KEYS
    if unexpected:
        raise PayloadError("unexpected_fields", "Unexpected top-level form fields")
    if _contains_secret_key(payload):
        raise PayloadError("credentials_not_accepted", "Credentials are not accepted in form data")

    title = payload.get("name")
    if not isinstance(title, str):
        raise PayloadError("invalid_title", "Form name is required")
    title = " ".join(title.split())
    if not 3 <= len(title) <= 160:
        raise PayloadError("invalid_title", "Form name must contain 3 to 160 characters")

    model = payload.get("model")
    if not isinstance(model, str) or model not in MODELS:
        raise PayloadError("invalid_model", "Unsupported form model")
    canonical_need = NEED_BY_MODEL[model]
    need = payload.get("need", canonical_need)
    if need != canonical_need:
        raise PayloadError("model_need_mismatch", "Form type does not match its model")

    slug = payload.get("slug")
    if slug is not None:
        if not isinstance(slug, str):
            raise PayloadError("invalid_slug", "Form path must be text")
        slug = slug.strip().strip("/")
        if slug and (len(slug) > 180 or not SLUG_RE.fullmatch(slug) or ".." in slug):
            raise PayloadError("invalid_slug", "Only a local path is allowed")
        slug = slug or None

    event_id = payload.get("ev")
    if event_id is not None:
        if not isinstance(event_id, str) or len(event_id.strip()) > 120:
            raise PayloadError("invalid_event", "Invalid event reference")
        event_id = event_id.strip() or None

    settings = payload.get("settings", {})
    if not isinstance(settings, dict):
        raise PayloadError("invalid_settings", "Form settings must be an object")
    settings = dict(settings)
    if any(key in settings for key in ("status", "owner_id", "published", "is_published")):
        raise PayloadError("server_owned_setting", "Status and ownership are server-controlled")
    purpose, recording_id = _normalize_purpose(payload, model, settings)
    if "ticketing" in settings:
        settings["ticketing"] = _normalize_ticketing_setting(settings["ticketing"], model)

    raw_fields = payload.get("fields")
    if not isinstance(raw_fields, list) or not 1 <= len(raw_fields) <= max_fields:
        raise PayloadError("invalid_field_count", f"A form must contain 1 to {max_fields} fields")

    fields: list[NormalizedField] = []
    seen: set[str] = set()
    seen_fields: dict[str, dict[str, Any]] = {}
    for raw in raw_fields:
        if not isinstance(raw, dict):
            raise PayloadError("invalid_field", "Each field must be an object")
        if _contains_secret_key(raw):
            raise PayloadError("credentials_not_accepted", "Credentials are not accepted in fields")
        raw_id = raw.get("id")
        if isinstance(raw_id, bool) or not isinstance(raw_id, (str, int)):
            raise PayloadError("invalid_field_id", "Each field needs a text or numeric id")
        field_key = str(raw_id).strip()
        if not 1 <= len(field_key) <= 80:
            raise PayloadError("invalid_field_id", "Field id must contain 1 to 80 characters")
        if field_key in seen:
            raise PayloadError("duplicate_field_id", "Field ids must be unique within a form")
        seen.add(field_key)

        field_type = raw.get("t")
        if not isinstance(field_type, str) or not 1 <= len(field_type.strip()) <= 48:
            raise PayloadError("invalid_field_type", "Each field needs a type")
        field_type = field_type.strip()

        label = raw.get("l")
        if not isinstance(label, str):
            raise PayloadError("invalid_field_label", "Each field needs a label")
        label = " ".join(label.split())
        if not 1 <= len(label) <= 160:
            raise PayloadError("invalid_field_label", "Field label must contain 1 to 160 characters")

        option_labels: list[str] = []
        option_key = "opts" if "opts" in raw else "options"
        if field_type in OPTION_FIELD_TYPES:
            raw_options = raw.get(option_key, [])
            if not isinstance(raw_options, list):
                raise PayloadError("invalid_options", "Field options must be a list")
            if len(raw_options) > MAX_FIELD_OPTIONS:
                raise PayloadError("too_many_options", f"A field may have at most {MAX_FIELD_OPTIONS} options")
            normalized_options: list[Any] = []
            option_keys: set[str] = set()
            for option in raw_options:
                label_value = option.get("l") if isinstance(option, dict) else option
                if not isinstance(label_value, str):
                    raise PayloadError("invalid_option", "Each option needs a text label")
                if any(unicodedata.category(char) in {"Cc", "Cs"} for char in label_value):
                    raise PayloadError(
                        "invalid_option", f"Option labels must contain 1 to {MAX_OPTION_LABEL} printable characters"
                    )
                option_label = label_value.strip(OPTION_LABEL_TRIM_CHARS)
                if not option_label or len(option_label) > MAX_OPTION_LABEL:
                    raise PayloadError(
                        "invalid_option", f"Option labels must contain 1 to {MAX_OPTION_LABEL} printable characters"
                    )
                option_identity = unicodedata.normalize("NFKC", option_label).casefold()
                if option_identity in option_keys:
                    raise PayloadError("duplicate_option", "Option labels must be unique")
                option_keys.add(option_identity)
                option_labels.append(option_label)
                if isinstance(option, dict):
                    normalized = dict(option)
                    normalized["l"] = option_label
                    normalized_options.append(normalized)
                else:
                    normalized_options.append(option_label)
            if field_type in OPTION_REQUIRED_TYPES and not option_labels:
                raise PayloadError("options_required", "This field type needs at least one option")
            if option_key in raw:
                raw[option_key] = normalized_options

        if field_type == "multi":
            limits: dict[str, int | None] = {}
            for key in ("minSelect", "maxSelect"):
                value = raw.get(key)
                if value is None or value == "":
                    limits[key] = None
                elif isinstance(value, bool) or not isinstance(value, int) or value < 1:
                    raise PayloadError("invalid_selection_limits", "Selection limits must be positive integers")
                elif value > len(option_labels):
                    raise PayloadError("invalid_selection_limits", "Selection limits cannot exceed available options")
                else:
                    limits[key] = value
            if limits["minSelect"] is not None and limits["maxSelect"] is not None and limits["minSelect"] > limits["maxSelect"]:
                raise PayloadError("invalid_selection_limits", "Minimum selections cannot exceed maximum selections")
            raw.update(limits)
        elif any(raw.get(key) not in (None, "") for key in ("minSelect", "maxSelect")):
            raise PayloadError("invalid_selection_limits", "Selection limits are only valid for multi-select fields")

        raw_conditions = raw.get("conditions")
        if raw_conditions is not None and not isinstance(raw_conditions, list):
            raise PayloadError("invalid_condition_rules", "Conditions must be a list")
        raw_condition_field = raw.get("condField", raw.get("cond_field", ""))
        if raw_condition_field is None:
            raw_condition_field = ""
        if isinstance(raw_condition_field, bool) or not isinstance(raw_condition_field, (str, int)):
            raise PayloadError("invalid_condition_field", "Condition reference must be a field id")
        legacy_field = str(raw_condition_field).strip()
        raw_rules = list(raw_conditions or [])
        if not raw_rules and legacy_field:
            raw_rules = [{
                "field": legacy_field,
                "op": raw.get("condOp", raw.get("cond_op", "eq")),
                "value": raw.get("condVal", raw.get("cond_val", "")),
            }]
        logic = raw.get("conditionLogic", raw.get("condLogic", "all"))
        if raw_rules and (not isinstance(logic, str) or logic not in {"all", "any"}):
            raise PayloadError("invalid_condition_logic", "Condition logic must be all or any")
        if len(raw_rules) > MAX_CONDITION_RULES:
            raise PayloadError(
                "too_many_condition_rules",
                f"A field may have at most {MAX_CONDITION_RULES} conditions",
            )

        conditions: list[dict[str, str]] = []
        for rule in raw_rules:
            if not isinstance(rule, dict):
                raise PayloadError("invalid_condition_rule", "Each condition must be an object")
            raw_reference = rule.get("field", rule.get("fieldId", rule.get("condField", "")))
            if isinstance(raw_reference, bool) or not isinstance(raw_reference, (str, int)):
                raise PayloadError("invalid_condition_field", "Condition reference must be a field id")
            reference = str(raw_reference).strip()
            if not reference or reference not in seen_fields:
                raise PayloadError("invalid_condition_order", "A condition must refer to an earlier field")
            operator = rule.get("op", rule.get("operator", rule.get("condOp", "eq")))
            source = seen_fields[reference]
            allowed_operators = _condition_operators_for(source["type"])
            if not isinstance(operator, str) or operator not in allowed_operators:
                raise PayloadError(
                    "invalid_condition_operator",
                    "Operator is not supported for the referenced field type",
                )

            raw_value = rule.get("value", rule.get("condVal", ""))
            if raw_value is None:
                raw_value = ""
            if isinstance(raw_value, bool) or not isinstance(raw_value, (str, int, float)):
                raise PayloadError("invalid_condition_value", "Condition value must be text or a number")
            value = str(raw_value).strip() if operator in CONDITION_VALUE_OPERATORS else ""
            if len(value) > 120:
                raise PayloadError("invalid_condition_value", "Condition value must be at most 120 characters")
            if operator in CONDITION_VALUE_OPERATORS and not value:
                raise PayloadError("invalid_condition_value", "This operator requires a comparison value")
            source_type = source["type"]
            if (
                source_type in CONDITION_NUMERIC_TYPES
                and operator in CONDITION_NUMERIC_OPERATORS
                and not _valid_condition_number(value)
            ):
                raise PayloadError("invalid_condition_value", "A numeric condition requires a valid number")
            if (
                source_type in CONDITION_TEMPORAL_TYPES
                and operator in CONDITION_VALUE_OPERATORS
                and not _valid_condition_temporal(value, source_type)
            ):
                raise PayloadError("invalid_condition_value", "A date or time condition requires a valid value")
            options = _condition_options(source["raw"], source_type)
            if (
                source_type in CONDITION_CHOICE_TYPES | {"multi"}
                and options
                and operator in CONDITION_VALUE_OPERATORS
                and value not in options
            ):
                raise PayloadError(
                    "invalid_condition_value",
                    "Condition value must match a choice in the referenced field",
                )
            conditions.append({"field": reference, "op": operator, "value": value})

        config = {
            key: value
            for key, value in raw.items()
            if key not in {"id", "t", "l", "cond_field", "cond_op", "cond_val", "condLogic"}
        }
        condition_aliases = (
            "condField", "cond_field", "condOp", "cond_op", "condVal", "cond_val", "conditionLogic", "condLogic"
        )
        has_condition_config = raw_conditions is not None or any(key in raw for key in condition_aliases)
        if has_condition_config:
            normalized_logic = logic if len(conditions) > 1 else "all"
            config["conditions"] = conditions
            config["conditionLogic"] = normalized_logic
            if len(conditions) == 1:
                config["condField"] = conditions[0]["field"]
                config["condOp"] = conditions[0]["op"]
                config["condVal"] = conditions[0]["value"]
            else:
                config["condField"] = ""
                config["condOp"] = "eq"
                config["condVal"] = ""
        try:
            json.dumps(config, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError):
            raise PayloadError("invalid_field_config", "Field settings must be JSON values") from None
        fields.append(NormalizedField(field_key, field_type, label, config))
        seen_fields[field_key] = {"type": field_type, "raw": raw}

    try:
        json.dumps(settings, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise PayloadError("invalid_settings", "Form settings must be JSON values") from None

    expected_version: int | None = None
    if updating:
        raw_version = payload.get("expected_version")
        if isinstance(raw_version, bool) or not isinstance(raw_version, int) or raw_version < 1:
            raise PayloadError("version_required", "expected_version is required when updating a form")
        expected_version = raw_version
    elif "expected_version" in payload:
        raise PayloadError("unexpected_version", "expected_version is only used when updating")

    return FormDefinition(
        title=title,
        model=model,
        need=canonical_need,
        slug=slug,
        event_id=event_id,
        settings=settings,
        fields=fields,
        expected_version=expected_version,
        purpose=purpose,
        recording_id=recording_id,
    )

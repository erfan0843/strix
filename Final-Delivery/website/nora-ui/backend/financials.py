"""Server-side pricing and payment-method validation for public forms."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from typing import Any


PAYMENT_METHODS = {"card_transfer", "bale_wallet"}
MAX_FINANCIAL_ITEMS = 20
MAX_FINANCIAL_GROUPS = 10
MAX_PAYMENT_AMOUNT = 2_000_000_000


class PaymentConfigurationError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _integer(value: Any, *, minimum: int = 0, maximum: int = MAX_PAYMENT_AMOUNT) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        return None
    return value


def _clean_text(value: Any, maximum: int, *, required: bool = False) -> str | None:
    if not isinstance(value, str):
        return None if required else ""
    if any(unicodedata.category(char) in {"Cc", "Cs"} for char in value):
        return None
    cleaned = " ".join(value.split()).strip()
    if (required and not cleaned) or len(cleaned) > maximum:
        return None
    return cleaned


def normalize_payment_methods(settings: dict[str, Any]) -> list[str]:
    """Return creator-selected built-in methods; never infer a provider from UI state."""
    raw = settings.get("enabledPaymentMethods")
    if raw is None:
        # Compatibility for existing manually-reviewed card forms.
        return ["card_transfer"] if settings.get("receiptReviewRequired") is True else []
    if not isinstance(raw, list) or len(raw) > len(PAYMENT_METHODS):
        raise PaymentConfigurationError("invalid_payment_methods")
    result: list[str] = []
    for item in raw:
        if not isinstance(item, str) or item not in PAYMENT_METHODS or item in result:
            raise PaymentConfigurationError("invalid_payment_methods")
        result.append(item)
    return result


def normalize_financial_config(settings: dict[str, Any]) -> dict[str, Any]:
    """Validate and return the public, non-secret portion of a form's prices."""
    raw_items = settings.get("fin", [])
    if not isinstance(raw_items, list) or len(raw_items) > MAX_FINANCIAL_ITEMS:
        raise PaymentConfigurationError("invalid_financial_items")
    items: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise PaymentConfigurationError("invalid_financial_item")
        label = _clean_text(item.get("l"), 120, required=True)
        amount = _integer(item.get("p"))
        discount = _integer(item.get("off", 0), maximum=100)
        required = item.get("req", False)
        description = _clean_text(item.get("d", ""), 400)
        group = item.get("g")
        if group is not None:
            group = _clean_text(group, 80, required=True)
        if (
            label is None or amount is None or discount is None
            or not isinstance(required, bool) or description is None
            or group is None and item.get("g") not in (None, "")
        ):
            raise PaymentConfigurationError("invalid_financial_item")
        discounted = (amount * (100 - discount) + 50) // 100
        if discounted > MAX_PAYMENT_AMOUNT:
            raise PaymentConfigurationError("financial_amount_too_large")
        items.append({
            "l": label,
            "p": amount,
            "off": discount,
            "req": required,
            "d": description,
            "g": group or None,
        })

    raw_groups = settings.get("groups", [])
    if not isinstance(raw_groups, list) or len(raw_groups) > MAX_FINANCIAL_GROUPS:
        raise PaymentConfigurationError("invalid_financial_groups")
    groups: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for group in raw_groups:
        if not isinstance(group, dict):
            raise PaymentConfigurationError("invalid_financial_group")
        name = _clean_text(group.get("n"), 80, required=True)
        members = group.get("of")
        required = group.get("req", False)
        one = group.get("one", True)
        if (
            name is None or not isinstance(members, list) or not 2 <= len(members) <= MAX_FINANCIAL_ITEMS
            or not isinstance(required, bool) or not isinstance(one, bool)
            or name.casefold() in seen_names
        ):
            raise PaymentConfigurationError("invalid_financial_group")
        normalized_members: list[int] = []
        for index in members:
            parsed = _integer(index, maximum=max(0, len(items) - 1))
            if parsed is None or parsed in normalized_members or parsed >= len(items):
                raise PaymentConfigurationError("invalid_financial_group")
            normalized_members.append(parsed)
        if len(normalized_members) < 2:
            raise PaymentConfigurationError("invalid_financial_group")
        seen_names.add(name.casefold())
        groups.append({"n": name, "of": normalized_members, "req": required, "one": one})

    # Reject inconsistent cross-references and duplicate group ownership.
    claimed: dict[int, str] = {}
    for group in groups:
        for index in group["of"]:
            if index in claimed:
                raise PaymentConfigurationError("financial_item_in_multiple_groups")
            claimed[index] = group["n"]
            if items[index]["g"] not in (None, group["n"]):
                raise PaymentConfigurationError("financial_group_mismatch")
    for index, item in enumerate(items):
        if item["g"] is not None and claimed.get(index) != item["g"]:
            raise PaymentConfigurationError("financial_group_mismatch")

    raw_coupon = settings.get("coupon", {})
    if raw_coupon is None:
        raw_coupon = {}
    if not isinstance(raw_coupon, dict):
        raise PaymentConfigurationError("invalid_coupon")
    coupon_code = _clean_text(raw_coupon.get("code", ""), 64)
    coupon_discount = _integer(raw_coupon.get("off", 0), maximum=100)
    coupon_all = raw_coupon.get("all", False)
    if coupon_code is None or coupon_discount is None or not isinstance(coupon_all, bool):
        raise PaymentConfigurationError("invalid_coupon")
    coupon = {"code": coupon_code, "off": coupon_discount, "all": coupon_all}
    return {"fin": items, "groups": groups, "coupon": coupon}


def payment_configuration_issues(settings: dict[str, Any], *, bale_ready: bool) -> list[str]:
    """Validate payment settings that are part of the saved, creator-authored form."""
    issues: list[str] = []
    try:
        methods = normalize_payment_methods(settings)
        financial = normalize_financial_config(settings)
    except PaymentConfigurationError as error:
        return [error.code]

    has_financial_items = bool(financial["fin"])
    if has_financial_items and not methods:
        issues.append("payment_method_required")
    if methods and not has_financial_items:
        issues.append("payment_amount_required")
    if methods and not any(item["p"] > 0 for item in financial["fin"]):
        issues.append("payment_amount_required")

    receipt_enabled = settings.get("receiptReviewRequired", False)
    if not isinstance(receipt_enabled, bool):
        issues.append("invalid_receipt_review_setting")
    if "card_transfer" in methods:
        if receipt_enabled is not True:
            issues.append("card_transfer_receipt_required")
    elif receipt_enabled is True and settings.get("enabledPaymentMethods") is not None:
        issues.append("card_transfer_not_selected")

    if "bale_wallet" in methods and not bale_ready:
        issues.append("bale_payment_not_configured")
    return issues


def public_payment_configuration(settings: dict[str, Any], *, bale_ready: bool) -> dict[str, Any]:
    """Only public prices and the methods enabled by the form creator are exposed."""
    financial = normalize_financial_config(settings)
    methods = normalize_payment_methods(settings)
    available = [method for method in methods if method != "bale_wallet" or bale_ready]
    return {
        **financial,
        "enabledPaymentMethods": available,
        "receiptUploadRequired": "card_transfer" in available and settings.get("receiptReviewRequired") is True,
    }


def calculate_payment_amount(
    settings: dict[str, Any], selection: Any, *, party_count: int
) -> dict[str, Any]:
    """Calculate the payable amount solely from saved form prices and selected indexes."""
    financial = normalize_financial_config(settings)
    if not isinstance(selection, dict) or set(selection) - {"items", "coupon_code"}:
        raise PaymentConfigurationError("invalid_payment_selection")
    indexes = selection.get("items")
    if not isinstance(indexes, list) or len(indexes) > len(financial["fin"]):
        raise PaymentConfigurationError("invalid_payment_selection")
    selected: list[int] = []
    for index in indexes:
        parsed = _integer(index, maximum=max(0, len(financial["fin"]) - 1))
        if parsed is None or parsed >= len(financial["fin"]) or parsed in selected:
            raise PaymentConfigurationError("invalid_payment_selection")
        selected.append(parsed)
    for index, item in enumerate(financial["fin"]):
        if item["req"] and index not in selected:
            raise PaymentConfigurationError("required_financial_item_missing")
    for group in financial["groups"]:
        selected_in_group = [index for index in group["of"] if index in selected]
        if group["req"] and not selected_in_group:
            raise PaymentConfigurationError("required_financial_group_missing")
        if group["one"] and len(selected_in_group) > 1:
            raise PaymentConfigurationError("financial_group_selection_invalid")

    if isinstance(party_count, bool) or not isinstance(party_count, int) or not 1 <= party_count <= 10:
        raise PaymentConfigurationError("invalid_payment_party_count")
    line_items = []
    per_person = 0
    for index in selected:
        item = financial["fin"][index]
        amount = (item["p"] * (100 - item["off"]) + 50) // 100
        per_person += amount
        line_items.append({"index": index, "name": item["l"], "amount": amount})
    subtotal = per_person * party_count
    if subtotal > MAX_PAYMENT_AMOUNT:
        raise PaymentConfigurationError("payment_amount_too_large")

    raw_code = selection.get("coupon_code", "")
    if not isinstance(raw_code, str) or len(raw_code) > 64:
        raise PaymentConfigurationError("invalid_coupon_code")
    normalized_code = unicodedata.normalize("NFKC", raw_code).strip().casefold()
    configured_code = unicodedata.normalize("NFKC", financial["coupon"]["code"]).strip().casefold()
    discount_percent = (
        financial["coupon"]["off"]
        if configured_code and normalized_code == configured_code
        else 0
    )
    eligible = subtotal if financial["coupon"]["all"] else per_person
    discount_amount = min(subtotal, (eligible * discount_percent + 50) // 100)
    amount = subtotal - discount_amount
    if amount <= 0:
        raise PaymentConfigurationError("payment_amount_must_be_positive")
    if amount > MAX_PAYMENT_AMOUNT:
        raise PaymentConfigurationError("payment_amount_too_large")
    return {
        "amount": amount,
        "currency": "IRR",
        "party_count": party_count,
        "items": line_items,
        "subtotal": subtotal,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "coupon_applied": discount_percent > 0,
    }

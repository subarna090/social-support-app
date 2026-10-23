"""Field validation rules for an application (FR-002) and Emirates ID normalisation (R5).

Messages here are the user-facing messages from contracts/api.md.
"""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

MSG_FULL_NAME = "Full name must be between 2 and 100 characters."
MSG_EMIRATES_ID = "Emirates ID must be 15 digits in the format 784-YYYY-NNNNNNN-N."
MSG_FAMILY_SIZE = "Family size must be a whole number from 1 to 20."
MSG_INCOME = (
    "Net monthly income must be a number from 0 to 1,000,000 AED with at most 2 decimal places."
)

FAMILY_SIZE_MIN, FAMILY_SIZE_MAX = 1, 20
INCOME_MIN, INCOME_MAX = Decimal("0"), Decimal("1000000")

_EMIRATES_ID_DIGITS = re.compile(r"^784(\d{4})\d{8}$")


@dataclass(frozen=True)
class FieldError:
    field: str
    message: str


def normalise_emirates_id(raw: str | None) -> str | None:
    """Return the canonical ``784-YYYY-NNNNNNN-N`` form, or None if the value is invalid."""
    if not isinstance(raw, str):
        return None
    digits = re.sub(r"[\s-]", "", raw)
    match = _EMIRATES_ID_DIGITS.match(digits)
    if not match or not 1900 <= int(match.group(1)) <= date.today().year:
        return None
    return f"{digits[:3]}-{digits[3:7]}-{digits[7:14]}-{digits[14]}"


def validate_full_name(value: str | None) -> list[FieldError]:
    if not isinstance(value, str) or not 2 <= len(value.strip()) <= 100:
        return [FieldError("full_name", MSG_FULL_NAME)]
    return []


def validate_emirates_id(value: str | None) -> list[FieldError]:
    if normalise_emirates_id(value) is None:
        return [FieldError("emirates_id", MSG_EMIRATES_ID)]
    return []


def validate_family_size(value: object) -> list[FieldError]:
    is_int = isinstance(value, int) and not isinstance(value, bool)
    if not is_int or not FAMILY_SIZE_MIN <= value <= FAMILY_SIZE_MAX:
        return [FieldError("family_size", MSG_FAMILY_SIZE)]
    return []


def validate_income(value: Decimal | None) -> list[FieldError]:
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or not INCOME_MIN <= value <= INCOME_MAX
        or value.as_tuple().exponent < -2
    ):
        return [FieldError("net_monthly_income_aed", MSG_INCOME)]
    return []

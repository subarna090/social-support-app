"""T007: field validation and Emirates ID normalisation (FR-002, FR-003, research R5)."""

from datetime import date
from decimal import Decimal

import pytest

from social_support.domain.validation import (
    MSG_EMIRATES_ID,
    MSG_FAMILY_SIZE,
    MSG_FULL_NAME,
    MSG_INCOME,
    normalise_emirates_id,
    validate_emirates_id,
    validate_family_size,
    validate_full_name,
    validate_income,
)


class TestEmiratesId:
    @pytest.mark.parametrize(
        "raw",
        ["784-1990-1234567-1", "784199012345671", " 784 1990 1234567 1 ", "784-1990 1234567-1"],
    )
    def test_accepts_dashes_spaces_or_neither_and_normalises(self, raw):
        assert normalise_emirates_id(raw) == "784-1990-1234567-1"
        assert validate_emirates_id(raw) == []

    @pytest.mark.parametrize(
        "raw",
        [
            "785-1990-1234567-1",  # wrong prefix
            "784-1990-123456-1",  # 14 digits
            "784-1990-12345678-1",  # 16 digits
            "784-1990-12345A7-1",  # non-digit
            "784-1899-1234567-1",  # year before 1900
            f"784-{date.today().year + 1}-1234567-1",  # future year
            "",
            "123-45",
        ],
    )
    def test_rejects_invalid(self, raw):
        errors = validate_emirates_id(raw)
        assert [(e.field, e.message) for e in errors] == [("emirates_id", MSG_EMIRATES_ID)]
        assert normalise_emirates_id(raw) is None

    def test_message_matches_contract(self):
        assert MSG_EMIRATES_ID == (
            "Emirates ID must be 15 digits in the format 784-YYYY-NNNNNNN-N."
        )


class TestFullName:
    @pytest.mark.parametrize("name", ["Al", "Aisha Al Mansoori", "x" * 100, "  Omar  "])
    def test_accepts_2_to_100_chars_after_trimming(self, name):
        assert validate_full_name(name) == []

    @pytest.mark.parametrize("name", ["", "A", "  A  ", "x" * 101, "   "])
    def test_rejects_outside_range(self, name):
        assert [(e.field, e.message) for e in validate_full_name(name)] == [
            ("full_name", MSG_FULL_NAME)
        ]


class TestFamilySize:
    @pytest.mark.parametrize("size", [1, 4, 20])
    def test_accepts_whole_number_1_to_20(self, size):
        assert validate_family_size(size) == []

    @pytest.mark.parametrize("size", [0, -1, 21, 2.5, "3", None, True])
    def test_rejects_others(self, size):
        assert [(e.field, e.message) for e in validate_family_size(size)] == [
            ("family_size", MSG_FAMILY_SIZE)
        ]

    def test_message_matches_contract(self):
        assert MSG_FAMILY_SIZE == "Family size must be a whole number from 1 to 20."


class TestIncome:
    @pytest.mark.parametrize(
        "income", [Decimal("0"), Decimal("0.00"), Decimal("6000.5"), Decimal("1000000.00")]
    )
    def test_accepts_0_to_1m_with_at_most_2_dp(self, income):
        assert validate_income(income) == []

    @pytest.mark.parametrize(
        "income",
        [Decimal("-0.01"), Decimal("1000000.01"), Decimal("100.123"), None, Decimal("NaN")],
    )
    def test_rejects_others(self, income):
        assert [(e.field, e.message) for e in validate_income(income)] == [
            ("net_monthly_income_aed", MSG_INCOME)
        ]

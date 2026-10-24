"""T021: application reference numbers (FR-004, research R4)."""

import re

from social_support.services.reference import generate_reference

PATTERN = re.compile(r"^SSA-[0-9A-HJKMNP-TV-Z]{10}$")


def test_format_is_crockford_base32_without_ambiguous_letters():
    for _ in range(200):
        assert PATTERN.fullmatch(generate_reference())


def test_1000_references_are_unique():
    assert len({generate_reference() for _ in range(1000)}) == 1000

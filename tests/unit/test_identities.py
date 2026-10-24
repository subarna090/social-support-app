"""T009: synthetic identities (research R6, FR-016)."""

import random
import re

from social_support.domain.validation import validate_emirates_id
from social_support.synthetic.identities import (
    IdentityFactory,
    emirates_id,
    load_reference_data,
    luhn_check_digit,
)

ID_PATTERN = re.compile(r"784-(\d{4})-00(\d{5})-(\d)")


def test_emirates_id_uses_birth_year_and_pack_index():
    assert emirates_id(1990, 1) == "784-1990-0000001-0"
    match = ID_PATTERN.fullmatch(emirates_id(1985, 4321))
    assert match and match.group(1) == "1985" and match.group(2) == "04321"


def test_emirates_id_check_digit_is_luhn():
    for index in (1, 2, 99, 4999, 5000):
        number = emirates_id(1977, index)
        digits = number.replace("-", "")
        assert int(digits[-1]) == luhn_check_digit(digits[:-1])
        assert _luhn_valid(digits)


def test_emirates_ids_pass_the_application_validator():
    for index in range(1, 50):
        assert validate_emirates_id(emirates_id(1960 + index % 40, index)) == []


def test_emirates_ids_are_unique_per_pack_and_independent_of_other_packs():
    ids = {emirates_id(1990, index) for index in range(1, 5001)}
    assert len(ids) == 5000
    assert emirates_id(1990, 7) == emirates_id(1990, 7)  # stateless: no "used numbers" tracking


def test_contacts_use_reserved_patterns():
    factory = IdentityFactory(random.Random(1))
    for _ in range(50):
        person = factory.person()
        assert person.email.endswith("@example.com")
        assert re.fullmatch(r"\+971 50 000 \d{4}", person.phone)
        assert person.full_name.strip() and person.nationality and person.gender in {"M", "F"}


def test_addresses_use_fictional_districts():
    factory = IdentityFactory(random.Random(2))
    reference = load_reference_data()
    for _ in range(50):
        address = factory.address()
        assert address.district in reference["districts"]
        assert address.emirate in reference["emirates"]


def test_employers_and_organisations_are_marked_demo():
    reference = load_reference_data()
    assert all("(Demo)" in employer for employer in reference["employers"])
    assert "Demo" in reference["bank_name"] and "Demo" in reference["bureau_name"]


def test_same_seed_gives_same_identities():
    def sample(seed):
        factory = IdentityFactory(random.Random(seed))
        return [
            (p.full_name, p.email, p.phone, factory.address())
            for p in (factory.person() for _ in range(10))
        ]

    assert sample(42) == sample(42)
    assert sample(42) != sample(43)


def _luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0

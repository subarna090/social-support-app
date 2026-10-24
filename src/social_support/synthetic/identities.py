"""Synthetic identities: names, reserved-block Emirates IDs, addresses and contacts (research R6).

Every value is fictional and recognisable as synthetic: Emirates ID serials start with ``00`` and
come from the pack index, emails use ``example.com`` and phones ``+971 50 000 NNNN``.
"""

import random
import re
import tomllib
from dataclasses import dataclass
from functools import cache
from importlib import resources

from faker import Faker


@cache
def load_reference_data() -> dict:
    text = (resources.files("social_support.synthetic") / "data" / "names.toml").read_text(
        encoding="utf-8"
    )
    data = tomllib.loads(text)
    return {**{k: v for k, v in data.items() if k != "lists"}, **data["lists"]}


@cache
def _faker(locale: str) -> Faker:
    return Faker(locale)


def luhn_check_digit(payload: str) -> int:
    total = 0
    for i, ch in enumerate(reversed(payload)):
        n = int(ch)
        if i % 2 == 0:  # these positions are doubled once the check digit is appended
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return (10 - total % 10) % 10


def format_emirates_id(digits: str) -> str:
    return f"{digits[:3]}-{digits[3:7]}-{digits[7:14]}-{digits[14]}"


def emirates_id(birth_year: int, pack_index: int) -> str:
    """``784-YYYY-00NNNNN-C``: the serial is the pack index, so IDs are unique within a run
    without tracking state, and pack *i* never depends on other packs (research R5, R6)."""
    if not 1 <= pack_index <= 99_999:
        raise ValueError("pack_index must be between 1 and 99999")
    payload = f"784{birth_year:04d}00{pack_index:05d}"
    return format_emirates_id(payload + str(luhn_check_digit(payload)))


@dataclass(frozen=True)
class Person:
    full_name: str
    given_name: str
    family_name: str
    gender: str  # "M" or "F"
    nationality: str
    email: str
    phone: str


@dataclass(frozen=True)
class Address:
    unit: str
    street: str
    district: str
    emirate: str

    def one_line(self) -> str:
        return f"{self.unit}, {self.street}, {self.district}, {self.emirate}"


class IdentityFactory:
    """Draws every random choice from the given ``rng`` so a seeded factory is reproducible."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.ref = load_reference_data()

    def person(self, gender: str | None = None, family_name: str | None = None) -> Person:
        rng = self.rng
        gender = gender or rng.choice("MF")
        nationalities = self.ref["nationalities"]
        nat = rng.choices(nationalities, weights=[n["weight"] for n in nationalities])[0]
        given, family = self._name(nat["names"], gender)
        family = family_name or family
        return Person(
            full_name=f"{given} {family}",
            given_name=given,
            family_name=family,
            gender=gender,
            nationality=nat["name"],
            email=self.email(f"{given} {family}"),
            phone=self.phone(),
        )

    def relative(self, of: Person, gender: str | None = None) -> str:
        """A household member's name, sharing the applicant's family name and name style."""
        gender = gender or self.rng.choice("MF")
        source = next(n["names"] for n in self.ref["nationalities"] if n["name"] == of.nationality)
        given, _ = self._name(source, gender)
        return f"{given} {of.family_name}"

    def _name(self, source: str, gender: str) -> tuple[str, str]:
        rng = self.rng
        if source == "arabic":
            given = rng.choice(
                self.ref["arabic_given_male" if gender == "M" else "arabic_given_female"]
            )
            return given, rng.choice(self.ref["arabic_family"])
        fake = _faker(source)
        fake.seed_instance(rng.getrandbits(32))
        given = fake.first_name_male() if gender == "M" else fake.first_name_female()
        return given, fake.last_name()

    def address(self) -> Address:
        rng = self.rng
        if rng.random() < 0.5:
            unit = f"Villa {rng.randint(1, 99)}"
        else:
            flat = f"{rng.randint(1, 30)}{rng.randint(1, 20):02d}"
            unit = f"Apartment {flat}, Building {rng.randint(1, 60)}"
        return Address(
            unit=unit,
            street=f"Street {rng.randint(1, 40)}",
            district=rng.choice(self.ref["districts"]),
            emirate=rng.choice(self.ref["emirates"]),
        )

    def email(self, full_name: str) -> str:
        local = ".".join(re.sub(r"[^a-z]", "", part.lower()) for part in full_name.split())
        return f"{local.strip('.')}{self.rng.randint(1, 99)}@example.com"

    def phone(self) -> str:
        return f"+971 50 000 {self.rng.randint(0, 9999):04d}"

    def employer(self) -> str:
        return self.rng.choice(self.ref["employers"])

    def job_title(self) -> str:
        return self.rng.choice(self.ref["job_titles"])

    def university(self) -> str:
        return self.rng.choice(self.ref["universities"])

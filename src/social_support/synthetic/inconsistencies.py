"""Deliberate cross-document inconsistencies (research R8, FR-007–FR-009).

At most one per pack. Each type alters exactly one place, chosen to mirror real patterns: the form
under-reports income, the bureau holds a stale address, the ID card carries a typo, the resume
names a different employer, the form lists one member more or fewer than the bureau.
"""

import random
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from social_support.labelling.facts import money
from social_support.synthetic.identities import (
    IdentityFactory,
    format_emirates_id,
    luhn_check_digit,
)
from social_support.synthetic.pack import ApplicantPack, jsonable, submission
from social_support.synthetic.profile import WORKING, HouseholdProfile, Member


class InconsistencyType(StrEnum):
    INCOME_MISMATCH = "INCOME_MISMATCH"
    ADDRESS_MISMATCH = "ADDRESS_MISMATCH"
    FAMILY_SIZE_MISMATCH = "FAMILY_SIZE_MISMATCH"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    EMPLOYMENT_MISMATCH = "EMPLOYMENT_MISMATCH"


def applies(kind: InconsistencyType, profile: HouseholdProfile) -> bool:
    if kind is InconsistencyType.INCOME_MISMATCH:
        return profile.net_monthly_income_aed > 0
    if kind is InconsistencyType.EMPLOYMENT_MISMATCH:
        return profile.employment_status in WORKING and profile.current_job is not None
    return True


def affected_count(count: int, rate_pct: int) -> int:
    """``rate × count`` rounded half up (5 packs at 50% gives 3; Python's round would give 2)."""
    exact = Decimal(count) * Decimal(rate_pct) / Decimal(100)
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def select_slots(
    rng: random.Random, count: int, rate_pct: int, types: tuple[str, ...]
) -> dict[int, InconsistencyType]:
    """Which packs (1-based) get which type, decided up front with the run's generator."""
    kinds = sorted(InconsistencyType(t) for t in types)
    chosen = sorted(rng.sample(range(1, count + 1), affected_count(count, rate_pct)))
    return {index: rng.choice(kinds) for index in chosen}


def inject(pack: ApplicantPack, kind: InconsistencyType, rng: random.Random) -> dict:
    """Alter one place in the pack's form or document views and record it in the pack."""
    if not applies(kind, pack.profile):
        raise ValueError(f"{kind.value} does not apply to {pack.pack_id}")
    field, documents, true, altered = _INJECTORS[kind](pack, rng)
    pack.form["submission"] = submission(pack.form)
    record = {
        "type": kind.value,
        "documents": documents,
        "field": field,
        "true_value": true,
        "altered_value": altered,
    }
    pack.inconsistency = record
    return record


def _income(pack: ApplicantPack, rng: random.Random):
    true = pack.profile.net_monthly_income_aed
    factor = Decimal(str(round(rng.uniform(0.60, 0.80), 3)))
    altered = money(true * factor)
    if altered == true:  # tiny incomes could round back to the true value
        altered = money(true - Decimal("0.01"))
    pack.form["net_monthly_income_aed"] = jsonable(altered)
    return "net_monthly_income_aed", ["form", "bank_statement"], jsonable(true), jsonable(altered)


def _address(pack: ApplicantPack, rng: random.Random):
    true = pack.profile.address.one_line()
    ids = IdentityFactory(rng)
    altered = true
    while altered == true:
        altered = ids.address().one_line()
    pack.views["credit_report"]["address"] = altered
    return "address", ["form", "credit_report"], true, altered


def _family_size(pack: ApplicantPack, rng: random.Random):
    members = list(pack.form["family_members"])
    true = 1 + len(members)
    if members and rng.random() < 0.5:
        members.pop(rng.randrange(len(members)))
    else:
        ids = IdentityFactory(rng)
        person = ids.person(family_name=pack.profile.full_name.split(" ", 1)[-1])
        members.append(jsonable(Member(person.full_name, "CHILD", rng.randint(0, 17))))
    pack.form["family_members"] = members
    pack.form["family_size"] = 1 + len(members)
    return "family_size", ["form", "credit_report"], str(true), str(1 + len(members))


def _identity(pack: ApplicantPack, rng: random.Random):
    card = pack.views["emirates_id"]
    if rng.random() < 0.5:
        true = card["full_name"]
        given, _, rest = true.partition(" ")
        altered = true
        while altered == true:
            i = rng.randrange(max(1, len(given) - 1))
            typo = given[:i] + given[i + 1] + given[i] + given[i + 2 :] if len(given) > 1 else given
            if typo == given:  # double letters: drop one instead
                typo = given[:i] + given[i + 1 :]
            altered = f"{typo} {rest}".strip()
        card["full_name"] = altered
        return "full_name", ["form", "emirates_id"], true, altered
    true = card["emirates_id"]
    digits = true.replace("-", "")
    position = rng.randrange(9, 14)  # the last 5 serial digits, keeping the reserved "00" prefix
    new_digit = rng.choice([d for d in "0123456789" if d != digits[position]])
    payload = digits[:position] + new_digit + digits[position + 1 : 14]
    altered = format_emirates_id(payload + str(luhn_check_digit(payload)))
    card["emirates_id"] = altered
    return "emirates_id", ["form", "emirates_id"], true, altered


def _employment(pack: ApplicantPack, rng: random.Random):
    resume = pack.views["resume"]
    true = resume["current_employer"]
    ids = IdentityFactory(rng)
    altered = true
    while altered == true:
        altered = ids.employer()
    resume["current_employer"] = altered
    for job in resume["jobs"]:
        if job["end"] is None:
            job["employer"] = altered
    return "employer", ["form", "resume"], true, altered


_INJECTORS = {
    InconsistencyType.INCOME_MISMATCH: _income,
    InconsistencyType.ADDRESS_MISMATCH: _address,
    InconsistencyType.FAMILY_SIZE_MISMATCH: _family_size,
    InconsistencyType.IDENTITY_MISMATCH: _identity,
    InconsistencyType.EMPLOYMENT_MISMATCH: _employment,
}

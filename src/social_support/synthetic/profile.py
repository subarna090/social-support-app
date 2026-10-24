"""The true facts about one fictional household, and how to sample them (data-model).

Every document in a pack is rendered from a ``HouseholdProfile``. ``to_facts`` is the only place
where the labelling facts are derived from it.
"""

import dataclasses
import random
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from social_support.domain.models import EmploymentStatus
from social_support.labelling import HouseholdFacts
from social_support.labelling.facts import money
from social_support.synthetic.identities import Address, IdentityFactory, emirates_id

WORKING = (EmploymentStatus.EMPLOYED, EmploymentStatus.SELF_EMPLOYED)


@dataclass(frozen=True)
class Member:
    name: str
    relationship: str  # SPOUSE, CHILD, PARENT, SIBLING
    age: int


@dataclass(frozen=True)
class Job:
    employer: str
    title: str
    start: date  # first day of the month
    end: date | None  # first day of the last month worked; None for the current job


@dataclass(frozen=True)
class IncomeSource:
    kind: str  # SALARY, BUSINESS, RENTAL, PENSION, BENEFIT
    monthly_amount_aed: Decimal
    payer: str


@dataclass(frozen=True)
class Asset:
    kind: str  # CASH, PROPERTY, VEHICLE, INVESTMENT
    description: str
    value_aed: Decimal


@dataclass(frozen=True)
class Liability:
    kind: str  # MORTGAGE, CAR_LOAN, PERSONAL_LOAN, CREDIT_CARD
    lender: str
    outstanding_aed: Decimal
    monthly_payment_aed: Decimal


@dataclass(frozen=True)
class CreditAccount:
    lender: str
    kind: str
    balance_aed: Decimal
    status: str  # CURRENT, LATE, DEFAULT


@dataclass(frozen=True)
class HouseholdProfile:
    full_name: str
    emirates_id: str
    date_of_birth: date
    nationality: str  # protected: documents and audit columns only, never HouseholdFacts
    gender: str  # protected: documents and audit columns only, never HouseholdFacts
    address: Address
    email: str
    phone: str
    members: tuple[Member, ...]
    employment_status: EmploymentStatus
    jobs: tuple[Job, ...]  # most recent first
    income_sources: tuple[IncomeSource, ...]
    assets: tuple[Asset, ...]
    liabilities: tuple[Liability, ...]
    credit_score: int
    credit_accounts: tuple[CreditAccount, ...]
    university: str
    graduation_year: int
    skills: tuple[str, ...]

    @property
    def family_size(self) -> int:
        return 1 + len(self.members)

    @property
    def current_job(self) -> Job | None:
        return next((job for job in self.jobs if job.end is None), None)

    @property
    def active_credit_defaults(self) -> int:
        return sum(account.status == "DEFAULT" for account in self.credit_accounts)

    @property
    def net_monthly_income_aed(self) -> Decimal:
        return money(sum((s.monthly_amount_aed for s in self.income_sources), Decimal("0")))

    def replace(self, **changes) -> "HouseholdProfile":
        return dataclasses.replace(self, **changes)


def pack_rng(seed: int, index: int) -> random.Random:
    """Each pack gets its own generator, so pack *i* is the same whatever else is in the batch."""
    return random.Random(seed * 1_000_003 + index)


def _month_index(day: date) -> int:
    return day.year * 12 + day.month - 1


def _month_start(index: int) -> date:
    return date(index // 12, index % 12 + 1, 1)


def months_employed_last_24(jobs: tuple[Job, ...], as_of: date) -> int:
    window_end = _month_index(as_of) - 1  # the 24 full months before the as-of month
    window = range(window_end - 23, window_end + 1)
    covered: set[int] = set()
    for job in jobs:
        last = window_end if job.end is None else _month_index(job.end)
        covered.update(m for m in range(_month_index(job.start), last + 1) if m in window)
    return len(covered)


def to_facts(profile: HouseholdProfile, as_of: date) -> HouseholdFacts:
    return HouseholdFacts.build(
        family_size=profile.family_size,
        net_monthly_income_aed=profile.net_monthly_income_aed,
        employment_status=profile.employment_status,
        months_employed_last_24=months_employed_last_24(profile.jobs, as_of),
        total_assets_aed=sum((a.value_aed for a in profile.assets), Decimal("0")),
        total_liabilities_aed=sum((li.outstanding_aed for li in profile.liabilities), Decimal("0")),
        credit_score=profile.credit_score,
        active_credit_defaults=profile.active_credit_defaults,
    )


# --- sampling ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Priors:
    """Ranges the sampler draws from. Feature 002 US3 adds outcome-targeted variants."""

    status_weights: tuple[int, int, int, int, int] = (50, 12, 18, 8, 12)  # EmploymentStatus order
    salary_range: tuple[int, int] = (2500, 25000)
    stable_job_share: float = 0.75
    property_share: float = 0.15
    investment_share: float = 0.15
    default_share_low_score: float = 0.5
    default_share: float = 0.05
    score_mean: int = 680


BASE_PRIORS = Priors()


def _amount(rng: random.Random, low: int, high: int, step: int = 50) -> Decimal:
    return money(round(rng.uniform(low, high) / step) * step)


def _months_ago(as_of: date, months: int) -> date:
    return _month_start(_month_index(as_of) - months)


class SamplingError(RuntimeError):
    """The sampler could not meet its constraints within the attempt limit."""


def sample_profile(
    rng: random.Random,
    as_of: date,
    pack_index: int,
    priors: Priors = BASE_PRIORS,
    *,
    requires_income: bool = False,
    requires_employment: bool = False,
    max_attempts: int = 200,
) -> HouseholdProfile:
    """Draw one household, redrawing until the constraints hold (research R8: a pack chosen for
    an income or employment mismatch must have income or a current job)."""
    for _ in range(max_attempts):
        profile = _draw_profile(rng, as_of, pack_index, priors)
        if requires_income and profile.net_monthly_income_aed <= 0:
            continue
        if requires_employment and profile.employment_status not in WORKING:
            continue
        return profile
    raise SamplingError(f"no profile met the constraints in {max_attempts} attempts")


def _draw_profile(
    rng: random.Random, as_of: date, pack_index: int, priors: Priors
) -> HouseholdProfile:
    """Draw one household. Every random choice comes from ``rng``, in a fixed order."""
    ids = IdentityFactory(rng)
    ref = ids.ref

    status = rng.choices(list(EmploymentStatus), weights=priors.status_weights)[0]
    age = {
        EmploymentStatus.STUDENT: rng.randint(19, 30),
        EmploymentStatus.RETIRED: rng.randint(55, 75),
    }.get(status, rng.randint(22, 60))
    birth = date(as_of.year - age, rng.randint(1, 12), rng.randint(1, 28))
    person = ids.person()

    members = _sample_members(rng, ids, person, age, status)
    jobs = _sample_jobs(rng, ids, person, as_of, status, priors)
    income = _sample_income(rng, ids, jobs, status, priors)
    assets, liabilities = _sample_wealth(rng, ref, priors)

    score = max(300, min(900, round(rng.gauss(priors.score_mean, 90))))
    default_share = priors.default_share_low_score if score < 550 else priors.default_share
    accounts = []
    for i, liability in enumerate(liabilities):
        if i == 0 and liabilities and rng.random() < default_share:
            state = "DEFAULT"
        else:
            state = "LATE" if rng.random() < 0.08 else "CURRENT"
        accounts.append(
            CreditAccount(liability.lender, liability.kind, liability.outstanding_aed, state)
        )
    if not liabilities and rng.random() < default_share:
        accounts.append(
            CreditAccount(
                rng.choice(ref["lenders"]), "PERSONAL_LOAN", _amount(rng, 2000, 20000), "DEFAULT"
            )
        )

    return HouseholdProfile(
        full_name=person.full_name,
        emirates_id=emirates_id(birth.year, pack_index),
        date_of_birth=birth,
        nationality=person.nationality,
        gender=person.gender,
        address=ids.address(),
        email=person.email,
        phone=person.phone,
        members=members,
        employment_status=status,
        jobs=jobs,
        income_sources=income,
        assets=assets,
        liabilities=liabilities,
        credit_score=score,
        credit_accounts=tuple(accounts),
        university=ids.university(),
        graduation_year=min(as_of.year - 1, birth.year + rng.randint(21, 25)),
        skills=tuple(rng.sample(ref["skills"], 3)),
    )


def _sample_members(rng, ids, person, age, status) -> tuple[Member, ...]:
    members: list[Member] = []
    if age >= 23 and rng.random() < 0.6:
        members.append(Member(ids.relative(person), "SPOUSE", max(20, age + rng.randint(-6, 4))))
    if age >= 20:
        children = rng.choices(range(9), weights=[20, 18, 20, 15, 10, 7, 4, 3, 3])[0]
        oldest = max(0, min(25, age - 19))
        for _ in range(children):
            members.append(Member(ids.relative(person), "CHILD", rng.randint(0, oldest)))
    for _ in range(rng.choices(range(3), weights=[85, 10, 5])[0]):
        members.append(Member(ids.relative(person), "PARENT", min(95, age + rng.randint(20, 32))))
    if status is EmploymentStatus.STUDENT and rng.random() < 0.3:
        members.append(Member(ids.relative(person), "SIBLING", max(5, age + rng.randint(-8, 8))))
    return tuple(members)


def _sample_jobs(rng, ids, person, as_of, status, priors) -> tuple[Job, ...]:
    jobs: list[Job] = []
    if status in WORKING:
        employer = (
            f"{person.family_name} Services (Demo)"
            if status is EmploymentStatus.SELF_EMPLOYED
            else ids.employer()
        )
        stable = rng.random() < priors.stable_job_share
        started = rng.randint(12, 120) if stable else rng.randint(1, 11)
        jobs.append(Job(employer, ids.job_title(), _months_ago(as_of, started), None))
        previous_end = started + rng.randint(1, 8)  # gap before the current job
    elif status is EmploymentStatus.UNEMPLOYED:
        previous_end = rng.randint(1, 30)
    elif status is EmploymentStatus.RETIRED:
        previous_end = rng.randint(6, 120)
    else:  # student: perhaps a past part-time job
        previous_end = rng.randint(3, 24) if rng.random() < 0.3 else None
    if previous_end is not None and rng.random() < 0.85:
        length = rng.randint(6, 72)
        jobs.append(
            Job(
                ids.employer(),
                ids.job_title(),
                _months_ago(as_of, previous_end + length),
                _months_ago(as_of, previous_end),
            )
        )
    return tuple(jobs)


def _sample_income(rng, ids, jobs, status, priors) -> tuple[IncomeSource, ...]:
    sources: list[IncomeSource] = []
    if status is EmploymentStatus.EMPLOYED:
        sources.append(IncomeSource("SALARY", _amount(rng, *priors.salary_range), jobs[0].employer))
    elif status is EmploymentStatus.SELF_EMPLOYED:
        low, high = priors.salary_range
        sources.append(IncomeSource("BUSINESS", _amount(rng, low // 2, high), jobs[0].employer))
    elif status is EmploymentStatus.RETIRED and rng.random() < 0.7:
        sources.append(
            IncomeSource("PENSION", _amount(rng, 1500, 12000), "General Pension Fund (Demo)")
        )
    elif status is EmploymentStatus.UNEMPLOYED and rng.random() < 0.5:
        sources.append(
            IncomeSource("BENEFIT", _amount(rng, 500, 3000), "Social Support Programme (Demo)")
        )
    elif status is EmploymentStatus.STUDENT and rng.random() < 0.2:
        sources.append(
            IncomeSource("BENEFIT", _amount(rng, 300, 1500), "Student Grant Office (Demo)")
        )
    if rng.random() < 0.12:
        sources.append(IncomeSource("RENTAL", _amount(rng, 1500, 8000), "Tenant (rental income)"))
    return tuple(sources)


def _sample_wealth(rng, ref, priors) -> tuple[tuple[Asset, ...], tuple[Liability, ...]]:
    assets = [Asset("CASH", "Savings account", _amount(rng, 0, 60000, 10))]
    liabilities: list[Liability] = []
    if rng.random() < priors.property_share:
        value = _amount(rng, 300_000, 2_500_000, 1000)
        assets.append(Asset("PROPERTY", "Residential apartment", value))
        if rng.random() < 0.7:
            outstanding = money(value * Decimal(str(round(rng.uniform(0.4, 0.9), 2))))
            liabilities.append(
                Liability(
                    "MORTGAGE", rng.choice(ref["lenders"]), outstanding, money(outstanding / 240)
                )
            )
    if rng.random() < 0.5:
        value = _amount(rng, 15_000, 150_000, 500)
        assets.append(Asset("VEHICLE", "Family car", value))
        if rng.random() < 0.5:
            outstanding = money(value * Decimal("0.6"))
            liabilities.append(
                Liability(
                    "CAR_LOAN", rng.choice(ref["lenders"]), outstanding, money(outstanding / 48)
                )
            )
    if rng.random() < priors.investment_share:
        assets.append(Asset("INVESTMENT", "Shares and funds", _amount(rng, 5_000, 300_000, 500)))
    if rng.random() < 0.3:
        outstanding = _amount(rng, 5_000, 80_000)
        liabilities.append(
            Liability(
                "PERSONAL_LOAN", rng.choice(ref["lenders"]), outstanding, money(outstanding / 36)
            )
        )
    if rng.random() < 0.5:
        outstanding = _amount(rng, 1_000, 30_000)
        liabilities.append(
            Liability(
                "CREDIT_CARD", rng.choice(ref["lenders"]), outstanding, money(outstanding / 20)
            )
        )
    return tuple(assets), tuple(liabilities)

"""Three fixed demo applicants, one per outcome (feature 004, research R8).

Hand-built profiles instead of sampled ones, so the presenter's story is exact: the same names,
amounts and documents on every run. They are rendered with the normal 002 pack writer, so each
folder also holds ``form.json`` and ``answer_key.json``.
"""

import random
import shutil
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from social_support.domain.models import EmploymentStatus, Outcome
from social_support.labelling import load_policy
from social_support.synthetic.identities import Address, emirates_id
from social_support.synthetic.inconsistencies import InconsistencyType
from social_support.synthetic.pack import build_pack, jsonable, submission, write_pack
from social_support.synthetic.profile import (
    Asset,
    CreditAccount,
    HouseholdProfile,
    IncomeSource,
    Job,
    Liability,
    Member,
)

AS_OF = date(2026, 10, 1)
RUN_ID = "demo"


class DemoExistsError(Exception):
    pass


@dataclass(frozen=True)
class DemoPack:
    name: str  # folder name
    index: int
    expected: Outcome
    profile: HouseholdProfile
    declared_income_aed: Decimal | None = None  # set when the form under-reports income


def _approve() -> HouseholdProfile:
    birth = date(1988, 3, 12)
    return HouseholdProfile(
        full_name="Mariam Saeed Al Hammadi",
        emirates_id=emirates_id(birth.year, 901),
        date_of_birth=birth,
        nationality="Emirati",
        gender="F",
        address=Address("Apartment 1408, Building 22", "Street 9", "Al Waha District", "Sharjah"),
        email="mariam.al.hammadi12@example.com",
        phone="+971 50 000 0901",
        members=(
            Member("Saeed Rashid Al Hammadi", "SPOUSE", 39),
            Member("Noura Al Hammadi", "CHILD", 11),
            Member("Ahmed Al Hammadi", "CHILD", 8),
            Member("Latifa Al Hammadi", "CHILD", 4),
        ),
        employment_status=EmploymentStatus.EMPLOYED,
        jobs=(
            Job("Palm Leaf Retail (Demo)", "Sales Associate", date(2025, 2, 1), None),
            Job(
                "Blue Lagoon Hospitality (Demo)",
                "Receptionist",
                date(2021, 6, 1),
                date(2024, 11, 1),
            ),
        ),
        income_sources=(IncomeSource("SALARY", Decimal("6000.00"), "Palm Leaf Retail (Demo)"),),
        assets=(
            Asset("CASH", "Savings account", Decimal("18000.00")),
            Asset("VEHICLE", "Family car", Decimal("25000.00")),
        ),
        liabilities=(
            Liability("CAR_LOAN", "Crescent Demo Finance", Decimal("13000.00"), Decimal("900.00")),
        ),
        credit_score=720,
        credit_accounts=(
            CreditAccount("Crescent Demo Finance", "CAR_LOAN", Decimal("13000.00"), "CURRENT"),
        ),
        university="Gulf Coast University (Demo)",
        graduation_year=2009,
        skills=(
            "Customer service",
            "Point-of-sale systems",
            "Inventory control",
            "Arabic and English",
        ),
    )


def _soft_decline() -> HouseholdProfile:
    birth = date(1980, 7, 22)
    return HouseholdProfile(
        full_name="Omar Khalid Al Mansoori",
        emirates_id=emirates_id(birth.year, 902),
        date_of_birth=birth,
        nationality="Emirati",
        gender="M",
        address=Address("Villa 17", "Street 31", "Marina View", "Abu Dhabi"),
        email="omar.al.mansoori7@example.com",
        phone="+971 50 000 0902",
        members=(Member("Huda Al Mansoori", "SPOUSE", 43),),
        employment_status=EmploymentStatus.EMPLOYED,
        jobs=(
            Job("Mirage Software (Demo) FZ-LLC", "Project Manager", date(2019, 4, 1), None),
            Job("Al Waha Engineering (Demo)", "Engineer", date(2010, 9, 1), date(2019, 3, 1)),
        ),
        income_sources=(
            IncomeSource("SALARY", Decimal("18000.00"), "Mirage Software (Demo) FZ-LLC"),
        ),
        assets=(
            Asset("CASH", "Savings account", Decimal("120000.00")),
            Asset("PROPERTY", "Residential villa", Decimal("750000.00")),
            Asset("INVESTMENT", "Shares and funds", Decimal("80000.00")),
        ),
        liabilities=(
            Liability(
                "MORTGAGE", "Desert Falcon Demo Bank", Decimal("300000.00"), Decimal("4500.00")
            ),
        ),
        credit_score=760,
        credit_accounts=(
            CreditAccount("Desert Falcon Demo Bank", "MORTGAGE", Decimal("300000.00"), "CURRENT"),
        ),
        university="Desert Star University (Demo)",
        graduation_year=2002,
        skills=("Project management", "Team leadership", "Scheduling", "Microsoft Excel"),
    )


def _review() -> HouseholdProfile:
    birth = date(1985, 11, 5)
    return HouseholdProfile(
        full_name="Hassan Ali Al Zaabi",
        emirates_id=emirates_id(birth.year, 903),
        date_of_birth=birth,
        nationality="Emirati",
        gender="M",
        address=Address("Apartment 703, Building 41", "Street 14", "Al Fajr Park", "Ajman"),
        email="hassan.al.zaabi33@example.com",
        phone="+971 50 000 0903",
        members=(
            Member("Fatima Al Zaabi", "SPOUSE", 38),
            Member("Khalid Al Zaabi", "CHILD", 9),
            Member("Maitha Al Zaabi", "CHILD", 6),
        ),
        employment_status=EmploymentStatus.EMPLOYED,
        jobs=(Job("Al Waha Engineering (Demo)", "Technician", date(2022, 1, 1), None),),
        income_sources=(
            IncomeSource("SALARY", Decimal("7500.00"), "Al Waha Engineering (Demo)"),
            IncomeSource("RENTAL", Decimal("1500.00"), "Tenant (rental income)"),
        ),
        assets=(
            Asset("CASH", "Savings account", Decimal("22000.00")),
            Asset("VEHICLE", "Family car", Decimal("30000.00")),
        ),
        liabilities=(
            Liability(
                "PERSONAL_LOAN", "Sandstone Demo Credit", Decimal("12000.00"), Decimal("800.00")
            ),
        ),
        credit_score=690,
        credit_accounts=(
            CreditAccount("Sandstone Demo Credit", "PERSONAL_LOAN", Decimal("12000.00"), "CURRENT"),
        ),
        university="Crescent Polytechnic (Demo)",
        graduation_year=2006,
        skills=("Electrical maintenance", "First aid", "Driving licence", "Arabic and English"),
    )


DEMO_PACKS = (
    DemoPack("approve", 901, Outcome.APPROVE, _approve()),
    DemoPack("soft_decline", 902, Outcome.SOFT_DECLINE, _soft_decline()),
    # Borderline income (9000 / 4 = 2250) and the form under-reports it as 7000.
    DemoPack("review", 903, Outcome.NEEDS_HUMAN_REVIEW, _review(), Decimal("7000.00")),
)


def write_demo(out: Path, force: bool = False) -> list[tuple[str, Outcome, dict]]:
    """Write the three demo packs to ``out/<name>/``; returns (folder, expected, form values)."""
    folders = [out / demo.name for demo in DEMO_PACKS]
    existing = [f for f in folders if f.exists()]
    if existing and not force:
        names = ", ".join(f.name for f in existing)
        raise DemoExistsError(f"demo packs already exist in {out} ({names}); use --force")
    for folder in existing:
        shutil.rmtree(folder)

    policy = load_policy()
    written = []
    for demo, folder in zip(DEMO_PACKS, folders, strict=True):
        pack = build_pack(demo.index, demo.profile, policy, AS_OF, random.Random(demo.index))
        if demo.declared_income_aed is not None:
            true = pack.form["net_monthly_income_aed"]
            pack.form["net_monthly_income_aed"] = jsonable(demo.declared_income_aed)
            pack.form["submission"] = submission(pack.form)
            pack.inconsistency = {
                "type": InconsistencyType.INCOME_MISMATCH.value,
                "documents": ["form", "bank_statement"],
                "field": "net_monthly_income_aed",
                "true_value": true,
                "altered_value": jsonable(demo.declared_income_aed),
            }
        if pack.expected_routing is not demo.expected:  # guards the hand-built values
            raise AssertionError(f"{demo.name} would route to {pack.expected_routing.value}")
        write_pack(pack, folder, RUN_ID, AS_OF)
        written.append((demo.name, demo.expected, pack.form["submission"]))
    return written

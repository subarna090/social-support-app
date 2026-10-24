"""One applicant pack: form, five documents and the answer key (data-model ApplicantPack).

Documents are rendered from *views*: the values each document shows. Views start from the true
profile; an injected inconsistency (US2) alters exactly one view before rendering.
"""

import dataclasses
import json
import random
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path

from social_support.domain.models import Outcome
from social_support.labelling import HouseholdFacts, LabellingPolicy, LabelResult
from social_support.labelling.facts import money
from social_support.synthetic.documents.assets_liabilities import render_assets_liabilities
from social_support.synthetic.documents.bank_statement import render_bank_statement
from social_support.synthetic.documents.credit_report import render_credit_report
from social_support.synthetic.documents.emirates_id import render_emirates_id
from social_support.synthetic.documents.resume import render_resume
from social_support.synthetic.identities import load_reference_data
from social_support.synthetic.profile import HouseholdProfile, to_facts

FORMAT = "pack-format/1"
INCOME_LABELS = {
    "SALARY": "Salary",
    "BUSINESS": "Business income",
    "RENTAL": "Rental income",
    "PENSION": "Pension",
    "BENEFIT": "Benefit payment",
}


@dataclass
class ApplicantPack:
    index: int
    profile: HouseholdProfile
    facts: HouseholdFacts
    label: LabelResult
    form: dict
    views: dict[str, dict]
    inconsistency: dict | None = None

    @property
    def pack_id(self) -> str:
        return f"pack-{self.index:04d}"

    @property
    def expected_routing(self) -> Outcome:
        """FR-011: any injected inconsistency routes the pack to human review."""
        return Outcome.NEEDS_HUMAN_REVIEW if self.inconsistency else self.label.outcome


def jsonable(value):
    """Canonical JSON form: money and other Decimals as 2-dp strings, dates as ISO strings."""
    if dataclasses.is_dataclass(value):
        return {f.name: jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def build_form(index: int, profile: HouseholdProfile) -> dict:
    """What the applicant states: the FR-002 fields plus the 001 submission payload."""
    job = profile.current_job
    form = {
        "pack_id": f"pack-{index:04d}",
        "full_name": profile.full_name,
        "emirates_id": profile.emirates_id,
        "date_of_birth": profile.date_of_birth.isoformat(),
        "address": jsonable(profile.address),
        "email": profile.email,
        "phone": profile.phone,
        "family_size": profile.family_size,
        "family_members": jsonable(profile.members),
        "net_monthly_income_aed": jsonable(profile.net_monthly_income_aed),
        "employment_status": profile.employment_status.value,
        "employer": job.employer if job else None,
    }
    return form | {"submission": submission(form)}


def submission(form: dict) -> dict:
    """Exactly the body of the 001 ``POST /api/v1/applications`` request."""
    keys = (
        "full_name",
        "emirates_id",
        "family_size",
        "net_monthly_income_aed",
        "employment_status",
    )
    return {key: form[key] for key in keys}


LANDLORDS = (
    "Palm Grove Properties (Demo)",
    "Oasis Residences Management (Demo)",
    "Crescent Homes Leasing (Demo)",
    "Golden Dunes Real Estate (Demo)",
)


def _statement_months(
    start_index: int,
    months: int,
    opening: Decimal,
    credits: list[dict],
    payments: list[dict],
    rent: dict | None,
    rng: random.Random,
) -> list[dict]:
    """Every transaction the statement shows, with running and closing balances (FR-005)."""
    balance, result = opening, []
    for index in range(start_index, start_index + months):
        year, month = index // 12, index % 12 + 1
        entries = [(1, c["description"], Decimal(c["amount_aed"]), None) for c in credits]
        if rent:
            entries.append((3, rent["description"], None, Decimal(rent["amount_aed"])))
        entries += [(5, p["description"], None, Decimal(p["amount_aed"])) for p in payments]
        entries += [
            (10, "Utilities - Oasis Power and Water (Demo)", None, Decimal(rng.randint(250, 900))),
            (
                15,
                "Groceries - Spice Route Supermarket (Demo)",
                None,
                Decimal(rng.randint(300, 1500)),
            ),
            (25, "Groceries - Palm Leaf Retail (Demo)", None, Decimal(rng.randint(200, 1200))),
        ]
        transactions = []
        for day, description, credit, debit in entries:
            balance += (credit or 0) - (debit or 0)
            transactions.append(
                {
                    "date": date(year, month, day).isoformat(),
                    "description": description,
                    "credit_aed": jsonable(credit) if credit else None,
                    "debit_aed": jsonable(debit) if debit else None,
                    "balance_aed": jsonable(balance),
                }
            )
        result.append(
            {
                "month": date(year, month, 1).isoformat(),
                "transactions": transactions,
                "closing_balance_aed": jsonable(balance),
            }
        )
    return result


def build_views(profile: HouseholdProfile, as_of: date, rng: random.Random) -> dict[str, dict]:
    ref = load_reference_data()
    address = profile.address.one_line()
    months = rng.randint(3, 6)
    end_index = as_of.year * 12 + as_of.month - 2  # last full month before the as-of month
    start_index = end_index - months + 1
    credits = [
        {
            "kind": s.kind,
            "description": f"{INCOME_LABELS[s.kind]} - {s.payer}",
            "amount_aed": jsonable(s.monthly_amount_aed),
        }
        for s in profile.income_sources
    ]
    payments = [
        {
            "description": f"Loan repayment - {li.lender} ({li.kind.replace('_', ' ').lower()})",
            "amount_aed": jsonable(li.monthly_payment_aed),
        }
        for li in profile.liabilities
    ]
    rent = None
    if not any(li.kind == "MORTGAGE" for li in profile.liabilities):  # research R7
        rent = {
            "description": f"Rent - {rng.choice(LANDLORDS)}",
            "amount_aed": jsonable(money(round(rng.uniform(1500, 6000) / 50) * 50)),
        }
    account_number = f"DFDB 0000 {rng.randint(0, 99_999_999):08d}"
    opening = profile.assets[0].value_aed
    statement = _statement_months(start_index, months, opening, credits, payments, rent, rng)
    facts_total_assets = sum((a.value_aed for a in profile.assets), Decimal("0"))
    facts_total_liabilities = sum((li.outstanding_aed for li in profile.liabilities), Decimal("0"))
    current = profile.current_job
    return {
        "bank_statement": {
            "bank_name": ref["bank_name"],
            "account_holder": profile.full_name,
            "address": address,
            "account_number": account_number,
            "statement_months": months,
            "period_start": date(start_index // 12, start_index % 12 + 1, 1).isoformat(),
            "period_end": date(end_index // 12, end_index % 12 + 1, 1).isoformat(),
            "opening_balance_aed": jsonable(profile.assets[0].value_aed),
            "income_credits": credits,
            "monthly_income_credits_aed": jsonable(profile.net_monthly_income_aed),
            "monthly_payments": payments,
            "rent": rent,
            "months": statement,
        },
        "emirates_id": {
            "full_name": profile.full_name,
            "emirates_id": profile.emirates_id,
            "nationality": profile.nationality,
            "date_of_birth": profile.date_of_birth.isoformat(),
            "sex": profile.gender,
            "expiry_date": date(
                as_of.year + 3, profile.date_of_birth.month, profile.date_of_birth.day
            ).isoformat(),
        },
        "resume": {
            "full_name": profile.full_name,
            "email": profile.email,
            "phone": profile.phone,
            "address": address,
            "current_employer": current.employer if current else None,
            "jobs": jsonable(profile.jobs),
            "university": profile.university,
            "graduation_year": profile.graduation_year,
            "skills": list(profile.skills),
        },
        "assets_liabilities": {
            "assets": jsonable(profile.assets),
            "liabilities": jsonable(profile.liabilities),
            "total_assets_aed": jsonable(facts_total_assets),
            "total_liabilities_aed": jsonable(facts_total_liabilities),
            "net_wealth_aed": jsonable(facts_total_assets - facts_total_liabilities),
        },
        "credit_report": {
            "bureau_name": ref["bureau_name"],
            "report_date": as_of.isoformat(),
            "full_name": profile.full_name,
            "emirates_id": profile.emirates_id,
            "date_of_birth": profile.date_of_birth.isoformat(),
            "address": address,
            "household_members": jsonable(profile.members),
            "credit_score": profile.credit_score,
            "active_credit_defaults": profile.active_credit_defaults,
            "accounts": jsonable(profile.credit_accounts),
        },
    }


def build_pack(
    index: int,
    profile: HouseholdProfile,
    policy: LabellingPolicy,
    as_of: date,
    rng: random.Random,
) -> ApplicantPack:
    facts = to_facts(profile, as_of)
    return ApplicantPack(
        index=index,
        profile=profile,
        facts=facts,
        label=policy.evaluate(facts),
        form=build_form(index, profile),
        views=build_views(profile, as_of, rng),
    )


def write_pack(pack: ApplicantPack, folder: Path, run_id: str, as_of: date):
    folder.mkdir(parents=True)
    v = pack.views
    render_bank_statement(v["bank_statement"], folder / "bank_statement.pdf")
    render_emirates_id(v["emirates_id"], folder / "emirates_id.png")
    render_resume(v["resume"], folder / "resume.pdf")
    render_assets_liabilities(v["assets_liabilities"], folder / "assets_liabilities.xlsx", as_of)
    render_credit_report(v["credit_report"], folder / "credit_report.pdf")

    form_view = {k: val for k, val in pack.form.items() if k not in ("pack_id", "submission")}
    key = {
        "format": FORMAT,
        "run_id": run_id,
        "pack_id": pack.pack_id,
        "profile": jsonable(pack.profile),
        "facts": jsonable(pack.facts),
        "documents": {"form": form_view, **v},
        "inconsistency": pack.inconsistency,
        "eligibility": {
            "outcome": pack.label.outcome.value,
            "rule_id": pack.label.rule_id,
            "compared": jsonable(pack.label.compared),
            "reason": pack.label.reason,
            "policy_version_id": pack.label.policy_version_id,
        },
        "expected_routing": pack.expected_routing.value,
    }
    _write_json(folder / "form.json", pack.form)
    _write_json(folder / "answer_key.json", key)


def _write_json(path: Path, data: dict) -> None:
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")

"""Economic enablement recommendations (feature 004, US4, research R7). Pure types only.

The profile is all the language model ever sees: no name, Emirates ID, employer, exact income,
nationality or gender (FR-012).
"""

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Protocol

BORDERLINE_FROM_AED = Decimal("2000")
BORDERLINE_TO_AED = Decimal("2500")


def income_band(income_per_member_aed: Decimal | None) -> str:
    """A coarse label instead of the amount (same bands as decision_v1)."""
    if income_per_member_aed is None:
        return "unknown"
    if income_per_member_aed < BORDERLINE_FROM_AED:
        return "below_band"
    if income_per_member_aed <= BORDERLINE_TO_AED:
        return "borderline"
    return "above_band"


@dataclass(frozen=True)
class EnablementProfile:
    skills: tuple[str, ...]
    education: str
    years_experience: str
    last_job_title: str
    employment_status: str
    months_employed_last_24: int | None
    family_size: int
    outcome: str
    income_band: str  # below_band | borderline | above_band | unknown

    def as_dict(self) -> dict:
        data = asdict(self)
        data["skills"] = list(self.skills)
        return data


@dataclass(frozen=True)
class EnablementPlan:
    training: tuple[str, ...]
    job_matches: tuple[str, ...]
    career_counselling: str
    is_fallback: bool = False
    model: str = "fallback"


class EnablementAdvisor(Protocol):
    @property
    def model(self) -> str: ...

    def advise(self, profile: EnablementProfile) -> EnablementPlan:
        """Raise on any failure; the service then shows ``FALLBACK_PLAN``."""
        ...


FALLBACK_PLAN = EnablementPlan(
    training=(
        "Short digital skills course (office software, email and online job applications).",
        "Vocational certificate in a growing sector such as logistics, hospitality or healthcare "
        "support.",
        "English or Arabic language course to widen job options.",
    ),
    job_matches=(
        "Register with the national employment portal to be matched with current vacancies.",
        "Entry-level roles that build on your past experience while you train.",
    ),
    career_counselling=(
        "Book a session with a career counsellor to review your resume, set a 3-month job search "
        "plan and choose a training course that fits your experience."
    ),
    is_fallback=True,
    model="fallback",
)

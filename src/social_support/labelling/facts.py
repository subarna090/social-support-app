"""The only input the labelling policy sees. No identity and no protected attributes (FR-012)."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from social_support.domain.models import EmploymentStatus

CENT = Decimal("0.01")


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class HouseholdFacts:
    family_size: int
    net_monthly_income_aed: Decimal
    income_per_member_aed: Decimal
    employment_status: EmploymentStatus
    months_employed_last_24: int
    total_assets_aed: Decimal
    total_liabilities_aed: Decimal
    net_wealth_aed: Decimal
    credit_score: int
    active_credit_defaults: int

    def __post_init__(self) -> None:
        checks = {
            "family_size must be at least 1": self.family_size >= 1,
            "net_monthly_income_aed must not be negative": self.net_monthly_income_aed >= 0,
            "months_employed_last_24 must be between 0 and 24": 0
            <= self.months_employed_last_24
            <= 24,
            "total_assets_aed must not be negative": self.total_assets_aed >= 0,
            "total_liabilities_aed must not be negative": self.total_liabilities_aed >= 0,
            "credit_score must be between 300 and 900": 300 <= self.credit_score <= 900,
            "active_credit_defaults must not be negative": self.active_credit_defaults >= 0,
        }
        for message, ok in checks.items():
            if not ok:
                raise ValueError(message)

    @classmethod
    def build(
        cls,
        *,
        family_size: int,
        net_monthly_income_aed: Decimal,
        employment_status: EmploymentStatus,
        months_employed_last_24: int,
        total_assets_aed: Decimal,
        total_liabilities_aed: Decimal,
        credit_score: int,
        active_credit_defaults: int,
    ) -> "HouseholdFacts":
        """Derive income per member (ROUND_HALF_UP, 2 dp) and net wealth from the raw values."""
        income = money(net_monthly_income_aed)
        assets, liabilities = money(total_assets_aed), money(total_liabilities_aed)
        return cls(
            family_size=family_size,
            net_monthly_income_aed=income,
            income_per_member_aed=money(income / family_size),
            employment_status=EmploymentStatus(employment_status),
            months_employed_last_24=months_employed_last_24,
            total_assets_aed=assets,
            total_liabilities_aed=liabilities,
            net_wealth_aed=assets - liabilities,
            credit_score=credit_score,
            active_credit_defaults=active_credit_defaults,
        )

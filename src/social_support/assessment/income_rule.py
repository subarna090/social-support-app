"""Placeholder assessment rule v0.1: income per family member (data-model.md).

The thresholds are illustrative PoC values, not official policy.
"""

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal

from social_support.domain.models import (
    ApplicationInput,
    AssessmentResult,
    Outcome,
    RuleVersionInfo,
)

RULE_NAME = "income-per-member"
RULE_VERSION = "v0.1"
CENT = Decimal("0.01")
SOFT_DECLINE_NEXT_STEPS = (
    "Reapply if your household income or size changes",
    "Ask about economic enablement support (training, job matching)",
)


class IncomePerMemberRuleAssessor:
    def __init__(
        self,
        threshold_aed: Decimal = Decimal("2000"),
        band_upper_aed: Decimal = Decimal("2500"),
    ) -> None:
        self.threshold = Decimal(threshold_aed).quantize(CENT)
        self.band_upper = Decimal(band_upper_aed).quantize(CENT)
        parameters = {"threshold_aed": str(self.threshold), "band_upper_aed": str(self.band_upper)}
        digest = hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()
        self._rule_version = RuleVersionInfo(
            id=f"{RULE_NAME}/{RULE_VERSION}+{digest[:8]}", name=RULE_NAME, parameters=parameters
        )

    @property
    def rule_version(self) -> RuleVersionInfo:
        return self._rule_version

    def assess(self, application: ApplicationInput) -> AssessmentResult:
        income = Decimal(application.net_monthly_income_aed).quantize(CENT)
        members = application.family_size
        ipm = (income / members).quantize(CENT, rounding=ROUND_HALF_UP)

        basis = (
            f"Net monthly household income of {income} AED across {members} "
            f"{'member' if members == 1 else 'members'} gives {ipm} AED per member"
        )
        trailer = (
            f" Employment status: {application.employment_status.label}."
            f" Rule: {self._rule_version.id}."
        )

        if ipm < self.threshold:
            outcome, flag_reason, next_steps = Outcome.APPROVE, None, ()
            verdict = f", which is below the {self.threshold} AED support threshold."
        elif ipm <= self.band_upper:
            outcome, flag_reason, next_steps = Outcome.NEEDS_HUMAN_REVIEW, "borderline income", ()
            verdict = (
                f", which is within the borderline band of {self.threshold}–{self.band_upper} AED,"
                " so a caseworker will review this application."
            )
        else:
            outcome, flag_reason, next_steps = Outcome.SOFT_DECLINE, None, SOFT_DECLINE_NEXT_STEPS
            verdict = (
                f", which is above the {self.band_upper} AED upper limit of the borderline band."
            )

        return AssessmentResult(
            outcome=outcome,
            income_per_member_aed=ipm,
            explanation=basis + verdict + trailer,
            suggested_next_steps=next_steps,
            flag_reason=flag_reason,
            rule_version_id=self._rule_version.id,
        )

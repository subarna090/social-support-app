"""The assessment extension point (research R2).

Every assessor (the v0.1 rule now, the ML and agent versions later) implements ``Assessor``
and returns an ``AssessmentResult`` that always carries an explanation and a rule version.
"""

from typing import TYPE_CHECKING, Protocol

from social_support.domain.models import ApplicationInput, AssessmentResult, RuleVersionInfo

if TYPE_CHECKING:
    from social_support.config import Settings

FALLBACK_RULE_VERSION = RuleVersionInfo(id="fallback", name="fallback", parameters={})


class Assessor(Protocol):
    @property
    def rule_version(self) -> RuleVersionInfo: ...

    def assess(self, application: ApplicationInput) -> AssessmentResult: ...


def build_assessor(settings: "Settings") -> Assessor:
    """Create the assessor named by ``settings.assessor``."""
    if settings.assessor == "income_rule":
        from social_support.assessment.income_rule import IncomePerMemberRuleAssessor

        return IncomePerMemberRuleAssessor(
            threshold_aed=settings.rule_threshold_aed,
            band_upper_aed=settings.rule_band_upper_aed,
        )
    raise ValueError(f"Unknown assessor: {settings.assessor!r}")

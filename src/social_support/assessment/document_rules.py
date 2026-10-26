"""Document-based decision (feature 004, research R5 and R6).

The assessor sees only ``HouseholdFacts`` and findings the service has already built (failed
cross-checks, unreadable documents). It never receives documents, names or ID numbers.
"""

from social_support.domain.documents import FORM_LABEL, CaseAssessment, Finding
from social_support.domain.models import AssessmentResult, Outcome, RuleVersionInfo
from social_support.labelling import HouseholdFacts, LabellingPolicy, load_policy

SEVERITY = {Outcome.APPROVE: 0, Outcome.SOFT_DECLINE: 1, Outcome.NEEDS_HUMAN_REVIEW: 2}
FLAG_REASON_MAX = 200  # decisions.flag_reason column

# Where each factor's value comes from, for the "source" shown next to every finding.
FACTOR_SOURCES = {
    "income_per_member_aed": ("Bank statement", FORM_LABEL),
    "net_monthly_income_aed": ("Bank statement",),
    "net_wealth_aed": ("Assets and liabilities",),
    "total_assets_aed": ("Assets and liabilities",),
    "total_liabilities_aed": ("Assets and liabilities",),
    "credit_score": ("Credit report",),
    "active_credit_defaults": ("Credit report",),
    "months_employed_last_24": ("Resume",),
    "employment_status": (FORM_LABEL,),
    "family_size": (FORM_LABEL,),
}

NEXT_STEPS = {
    "income_above_band": (
        "You may reapply if your household income falls or your family size changes."
    ),
    "high_net_wealth": "You may reapply if your household's net wealth changes.",
}
GENERAL_NEXT_STEP = "Economic enablement support (training, job matching) is still available."
SKIPPED = Finding(
    "rules_skipped",
    Outcome.NEEDS_HUMAN_REVIEW,
    "The eligibility rules could not be applied, so a caseworker will assess this application.",
    (),
)


class DocumentRuleAssessor:
    def __init__(self, policy: LabellingPolicy | None = None) -> None:
        self.policy = policy or load_policy("decision", "v1")
        self._rule_version = RuleVersionInfo(
            id=self.policy.version_id,
            name=self.policy.name,
            parameters={"policy": f"{self.policy.name}_{self.policy.version}"},
        )

    @property
    def rule_version(self) -> RuleVersionInfo:
        return self._rule_version

    def assess_case(
        self, facts: HouseholdFacts | None, findings: tuple[Finding, ...]
    ) -> CaseAssessment:
        all_findings = list(findings)
        if facts is not None:
            all_findings += [self._finding(label) for label in self.policy.evaluate_all(facts)]
        elif not any(f.outcome is Outcome.NEEDS_HUMAN_REVIEW for f in findings):
            all_findings.append(SKIPPED)
        if not all_findings:  # cannot happen with decision_v1, but never decide without a reason
            all_findings.append(SKIPPED)
        # Most severe first, so the reasons that decided the outcome lead (stable: file order kept).
        all_findings.sort(key=lambda f: -SEVERITY[f.outcome])

        outcome = max((f.outcome for f in all_findings), key=SEVERITY.__getitem__)
        review = [f.text for f in all_findings if f.outcome is Outcome.NEEDS_HUMAN_REVIEW]
        steps = ()
        if outcome is Outcome.SOFT_DECLINE:
            ids = [f.rule_id for f in all_findings if f.outcome is Outcome.SOFT_DECLINE]
            steps = (*(NEXT_STEPS[i] for i in ids if i in NEXT_STEPS), GENERAL_NEXT_STEP)
        result = AssessmentResult(
            outcome=outcome,
            income_per_member_aed=facts.income_per_member_aed if facts else None,
            explanation=" ".join(f.text for f in all_findings) + f" Rule: {self.rule_version.id}.",
            suggested_next_steps=steps,
            flag_reason=_truncate("; ".join(review)) if review else None,
            rule_version_id=self.rule_version.id,
        )
        return CaseAssessment(result, tuple(all_findings))

    @staticmethod
    def _finding(label) -> Finding:
        sources = dict.fromkeys(s for factor in label.compared for s in FACTOR_SOURCES[factor])
        return Finding(label.rule_id, label.outcome, label.reason, tuple(sources))


def _truncate(text: str) -> str:
    return text if len(text) <= FLAG_REASON_MAX else text[: FLAG_REASON_MAX - 1] + "…"

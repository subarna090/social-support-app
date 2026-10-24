"""Turn an outcome mix into exact per-outcome pack counts (research R4, FR-013)."""

import random
from decimal import Decimal

from social_support.domain.models import Outcome

ORDER = (Outcome.APPROVE, Outcome.SOFT_DECLINE, Outcome.NEEDS_HUMAN_REVIEW)  # tie-break order


def quotas(count: int, mix_pct: dict[str, int]) -> dict[Outcome, int]:
    """Largest-remainder method: every quota is within one pack of its exact share."""
    exact = {o: Decimal(count) * Decimal(mix_pct[o.value]) / Decimal(100) for o in ORDER}
    result = {o: int(exact[o]) for o in ORDER}
    leftover = count - sum(result.values())
    by_remainder = sorted(ORDER, key=lambda o: (-(exact[o] - result[o]), ORDER.index(o)))
    for outcome in by_remainder[:leftover]:
        result[outcome] += 1
    return result


def assign_targets(rng: random.Random, counts: dict[Outcome, int]) -> list[Outcome]:
    """One target outcome per pack slot, shuffled with the run's generator."""
    targets = [outcome for outcome in ORDER for _ in range(counts[outcome])]
    rng.shuffle(targets)
    return targets

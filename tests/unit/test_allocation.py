"""T032: largest-remainder quotas for the outcome mix (FR-013, research R4, rounding edge case)."""

import random
from collections import Counter

import pytest

from social_support.domain.models import Outcome
from social_support.synthetic.allocation import assign_targets, quotas

A, D, R = Outcome.APPROVE, Outcome.SOFT_DECLINE, Outcome.NEEDS_HUMAN_REVIEW


def mix(a, d, r):
    return {"APPROVE": a, "SOFT_DECLINE": d, "NEEDS_HUMAN_REVIEW": r}


@pytest.mark.parametrize(
    ("count", "shares", "expected"),
    [
        (10, (33, 33, 34), {A: 3, D: 3, R: 4}),
        (500, (40, 40, 20), {A: 200, D: 200, R: 100}),
        (30, (40, 40, 20), {A: 12, D: 12, R: 6}),
        (10, (0, 50, 50), {A: 0, D: 5, R: 5}),
        (1, (34, 33, 33), {A: 1, D: 0, R: 0}),
        (2, (50, 25, 25), {A: 1, D: 1, R: 0}),  # tie on remainders: APPROVE, SOFT_DECLINE first
    ],
)
def test_quotas(count, shares, expected):
    assert quotas(count, mix(*shares)) == expected


@pytest.mark.parametrize("count", [1, 7, 13, 99, 500, 4999])
def test_quotas_sum_and_stay_within_one_of_the_exact_share(count):
    shares = mix(37, 41, 22)
    result = quotas(count, shares)
    assert sum(result.values()) == count
    for outcome, n in result.items():
        assert abs(n - count * shares[outcome.value] / 100) < 1


def test_assign_targets_matches_quotas_and_is_deterministic():
    q = quotas(50, mix(40, 40, 20))
    first = assign_targets(random.Random(3), q)
    assert Counter(first) == Counter(q)
    assert first == assign_targets(random.Random(3), q)
    assert first != assign_targets(random.Random(4), q)

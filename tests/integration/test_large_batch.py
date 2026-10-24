"""Volume checks over at least 200 packs (SC-003, SC-004). Run: uv run pytest -m slow."""

import pytest

from social_support.synthetic.run import GenerationRequest, generate
from tests.integration import pack_checks

pytestmark = pytest.mark.slow


def test_200_consistent_packs_agree_with_their_answer_keys(tmp_path):  # SC-003
    run = generate(GenerationRequest(count=200, seed=2026, output_root=tmp_path))
    problems = {}
    for pack in sorted((run.folder / "packs").iterdir()):
        form, key = pack_checks.load(pack)
        found = pack_checks.shown_values_appear(pack, key) + pack_checks.marking_problems(pack)
        found += [f"{field} differs in {doc}" for field, doc in pack_checks.differences(key, form)]
        if found:
            problems[pack.name] = found
    assert problems == {}


def test_200_packs_at_30_percent_record_every_inconsistency(tmp_path):  # SC-004
    request = GenerationRequest(
        count=200, seed=2027, inconsistency_rate_pct=30, output_root=tmp_path
    )
    run = generate(request)
    affected, problems = 0, {}
    for pack in sorted((run.folder / "packs").iterdir()):
        form, key = pack_checks.load(pack)
        record = key["inconsistency"]
        affected += record is not None
        if pack_checks.differences(key, form) != pack_checks.expected_differences(record):
            problems[pack.name] = sorted(pack_checks.differences(key, form))
        elif record and not pack_checks.recorded_values_match(key, form):
            problems[pack.name] = ["recorded values differ from what is shown"]
    assert affected == 60
    assert problems == {}

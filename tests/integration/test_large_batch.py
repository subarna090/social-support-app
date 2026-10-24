"""Volume checks over at least 200 packs (SC-003; SC-004 is added with US2). Run: pytest -m slow."""

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

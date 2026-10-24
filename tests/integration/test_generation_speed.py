"""T043: SC-001, 100 complete packs in under 5 minutes on the reference laptop. Run: -m slow."""

import time

import pytest

from social_support.synthetic.run import GenerationRequest, generate

pytestmark = pytest.mark.slow


def test_100_packs_in_under_5_minutes(tmp_path):
    start = time.perf_counter()
    run = generate(GenerationRequest(count=100, seed=100, output_root=tmp_path))
    elapsed = time.perf_counter() - start
    print(f"\n100 packs generated in {elapsed:.1f} s")
    assert len(list((run.folder / "packs").iterdir())) == 100
    assert elapsed < 300

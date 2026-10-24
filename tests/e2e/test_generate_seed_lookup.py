"""T040: end to end over synthetic data (Principle V): generate, seed the 001 app, look up.

US4 scenario 2 and SC-008: 50 seeded packs are all accepted, and lookups return exactly the
details that were generated.
"""

import json

from social_support.synthetic.run import GenerationRequest, generate
from social_support.synthetic.seeding import seed_run
from social_support.ui.client import ApiClient


def test_generate_seed_and_look_up(tmp_path, client):
    folder = generate(GenerationRequest(count=50, seed=5, output_root=tmp_path)).folder
    api = ApiClient(base_url="http://testserver", transport=client._transport)

    summary = seed_run(folder, api)
    assert (summary.submitted, summary.rejected, summary.unreachable) == (50, 0, False)

    for pack_id, reference in list(summary.references.items())[:3]:
        form = json.loads((folder / "packs" / pack_id / "form.json").read_text(encoding="utf-8"))
        response = client.post(
            "/api/v1/applications/lookup",
            json={"reference_number": reference, "emirates_id": form["emirates_id"]},
        )
        assert response.status_code == 200
        assert response.json()["application"] == form["submission"]

"""T051: feature 004 end to end over synthetic data (Principle V, SC-001).

Generate the three demo packs, submit each through the UI's own ``ApiClient`` (real OCR, fake
LLM), fetch the enablement plan, and check the caseworker queue.
"""

from social_support.synthetic.demo import write_demo
from social_support.ui.client import ApiClient
from tests.conftest import TEST_PASSCODE
from tests.fixtures.demo_upload import form_values, pack_files


def test_three_demo_applicants_get_their_three_outcomes(tmp_path, client):
    written = write_demo(tmp_path)
    api = ApiClient(base_url="http://testserver", transport=client._transport)

    references = {}
    for name, expected, _form in written:
        pack = tmp_path / name
        result = api.submit_with_documents(form_values(pack), pack_files(pack))
        assert result["decision"]["outcome"] == expected.value, name
        assert result["decision"]["findings"], name
        assert all(f["sources"] for f in result["decision"]["findings"]), name  # SC-004
        plan = api.enablement(result["reference_number"], form_values(pack)["emirates_id"])
        assert plan["training"] and plan["job_matches"] and not plan["is_fallback"]
        references[name] = result["reference_number"]

    queue = api.review_queue(TEST_PASSCODE)["items"]
    assert [item["reference_number"] for item in queue] == [references["review"]]
    assert len(queue[0]["reasons"]) >= 2

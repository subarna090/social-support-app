"""T039: seeding the running 001 app through its submission endpoint (FR-019, FR-020, R11).

The 001 app runs in-process: the generator's ApiClient talks to a FastAPI TestClient's transport,
so the real HTTP path (schemas, validation, service, storage) is exercised without a server.
"""

import csv
import json

import httpx
import pytest

from social_support.synthetic import cli
from social_support.synthetic.run import GenerationRequest, RequestError, generate
from social_support.synthetic.seeding import seed_run
from social_support.ui.client import ApiClient


@pytest.fixture(scope="module")
def run_folder(tmp_path_factory):
    out = tmp_path_factory.mktemp("seed")
    return generate(GenerationRequest(count=5, seed=31, output_root=out)).folder


@pytest.fixture
def api(client):
    return ApiClient(base_url="http://testserver", transport=client._transport)


def report(folder):
    with (folder / "seeding_report.csv").open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def test_every_pack_is_submitted_and_reported(run_folder, api):  # US4 scenario 1
    summary = seed_run(run_folder, api)
    assert (summary.submitted, summary.rejected, summary.unreachable) == (5, 0, False)
    names, rows = report(run_folder)
    assert names == [
        "pack_id",
        "status",
        "reference_number",
        "returned_outcome",
        "eligibility_outcome",
        "matched",
    ]
    assert [r["pack_id"] for r in rows] == [f"pack-{i:04d}" for i in range(1, 6)]
    for row in rows:
        key = json.loads(
            (run_folder / "packs" / row["pack_id"] / "answer_key.json").read_text(encoding="utf-8")
        )
        assert row["status"] == "submitted"
        assert row["reference_number"].startswith("SSA-")
        assert row["eligibility_outcome"] == key["eligibility"]["outcome"]
        expected = str(row["returned_outcome"] == row["eligibility_outcome"]).lower()
        assert row["matched"] == expected
    assert summary.matched == sum(r["matched"] == "true" for r in rows)


def test_limit_seeds_only_the_first_packs(run_folder, api):
    assert seed_run(run_folder, api, limit=2).submitted == 2
    assert [r["pack_id"] for r in report(run_folder)[1]] == ["pack-0001", "pack-0002"]


class FailsOnThirdRequest(httpx.BaseTransport):
    def __init__(self, inner):
        self.inner, self.calls = inner, 0

    def handle_request(self, request):
        self.calls += 1
        if self.calls >= 3:
            raise httpx.ConnectError("connection refused", request=request)
        return self.inner.handle_request(request)


def test_unreachable_api_stops_and_reports_only_submitted_packs(run_folder, client):  # FR-020
    api = ApiClient(base_url="http://testserver", transport=FailsOnThirdRequest(client._transport))
    summary = seed_run(run_folder, api)
    assert (summary.submitted, summary.unreachable) == (2, True)
    assert [r["pack_id"] for r in report(run_folder)[1]] == ["pack-0001", "pack-0002"]


def test_rejected_pack_is_recorded_and_seeding_continues(tmp_path, api):
    folder = generate(GenerationRequest(count=3, seed=32, output_root=tmp_path)).folder
    form_path = folder / "packs" / "pack-0002" / "form.json"
    form = json.loads(form_path.read_text(encoding="utf-8"))
    form["submission"]["family_size"] = 0
    form_path.write_text(json.dumps(form), encoding="utf-8")

    summary = seed_run(folder, api)
    assert (summary.submitted, summary.rejected) == (2, 1)
    rows = {r["pack_id"]: r for r in report(folder)[1]}
    assert rows["pack-0002"]["status"] == "rejected"
    assert rows["pack-0002"]["reference_number"] == rows["pack-0002"]["matched"] == ""
    assert rows["pack-0003"]["status"] == "submitted"


def test_folder_without_run_record_is_refused(tmp_path, api):
    with pytest.raises(RequestError, match="not a generated run"):
        seed_run(tmp_path, api)


# --- CLI (contracts/cli.md) --------------------------------------------------------------------


@pytest.fixture
def cli_api(client, monkeypatch):
    monkeypatch.setattr(
        cli,
        "ApiClient",
        lambda base_url=None: ApiClient(base_url="http://testserver", transport=client._transport),
    )


def test_seed_command_prints_summary_without_personal_data(run_folder, cli_api, capsys):
    code = cli.main(["seed", "--run", str(run_folder)])
    out, err = capsys.readouterr()
    assert code == 0, err
    assert out.strip().splitlines()[-1].startswith("Seeded 5 packs: ")
    assert "Report: " in out
    for pack in (run_folder / "packs").iterdir():
        form = json.loads((pack / "form.json").read_text(encoding="utf-8"))
        for secret in (form["full_name"], form["emirates_id"], form["net_monthly_income_aed"]):
            assert secret not in out


def test_seed_command_exits_1_when_unreachable(run_folder, monkeypatch, capsys):
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)

    monkeypatch.setattr(
        cli,
        "ApiClient",
        lambda base_url=None: ApiClient(base_url="http://x", transport=httpx.MockTransport(refuse)),
    )
    code = cli.main(["seed", "--run", str(run_folder)])
    out, err = capsys.readouterr()
    assert code == 1
    assert "The assessment service can't be reached. Check that the API is running." in err
    assert "Submitted 0 of 5 packs before stopping." in err


def test_seed_command_rejects_a_folder_that_is_not_a_run(tmp_path, capsys):
    assert cli.main(["seed", "--run", str(tmp_path)]) == 2
    assert f"not a generated run: {tmp_path}" in capsys.readouterr().err

"""T014: a generated batch has readable, consistent, synthetic-marked documents (US1)."""

import json
import logging
from decimal import Decimal

import pytest
from PIL import Image

from social_support.api.schemas import SubmitApplicationRequest
from social_support.labelling import HouseholdFacts, load_policy
from social_support.synthetic.documents.emirates_id import render_emirates_id
from social_support.synthetic.run import GenerationRequest, generate
from tests.integration import pack_checks

SEED = 42  # this batch includes a zero-income household (asserted below)
FILES = {
    "form.json",
    "answer_key.json",
    "bank_statement.pdf",
    "emirates_id.png",
    "resume.pdf",
    "assets_liabilities.xlsx",
    "credit_report.pdf",
}


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    return generate(
        GenerationRequest(count=10, seed=SEED, output_root=tmp_path_factory.mktemp("o"))
    )


@pytest.fixture(scope="module")
def packs(run):
    return sorted((run.folder / "packs").iterdir())


def test_layout_matches_the_contract(run, packs):
    assert (run.folder / "run.json").is_file()
    assert [p.name for p in packs] == [f"pack-{i:04d}" for i in range(1, 11)]
    for pack in packs:
        assert {f.name for f in pack.iterdir()} == FILES


def test_submission_block_is_a_valid_application(packs):
    for pack in packs:
        form, _ = pack_checks.load(pack)
        SubmitApplicationRequest.model_validate(form["submission"])
        assert form["submission"]["full_name"] == form["full_name"]


def test_documents_show_the_answer_key_values(packs):
    for pack in packs:
        _, key = pack_checks.load(pack)
        assert pack_checks.shown_values_appear(pack, key) == [], pack.name


def test_consistent_packs_agree_everywhere(packs):  # FR-004, SC-003
    for pack in packs:
        form, key = pack_checks.load(pack)
        assert key["inconsistency"] is None
        assert pack_checks.differences(key, form) == set(), pack.name


def test_every_document_is_marked_synthetic(packs):  # FR-017, SC-006
    for pack in packs:
        assert pack_checks.marking_problems(pack) == []
        image = Image.open(pack / "emirates_id.png").convert("RGB")
        banner = image.crop((0, image.height - 60, image.width, image.height))
        pixels = list(banner.get_flattened_data())
        red = sum(r > 150 and g < 90 and b < 90 for r, g, b in pixels)
        assert red / len(pixels) > 0.6, f"{pack.name}: ID card banner is not predominantly red"


def test_id_card_fields_are_actually_drawn(packs, tmp_path):  # U2
    _, key = pack_checks.load(packs[0])
    rendered = render_emirates_id(key["documents"]["emirates_id"], tmp_path / "card.png")
    image = Image.open(rendered.path).convert("L")
    background = image.getpixel((5, image.height // 2))
    assert set(rendered.field_boxes) == {
        "full_name",
        "emirates_id",
        "nationality",
        "date_of_birth",
        "sex",
        "expiry_date",
    }
    for field, box in rendered.field_boxes.items():
        region = list(image.crop(box).get_flattened_data())
        assert sum(abs(p - background) > 60 for p in region) > 20, f"{field} not drawn"


def test_emirates_ids_use_the_reserved_block(packs):  # FR-016, SC-006
    for pack in packs:
        form, _ = pack_checks.load(pack)
        assert form["emirates_id"].split("-")[2].startswith("00")


def test_labels_come_from_the_policy(packs):  # FR-010, FR-011
    policy = load_policy()
    for pack in packs:
        _, key = pack_checks.load(pack)
        f = key["facts"]
        facts = HouseholdFacts(
            **{
                **f,
                **{k: Decimal(v) for k, v in f.items() if k.endswith("_aed")},
            }
        )
        expected = policy.evaluate(facts)
        assert key["eligibility"]["outcome"] == expected.outcome.value
        assert key["eligibility"]["rule_id"] == expected.rule_id
        assert key["eligibility"]["policy_version_id"] == policy.version_id
        assert key["expected_routing"] == key["eligibility"]["outcome"]


def test_zero_income_household_has_no_income_credits(packs):  # spec edge case
    zero = []
    for pack in packs:
        _, key = pack_checks.load(pack)
        if key["facts"]["net_monthly_income_aed"] == "0.00":
            zero.append(pack)
            assert key["documents"]["bank_statement"]["income_credits"] == []
            assert "Salary" not in pack_checks.pdf_text(pack / "bank_statement.pdf")
    assert zero, "seed no longer produces a zero-income household; pick another SEED"


def test_run_record(run):
    record = json.loads((run.folder / "run.json").read_text(encoding="utf-8"))
    assert record["format"] == "pack-format/1"
    assert record["run_id"] == run.run_id
    assert record["counts"]["packs"] == 10
    assert sum(record["counts"]["eligibility"].values()) == 10
    assert record["generated_at"].endswith("Z")


def test_logs_carry_ids_but_no_personal_data(tmp_path, caplog):  # U3, Principle I/VII
    from social_support.services.tracing import JsonFormatter

    caplog.set_level(logging.INFO, logger="social_support")
    run = generate(GenerationRequest(count=3, seed=9, output_root=tmp_path))
    lines = [
        JsonFormatter().format(r) for r in caplog.records if r.name.startswith("social_support")
    ]
    output = "\n".join(lines)
    assert run.run_id in output and '"pack_id": "pack-0001"' in output
    for pack in sorted((run.folder / "packs").iterdir()):
        form, _ = pack_checks.load(pack)
        for secret in (form["full_name"], form["emirates_id"], form["net_monthly_income_aed"]):
            assert secret not in output

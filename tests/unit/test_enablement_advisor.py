"""T044: the Ollama enablement advisor with a mocked HTTP transport (no model needed)."""

import json

import httpx
import pytest

from social_support.domain.enablement import EnablementProfile, income_band
from social_support.enablement.ollama import EnablementError, OllamaEnablementAdvisor

PROFILE = EnablementProfile(
    skills=("Electrical maintenance", "First aid"),
    education="Crescent Polytechnic (Demo), graduated 2006",
    years_experience="4.8",
    last_job_title="Technician",
    employment_status="EMPLOYED",
    months_employed_last_24=24,
    family_size=4,
    outcome="NEEDS_HUMAN_REVIEW",
    income_band="borderline",
)
GOOD = {
    "training": ["Solar PV installation course", "Advanced electrical safety"],
    "job_matches": ["Maintenance technician, facilities company"],
    "career_counselling": "Your maintenance experience fits the growing solar sector.",
}


def advisor(handler, **kwargs) -> OllamaEnablementAdvisor:
    return OllamaEnablementAdvisor(
        url="http://ollama.test",
        model="qwen2.5:7b",
        timeout_s=5,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def answering(content, seen: list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        text = content if isinstance(content, str) else json.dumps(content)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": text}})

    return handler


def test_valid_answer_becomes_a_plan():
    seen = []
    plan = advisor(answering(GOOD, seen)).advise(PROFILE)
    assert plan.training == tuple(GOOD["training"])
    assert plan.job_matches == tuple(GOOD["job_matches"])
    assert plan.career_counselling == GOOD["career_counselling"]
    assert (plan.is_fallback, plan.model) == (False, "qwen2.5:7b")
    body = json.loads(seen[0].content)
    assert seen[0].url == "http://ollama.test/api/chat"
    assert (body["model"], body["format"], body["stream"]) == ("qwen2.5:7b", "json", False)


def test_the_request_carries_only_the_anonymised_profile():
    seen = []
    advisor(answering(GOOD, seen)).advise(PROFILE)
    sent = seen[0].content.decode()
    # The review demo applicant's identity, employer and income never reach the model.
    for secret in ("Hassan", "Al Zaabi", "784-1985", "Al Waha Engineering", "9000", "7000"):
        assert secret not in sent
    user = json.loads(json.loads(sent)["messages"][-1]["content"])
    assert user == PROFILE.as_dict()


def test_lists_are_capped_at_five_items():
    many = GOOD | {"training": [f"Course {i}" for i in range(9)]}
    assert len(advisor(answering(many)).advise(PROFILE).training) == 5


@pytest.mark.parametrize(
    "content",
    [
        "not json at all",
        {"training": ["x"], "job_matches": ["y"]},  # missing key
        GOOD | {"training": []},  # empty list
        GOOD | {"job_matches": "a string"},  # wrong type
        GOOD | {"career_counselling": "  "},  # blank
        GOOD | {"training": ["ok", 3]},  # non-string item
    ],
)
def test_unusable_answers_raise(content):
    with pytest.raises(EnablementError):
        advisor(answering(content)).advise(PROFILE)


def test_timeout_raises():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(EnablementError):
        advisor(handler).advise(PROFILE)


def test_server_error_raises():
    with pytest.raises(EnablementError):
        advisor(lambda request: httpx.Response(500, text="model not found")).advise(PROFILE)


@pytest.mark.parametrize(
    ("value", "band"),
    [(None, "unknown"), ("1999.99", "below_band"), ("2000", "borderline"), ("2500", "borderline"),
     ("2500.01", "above_band")],
)  # fmt: skip
def test_income_band(value, band):
    from decimal import Decimal

    assert income_band(None if value is None else Decimal(value)) == band

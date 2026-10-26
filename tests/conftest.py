"""Shared fixtures: in-memory database, API client factory and fake assessors (T017)."""

from collections.abc import Callable
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from social_support.api.main import create_app
from social_support.config import Settings
from social_support.domain.enablement import EnablementPlan, EnablementProfile
from social_support.domain.models import ApplicationInput, AssessmentResult, RuleVersionInfo
from social_support.synthetic.demo import write_demo

TEST_PASSCODE = "test-passcode"


class FailingAssessor:
    """An assessor whose assessment always raises, to exercise the fallback path (FR-015)."""

    rule_version = RuleVersionInfo(id="failing/test", name="failing", parameters={})

    def assess(self, application: ApplicationInput) -> AssessmentResult:
        raise RuntimeError("assessment engine exploded")


class FakeAdvisor:
    """A deterministic enablement advisor: tests never call the real local model."""

    model = "fake-model"

    def __init__(self) -> None:
        self.profiles: list[EnablementProfile] = []

    def advise(self, profile: EnablementProfile) -> EnablementPlan:
        self.profiles.append(profile)
        skill = profile.skills[0] if profile.skills else "your experience"
        return EnablementPlan(
            training=(f"Advanced course building on {skill}",),
            job_matches=(f"Senior {profile.last_job_title or 'entry-level'} roles",),
            career_counselling="Use your experience to move into a better-paid role.",
            model=self.model,
        )


class FailingAdvisor:
    model = "failing-model"

    def advise(self, profile: EnablementProfile) -> EnablementPlan:
        raise TimeoutError("the model took too long")


def make_settings(**overrides) -> Settings:
    values = {"database_url": "sqlite://", "caseworker_passcode": TEST_PASSCODE} | overrides
    return Settings(_env_file=None, **values)


@pytest.fixture
def make_client(tmp_path) -> Callable[..., TestClient]:
    """Factory: ``make_client(assessor=..., advisor=..., **settings_overrides)`` returns a started
    TestClient.

    Uploaded documents (feature 004) go to a per-test folder, never ``data/``; the enablement
    advisor defaults to ``FakeAdvisor``, so no test ever calls the real local model.
    """
    with ExitStack() as stack:

        def _make(assessor=None, advisor=None, **overrides) -> TestClient:
            overrides.setdefault("upload_dir", tmp_path / "uploads")
            app = create_app(
                make_settings(**overrides), assessor=assessor, advisor=advisor or FakeAdvisor()
            )
            return stack.enter_context(TestClient(app))

        yield _make


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def db_session(client) -> Session:
    with client.app.state.sessionmaker() as session:
        yield session


@pytest.fixture(scope="session")
def demo_packs(tmp_path_factory):
    """The three feature 004 demo packs, written once per test session: ``{name: folder}``."""
    out = tmp_path_factory.mktemp("demo")
    write_demo(out)
    return {name: out / name for name in ("approve", "soft_decline", "review")}

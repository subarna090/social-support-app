"""Shared fixtures: in-memory database, API client factory and fake assessors (T017)."""

from collections.abc import Callable
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from social_support.api.main import create_app
from social_support.config import Settings
from social_support.domain.models import ApplicationInput, AssessmentResult, RuleVersionInfo

TEST_PASSCODE = "test-passcode"


class FailingAssessor:
    """An assessor whose assessment always raises, to exercise the fallback path (FR-015)."""

    rule_version = RuleVersionInfo(id="failing/test", name="failing", parameters={})

    def assess(self, application: ApplicationInput) -> AssessmentResult:
        raise RuntimeError("assessment engine exploded")


def make_settings(**overrides) -> Settings:
    values = {"database_url": "sqlite://", "caseworker_passcode": TEST_PASSCODE} | overrides
    return Settings(_env_file=None, **values)


@pytest.fixture
def make_client() -> Callable[..., TestClient]:
    """Factory: ``make_client(assessor=..., **settings_overrides)`` returns a started TestClient."""
    with ExitStack() as stack:

        def _make(assessor=None, **overrides) -> TestClient:
            app = create_app(make_settings(**overrides), assessor=assessor)
            return stack.enter_context(TestClient(app))

        yield _make


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def db_session(client) -> Session:
    with client.app.state.sessionmaker() as session:
        yield session

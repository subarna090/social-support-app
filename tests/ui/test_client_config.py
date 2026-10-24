"""T051: the UI client finds the API from API_BASE_URL in the environment or in a local .env."""

import pytest

from social_support.ui.client import ApiClient


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("API_BASE_URL", raising=False)
    return tmp_path


def _base_url() -> str:
    return str(ApiClient()._http.base_url).rstrip("/")


def test_defaults_to_local_api():
    assert _base_url() == "http://127.0.0.1:8000"


def test_reads_api_base_url_from_dotenv(isolated):
    (isolated / ".env").write_text("API_BASE_URL=http://api.example.test:9000\n", encoding="utf-8")
    assert _base_url() == "http://api.example.test:9000"


def test_environment_variable_wins_over_dotenv(isolated, monkeypatch):
    (isolated / ".env").write_text("API_BASE_URL=http://from-dotenv:9000\n", encoding="utf-8")
    monkeypatch.setenv("API_BASE_URL", "http://from-env:9001")
    assert _base_url() == "http://from-env:9001"


def test_explicit_argument_wins_over_everything(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "http://from-env:9001")
    assert str(ApiClient("http://explicit:1")._http.base_url).rstrip("/") == "http://explicit:1"

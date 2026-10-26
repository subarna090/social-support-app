"""Enablement recommendations from a local Ollama model (feature 004, research R7).

Plain HTTP with ``httpx`` (no SDK, Principle VI). JSON mode keeps qwen2.5's answer parseable; any
answer that is not exactly the expected shape raises, and the service shows the fallback plan.
"""

import json

import httpx

from social_support.domain.enablement import EnablementPlan, EnablementProfile

MAX_ITEMS = 5
MAX_ITEM_CHARS = 300
SYSTEM_PROMPT = """You are a career adviser for a government social support programme in the \
United Arab Emirates. You receive an anonymised applicant profile as JSON: skills, education, \
years of experience, last job title, employment status, months worked in the last 24, family \
size, the support decision and an income band.

Recommend economic enablement support that fits THIS profile, building on the applicant's actual \
skills and last job title:
- "training": 2 to 4 specific upskilling or training courses or certifications;
- "job_matches": 2 to 4 realistic job roles or sectors to apply to now;
- "career_counselling": one short paragraph (at most 3 sentences) of practical advice.

Each list item is one short sentence. Do not invent personal details, names or employers.
Answer ONLY with a JSON object with exactly these keys: "training", "job_matches", \
"career_counselling"."""


class EnablementError(Exception):
    """The model could not be reached or gave an unusable answer."""


def _items(data: dict, key: str) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise EnablementError(f"{key} is not a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise EnablementError(f"{key} contains a non-text item")
    return tuple(item.strip()[:MAX_ITEM_CHARS] for item in value[:MAX_ITEMS])


class OllamaEnablementAdvisor:
    def __init__(
        self,
        url: str,
        model: str,
        timeout_s: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        self._model = model
        self.timeout_s = timeout_s
        self.transport = transport

    @property
    def model(self) -> str:
        return self._model

    def advise(self, profile: EnablementProfile) -> EnablementPlan:
        body = {
            "model": self._model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.3},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(profile.as_dict())},
            ],
        }
        try:
            with httpx.Client(timeout=self.timeout_s, transport=self.transport) as client:
                response = client.post(f"{self.url}/api/chat", json=body)
                response.raise_for_status()
                content = response.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise EnablementError(f"the model call failed ({type(exc).__name__})") from exc
        try:
            data = json.loads(content)
        except ValueError as exc:
            raise EnablementError("the model did not answer with JSON") from exc
        if not isinstance(data, dict):
            raise EnablementError("the model answer is not a JSON object")
        counselling = data.get("career_counselling")
        if not isinstance(counselling, str) or not counselling.strip():
            raise EnablementError("career_counselling is missing")
        return EnablementPlan(
            training=_items(data, "training"),
            job_matches=_items(data, "job_matches"),
            career_counselling=counselling.strip()[: MAX_ITEM_CHARS * 3],
            is_fallback=False,
            model=self._model,
        )

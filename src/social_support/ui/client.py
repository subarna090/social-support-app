"""HTTP client the Streamlit UI uses to talk to the API (research R1).

This module must not import anything else from ``social_support``: the UI only knows the API.
"""

import os

import httpx

UNREACHABLE = "The assessment service can't be reached. Check that the API is running."


class ApiError(Exception):
    def __init__(
        self, status_code: int, detail: str, field_errors: dict[str, str] | None = None
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.field_errors = field_errors or {}


class ApiClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url or os.environ.get("API_BASE_URL", "http://127.0.0.1:8000"),
            timeout=timeout,
            transport=transport,
        )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError(0, UNREACHABLE) from exc
        if response.is_success:
            return response.json()
        try:
            body = response.json()
        except ValueError:
            body = {}
        field_errors = {e["field"]: e["message"] for e in body.get("errors", [])}
        detail = body.get("detail") or f"Request failed ({response.status_code})."
        raise ApiError(response.status_code, detail, field_errors)

    def submit(self, payload: dict) -> dict:
        return self._request("POST", "/api/v1/applications", json=payload)

    def review_queue(self, passcode: str) -> dict:
        headers = {"X-Caseworker-Passcode": passcode}
        return self._request("GET", "/api/v1/review-queue", headers=headers)

    def lookup(self, reference_number: str, emirates_id: str) -> dict:
        body = {"reference_number": reference_number, "emirates_id": emirates_id}
        return self._request("POST", "/api/v1/applications/lookup", json=body)

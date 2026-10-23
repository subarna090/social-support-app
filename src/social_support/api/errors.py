"""422 handler producing the flat ``errors[]`` shape from contracts/api.md (FR-003)."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from social_support.domain.models import EmploymentStatus
from social_support.domain.validation import (
    MSG_EMIRATES_ID,
    MSG_FAMILY_SIZE,
    MSG_FULL_NAME,
    MSG_INCOME,
)

FIELD_MESSAGES = {
    "full_name": MSG_FULL_NAME,
    "emirates_id": MSG_EMIRATES_ID,
    "family_size": MSG_FAMILY_SIZE,
    "net_monthly_income_aed": MSG_INCOME,
    "employment_status": "Employment status must be one of: "
    + ", ".join(s.label for s in EmploymentStatus)
    + ".",
}
MSG_NOT_ACCEPTED = "This field is not accepted."


def _field_name(loc: tuple) -> str:
    parts = [str(p) for p in loc if p != "body"]
    return parts[-1] if parts else "body"


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors: dict[str, str] = {}
    for error in exc.errors():
        name = _field_name(tuple(error.get("loc", ())))
        if name in errors:
            continue  # one entry per field
        if error.get("type") == "extra_forbidden":
            errors[name] = MSG_NOT_ACCEPTED
        else:
            errors[name] = FIELD_MESSAGES.get(name, error.get("msg", "Invalid value."))
    return JSONResponse(
        status_code=422,
        content={"errors": [{"field": f, "message": m} for f, m in errors.items()]},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_error_handler)

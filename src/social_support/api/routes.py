"""HTTP routes for API v1 (contracts/api.md)."""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from social_support.api.schemas import (
    DecisionOut,
    SubmitApplicationRequest,
    SubmitApplicationResponse,
    iso_utc,
)
from social_support.persistence.db import get_session
from social_support.persistence.repository import ApplicationRepository
from social_support.services.applications import ApplicationService, Submission

router = APIRouter()


def get_service(request: Request, session: Session = Depends(get_session)) -> ApplicationService:
    return ApplicationService(ApplicationRepository(session), request.app.state.assessor)


@router.get("/health")
def health(request: Request) -> dict:
    assessor = request.app.state.assessor
    return {
        "status": "ok",
        "assessor": request.app.state.settings.assessor,
        "rule_version": assessor.rule_version.id,
    }


@router.post(
    "/applications",
    status_code=status.HTTP_201_CREATED,
    response_model=SubmitApplicationResponse,
)
def submit_application(
    body: SubmitApplicationRequest, service: ApplicationService = Depends(get_service)
) -> SubmitApplicationResponse:
    result = service.submit(Submission(**body.model_dump()))
    return SubmitApplicationResponse(
        reference_number=result.reference_number,
        submitted_at=iso_utc(result.submitted_at),
        previous_application_exists=result.previous_application_exists,
        decision=DecisionOut.from_assessment(result.assessment, result.decided_at),
    )

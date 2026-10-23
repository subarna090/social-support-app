"""HTTP routes for API v1 (contracts/api.md)."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from social_support.api.schemas import (
    ApplicationOut,
    DecisionOut,
    LookupRequest,
    LookupResponse,
    SubmitApplicationRequest,
    SubmitApplicationResponse,
    iso_utc,
    money,
)
from social_support.persistence.db import get_session
from social_support.persistence.repository import ApplicationRepository
from social_support.services.applications import ApplicationService, Submission

router = APIRouter()

NOT_FOUND_DETAIL = "No application found for the details provided."


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


@router.post("/applications/lookup", response_model=LookupResponse)
def lookup_application(
    body: LookupRequest, service: ApplicationService = Depends(get_service)
) -> LookupResponse:
    found = service.lookup(body.reference_number, body.emirates_id)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_DETAIL)
    submission, result = found.submission, found.result
    return LookupResponse(
        reference_number=result.reference_number,
        submitted_at=iso_utc(result.submitted_at),
        previous_application_exists=result.previous_application_exists,
        application=ApplicationOut(
            full_name=submission.full_name,
            emirates_id=submission.emirates_id,
            family_size=submission.family_size,
            net_monthly_income_aed=money(submission.net_monthly_income_aed),
            employment_status=submission.employment_status.value,
        ),
        decision=DecisionOut.from_assessment(result.assessment, result.decided_at),
    )

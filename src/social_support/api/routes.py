"""HTTP routes for API v1 (contracts/api.md)."""

import secrets
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from social_support.api.schemas import (
    ApplicationOut,
    CrossCheckOut,
    DecisionOut,
    DocumentOut,
    DocumentSubmissionResponse,
    EnablementOut,
    EnablementRequest,
    LookupRequest,
    LookupResponse,
    ReviewQueueItem,
    ReviewQueueResponse,
    SubmitApplicationRequest,
    SubmitApplicationResponse,
    SubmitWithDocumentsForm,
    iso_utc,
    money,
)
from social_support.domain.documents import DocumentType
from social_support.persistence.db import get_session
from social_support.persistence.repository import ApplicationRepository
from social_support.services.applications import (
    ApplicationService,
    DocumentSettings,
    Submission,
)
from social_support.services.uploads import Upload

router = APIRouter()

NOT_FOUND_DETAIL = "No application found for the details provided."
ACCESS_DENIED_DETAIL = "Access denied."


def get_service(request: Request, session: Session = Depends(get_session)) -> ApplicationService:
    state = request.app.state
    settings = state.settings
    return ApplicationService(
        ApplicationRepository(session),
        state.assessor,
        case_assessor=state.case_assessor,
        document_settings=DocumentSettings(
            upload_dir=settings.upload_dir,
            income_tolerance_pct=settings.income_tolerance_pct,
            ocr_min_confidence=settings.ocr_min_confidence,
        ),
        advisor=state.advisor,
    )


def require_caseworker(
    request: Request,
    passcode: str | None = Header(default=None, alias="X-Caseworker-Passcode"),
) -> None:
    """Shared caseworker passcode check (Clarification Q3). Fails closed if none is set."""
    configured = request.app.state.settings.caseworker_passcode
    expected = configured.get_secret_value() if configured else ""
    given = passcode or ""
    if not expected or not secrets.compare_digest(given.encode(), expected.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ACCESS_DENIED_DETAIL)


@router.get("/health")
def health(request: Request) -> dict:
    assessor = request.app.state.assessor
    return {
        "status": "ok",
        "assessor": request.app.state.settings.assessor,
        "rule_version": assessor.rule_version.id,
        "enablement_model": request.app.state.settings.enablement_model,
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


@router.post(
    "/applications/with-documents",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentSubmissionResponse,
)
def submit_with_documents(
    body: Annotated[SubmitWithDocumentsForm, Form()],
    bank_statement: Annotated[UploadFile, File()],
    emirates_id_card: Annotated[UploadFile, File()],
    resume: Annotated[UploadFile, File()],
    assets_liabilities: Annotated[UploadFile, File()],
    credit_report: Annotated[UploadFile, File()],
    service: ApplicationService = Depends(get_service),
) -> DocumentSubmissionResponse:
    """Feature 004: the form plus five documents. An unreadable document is not an error here:
    it routes the case to human review (spec edge cases)."""
    files = {
        DocumentType.BANK_STATEMENT: bank_statement,
        DocumentType.EMIRATES_ID_CARD: emirates_id_card,
        DocumentType.RESUME: resume,
        DocumentType.ASSETS_LIABILITIES: assets_liabilities,
        DocumentType.CREDIT_REPORT: credit_report,
    }
    uploads = [Upload(t, f.filename or "", f.file.read()) for t, f in files.items()]
    outcome = service.submit_with_documents(Submission(**body.model_dump()), uploads)
    result = outcome.result
    return DocumentSubmissionResponse(
        reference_number=result.reference_number,
        submitted_at=iso_utc(result.submitted_at),
        previous_application_exists=result.previous_application_exists,
        decision=DecisionOut.from_assessment(result.assessment, result.decided_at, result.findings),
        documents=[DocumentOut.from_document(d) for d in outcome.documents.values()],
        cross_checks=[CrossCheckOut.from_result(c) for c in outcome.cross_checks],
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
        decision=DecisionOut.from_assessment(result.assessment, result.decided_at, result.findings),
    )


@router.post("/applications/{reference_number}/enablement", response_model=EnablementOut)
def enablement(
    reference_number: str,
    body: EnablementRequest,
    service: ApplicationService = Depends(get_service),
) -> EnablementOut:
    """US4: economic enablement recommendations from the local LLM (or the labelled fallback).
    A missing reference and a mismatched Emirates ID get the same 404 as lookup."""
    found = service.enablement_for(reference_number, body.emirates_id)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_DETAIL)
    plan = found.plan
    return EnablementOut(
        training=list(plan.training),
        job_matches=list(plan.job_matches),
        career_counselling=plan.career_counselling,
        is_fallback=plan.is_fallback,
        model=plan.model,
        created_at=iso_utc(found.created_at),
    )


@router.get(
    "/review-queue",
    response_model=ReviewQueueResponse,
    dependencies=[Depends(require_caseworker)],
)
def review_queue(service: ApplicationService = Depends(get_service)) -> ReviewQueueResponse:
    return ReviewQueueResponse(
        items=[
            ReviewQueueItem(
                reference_number=item.reference_number,
                full_name=item.full_name,
                submitted_at=iso_utc(item.submitted_at),
                flag_reason=item.flag_reason,
                reasons=list(item.reasons),
            )
            for item in service.review_queue()
        ]
    )

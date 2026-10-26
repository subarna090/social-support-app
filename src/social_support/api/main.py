"""FastAPI application factory.

Run with: ``uv run uvicorn social_support.api.main:app --reload``
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from social_support.api.errors import register_error_handlers
from social_support.api.routes import router
from social_support.assessment.document_rules import DocumentRuleAssessor
from social_support.config import Settings, get_settings
from social_support.domain.assessor import FALLBACK_RULE_VERSION, Assessor, build_assessor
from social_support.domain.enablement import EnablementAdvisor
from social_support.enablement.ollama import OllamaEnablementAdvisor
from social_support.labelling import load_policy
from social_support.persistence.db import init_db, make_engine, make_sessionmaker
from social_support.persistence.repository import ApplicationRepository
from social_support.services.tracing import configure_logging


def create_app(
    settings: Settings | None = None,
    assessor: Assessor | None = None,
    advisor: EnablementAdvisor | None = None,
) -> FastAPI:
    """Build the app. ``assessor`` and ``advisor`` override the configured ones (used by tests)."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        engine = make_engine(settings.database_url)
        init_db(engine)
        session_factory = make_sessionmaker(engine)
        active_assessor = assessor or build_assessor(settings)
        name, version = settings.decision_policy.rsplit("_", 1)  # "decision_v1"
        case_assessor = DocumentRuleAssessor(load_policy(name, version))
        with session_factory() as session:
            repo = ApplicationRepository(session)
            repo.ensure_rule_version(active_assessor.rule_version)
            repo.ensure_rule_version(case_assessor.rule_version)
            repo.ensure_rule_version(FALLBACK_RULE_VERSION)

        app.state.settings = settings
        app.state.engine = engine
        app.state.sessionmaker = session_factory
        app.state.assessor = active_assessor
        app.state.case_assessor = case_assessor
        app.state.advisor = advisor or OllamaEnablementAdvisor(
            url=settings.ollama_url,
            model=settings.enablement_model,
            timeout_s=settings.enablement_timeout_s,
        )
        yield
        engine.dispose()

    app = FastAPI(title="Social Support Assessor API", version="0.1.0", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()

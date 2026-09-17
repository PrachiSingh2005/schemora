import uuid
# Reload trigger for Knowledge Base 70-Query Evaluation Suite 5
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.core.database import engine
from app.db.base import Base
from app.api.v1.health import router as health_router
from app.api.v1.profile import router as profile_router
from app.api.v1.schemes import router as schemes_router
from app.api.v1.ai import router as ai_router
from app.api.v1.documents import router as documents_router
from app.api.v1.saved_schemes import router as saved_schemes_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.admin import router as admin_router
from app.schemas.common import ErrorResponse, ErrorDetail

setup_logging()


def run_sqlite_schema_migrations():
    if "sqlite" in settings.DATABASE_URL:
        try:
            import sqlite3, os
            db_file = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
            if db_file.startswith("./"):
                db_file = os.path.join(os.path.dirname(__file__), "..", db_file[2:])
            db_file = os.path.abspath(db_file)
            print(f"[MIGRATION] Connecting to SQLite DB at: {db_file}")

            conn_sync = sqlite3.connect(db_file)
            cur = conn_sync.execute("PRAGMA table_info(knowledge_chunks)")
            existing_cols = {row[1] for row in cur.fetchall()}
            print(f"[MIGRATION] Existing columns: {existing_cols}")

            new_cols = [
                ("section",               "TEXT"),
                ("scheme_name",           "TEXT"),
                ("jurisdiction",          "TEXT"),
                ("state",                 "TEXT"),
                ("category",              "TEXT"),
                ("source_id",             "TEXT"),
                ("source_name",           "TEXT"),
                ("official_info_url",     "TEXT"),
                ("official_app_url",      "TEXT"),
                ("official_scheme_url",   "TEXT"),
                ("official_portal_url",   "TEXT"),
                ("last_verified_at",      "TEXT"),
                ("scheme_version",        "TEXT"),
                ("is_indexed",            "INTEGER NOT NULL DEFAULT 0"),
                ("embedding_vec",         "TEXT"),
                ("metadata_json",         "TEXT"),
            ]
            for col_name, col_type in new_cols:
                if col_name not in existing_cols:
                    try:
                        conn_sync.execute(
                            f"ALTER TABLE knowledge_chunks ADD COLUMN {col_name} {col_type}"
                        )
                        print(f"[MIGRATION] Added knowledge_chunks.{col_name}")
                    except Exception as col_err:
                        print(f"[MIGRATION] Could not add {col_name}: {col_err}")
            conn_sync.commit()
            conn_sync.close()
        except Exception as e:
            print(f"[MIGRATION] General migration exception: {e}")

run_sqlite_schema_migrations()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables for development/testing if using SQLite
    if "sqlite" in settings.DATABASE_URL:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            from sqlalchemy import text
            for col in ["source_name", "official_scheme_url", "official_portal_url"]:
                try:
                    await conn.execute(text(f"ALTER TABLE knowledge_chunks ADD COLUMN {col} TEXT"))
                except Exception:
                    pass
            for col in ["source_url", "source_name", "official_scheme_url", "application_url", "official_portal_url"]:
                try:
                    await conn.execute(text(f"ALTER TABLE schemes ADD COLUMN {col} TEXT"))
                except Exception:
                    pass

        try:
            from scripts.fix_sqlite_schema import migrate
            migrate()
        except Exception as e:
            logger.warning(f"SQLite schema migration skipped: {e}")

        # Seed Schemora Glossary into Knowledge Base
        try:
            from app.core.database import AsyncSessionLocal
            from app.services.glossary_service import ensure_glossary_indexed
            async with AsyncSessionLocal() as session:
                await ensure_glossary_indexed(session)
            logger.info("Schemora Authoritative Glossary seeded into Knowledge Base on startup.")
        except Exception as e:
            logger.warning(f"Glossary seeding on startup skipped: {e}")

    # Check if schemes already exist to prevent slow ingestion lock on every uvicorn reload
    already_seeded = False
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.scheme import Scheme
        from sqlalchemy import select, func
        async with AsyncSessionLocal() as session:
            count_res = await session.execute(select(func.count()).select_from(Scheme))
            scheme_count = count_res.scalar() or 0
            if scheme_count >= 50:
                already_seeded = True
                logger.info(f"Database already seeded with {scheme_count} schemes. Skipping startup re-ingestion.")
    except Exception as e:
        logger.warning(f"Failed to check scheme count: {e}")

    if not already_seeded:
        # Audit and retrofit scheme URLs on startup for PostgreSQL & SQLite
        try:
            from scripts.audit_and_fix_scheme_urls import audit_and_fix_scheme_urls
            await audit_and_fix_scheme_urls()
            logger.info("Scheme URL audit & retrofit completed on startup.")
        except Exception as e:
            logger.warning(f"Scheme URL audit & retrofit on startup skipped: {e}")

        # Ensure full scheme catalog (66+ schemes) is ingested into database on startup
        try:
            from scripts.ingest_full_66_catalog import ingest_all_schemes
            await ingest_all_schemes()
            logger.info("Full scheme catalog ingestion completed on startup.")
        except Exception as e:
            logger.warning(f"Full scheme catalog ingestion on startup skipped: {e}")

    yield




app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        path=request.url.path,
        method=request.method,
    )

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            message="Internal server error",
            errors=[ErrorDetail(code="INTERNAL_ERROR", message=str(exc))],
        ).model_dump(),
    )


# Mount Routers
app.include_router(health_router, prefix=settings.API_V1_STR, tags=["Health"])
app.include_router(profile_router, prefix=f"{settings.API_V1_STR}/profile", tags=["Student Profile"])
app.include_router(schemes_router, prefix=f"{settings.API_V1_STR}/schemes", tags=["Scheme Catalog & Recommendations"])
app.include_router(ai_router, prefix=f"{settings.API_V1_STR}/ai", tags=["AI Grounded Explanations & Scoped Assistant"])
app.include_router(documents_router, prefix=f"{settings.API_V1_STR}/documents", tags=["OCR Document Analysis & Application Checklist"])
app.include_router(saved_schemes_router, prefix=f"{settings.API_V1_STR}/saved-schemes", tags=["Saved Schemes & Status Tracker"])
app.include_router(analytics_router, prefix=f"{settings.API_V1_STR}/analytics", tags=["Privacy-Safe Analytics"])
app.include_router(admin_router, prefix=f"{settings.API_V1_STR}/admin", tags=["Admin Dashboard"])


@app.get("/health")
async def simple_health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health",
        "api_v1_health": f"{settings.API_V1_STR}/health",
        "profile": f"{settings.API_V1_STR}/profile/me",
        "schemes": f"{settings.API_V1_STR}/schemes",
        "ai": f"{settings.API_V1_STR}/ai/chat",
        "documents": f"{settings.API_V1_STR}/documents/my-documents",
        "saved_schemes": f"{settings.API_V1_STR}/saved-schemes",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)


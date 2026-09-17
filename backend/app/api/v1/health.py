import time
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from app.core.database import get_db
from app.core.config import settings
from app.schemas.common import APIResponse

router = APIRouter()


class HealthCheckData(BaseModel):
    status: str
    version: str
    environment: str
    database_connected: bool
    db_backend: str
    db_host: str
    db_error: Optional[str] = None
    total_schemes: int = 0
    total_chunks: int = 0
    indexed_chunks: int = 0
    latency_ms: float


@router.get("/health", summary="Backend Health Check")
async def health_check():
    """Health check endpoint to verify backend service and database connectivity."""
    start_time = time.time()
    db_connected = False
    db_error = None
    total_schemes = 0
    total_chunks = 0
    indexed_chunks = 0

    from app.core.database import AsyncSessionLocal, engine
    dialect_name = getattr(engine.dialect, "name", "unknown")

    import re
    raw_url = str(engine.url)
    safe_url = re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", raw_url)

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            if result.scalar() == 1:
                db_connected = True

            sch_res = await session.execute(text("SELECT COUNT(*) FROM schemes"))
            total_schemes = sch_res.scalar() or 0

            chk_res = await session.execute(text("SELECT COUNT(*) FROM knowledge_chunks"))
            total_chunks = chk_res.scalar() or 0

            if dialect_name == "postgresql":
                try:
                    idx_res = await session.execute(text("SELECT COUNT(*) FROM knowledge_chunks WHERE embedding_vec IS NOT NULL"))
                    indexed_chunks = idx_res.scalar() or 0
                except Exception:
                    pass

    except Exception as exc:
        db_connected = False
        db_error = f"{type(exc).__name__}: {str(exc)}"

    latency = round((time.time() - start_time) * 1000, 2)

    return {
        "success": True,
        "message": "Schemora backend operational",
        "data": {
            "status": "healthy" if db_connected else "degraded",
            "version": settings.VERSION,
            "environment": settings.APP_ENV,
            "database_connected": db_connected,
            "db_backend": dialect_name,
            "db_host": safe_url,
            "db_error": db_error,
            "total_schemes": total_schemes,
            "total_chunks": total_chunks,
            "indexed_chunks": indexed_chunks,
            "latency_ms": latency,
        }
    }

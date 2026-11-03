import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import config
from ai_processor import AIResumeProcessor
from database import DatabaseError, database
import backup
from request_context import RequestIdMiddleware
from routers import api_v1_router, legacy_router
from services.errors import ScanError
from services.jobs import JobRunner
from services.retention import retention_loop
from storage import StorageError, get_storage
from virus_scan import get_virus_scanner

config.configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create shared services on startup and release them on shutdown"""
    config.validate_settings()

    try:
        await database.connect()
        logger.info("Database connected successfully")

        app.state.ai_processor = AIResumeProcessor()
        logger.info("AI processor initialized successfully")

        if await app.state.ai_processor.test_connection():
            logger.info("AI service connection verified")
        else:
            logger.warning("AI service connection test failed")
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise

    app.state.virus_scanner = get_virus_scanner()
    app.state.file_storage = get_storage()
    sweep_task = None
    if app.state.file_storage is not None:
        try:
            await app.state.file_storage.ensure_ready()
            logger.info(f"Original resumes are kept in '{app.state.file_storage.name}' storage")
        except StorageError as e:
            # Scans still work; archiving each upload will log an error until this is fixed
            logger.error(f"File storage is not ready: {e}")
        sweep_task = asyncio.create_task(retention_loop(app.state.file_storage))
    else:
        logger.info("Original resumes are not kept (STORAGE_BACKEND=none)")

    # Background workers pick up queued scans; JOB_WORKERS=0 leaves them to a separate process
    app.state.job_runner = JobRunner(app.state.ai_processor, app.state.file_storage)
    await app.state.job_runner.start()

    backup_task = None
    backup_hours = float(os.getenv("BACKUP_INTERVAL_HOURS", "0"))
    if backup_hours > 0:
        backup_task = asyncio.create_task(backup.backup_loop(lambda: database.db, backup_hours))
        logger.info(f"Backing up the database every {backup_hours:g} hour(s) to {backup.backup_dir()}")

    yield

    if backup_task:
        backup_task.cancel()
        try:
            await backup_task
        except asyncio.CancelledError:
            pass
    await app.state.job_runner.stop()
    if sweep_task:
        sweep_task.cancel()
        try:
            await sweep_task
        except asyncio.CancelledError:
            pass
    await database.close()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI-Powered Resume Scanner API",
        description="Intelligent Resume Screening using AI & NLP. Current version: /api/v1. The unversioned /api paths are deprecated.",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Location", "Idempotent-Replay", "Deprecation"],
    )
    # Added last so it is outermost: every response, errors and CORS replies included, carries an id
    app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(ScanError)
    async def scan_error_handler(request: Request, exc: ScanError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)

    @app.exception_handler(DatabaseError)
    async def database_error_handler(request: Request, exc: DatabaseError):
        return JSONResponse(
            status_code=503,
            content={"detail": "The database is temporarily unavailable. Please try again shortly."},
        )

    app.include_router(api_v1_router)
    app.include_router(legacy_router)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )

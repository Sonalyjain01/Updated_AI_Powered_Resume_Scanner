from fastapi import APIRouter, Request

from database import database
from models import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/")
async def root():
    """Root endpoint for health check"""
    return {"message": "AI-Powered Resume Scanner API is running"}


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Report the state of each dependency; status is 'degraded' when one is down"""
    ai_processor = getattr(request.app.state, "ai_processor", None)
    ai_ok = bool(ai_processor and await ai_processor.test_connection())
    db_ok = await database.ping()
    scanner = request.app.state.virus_scanner
    scanner_ok = await scanner.ping()  # a disabled scanner always reports ok

    healthy = ai_ok and db_ok and scanner_ok
    return HealthResponse(
        status="healthy" if healthy else "degraded",
        message="All services operational" if healthy else "One or more services are unavailable",
        ai_service="Connected" if ai_ok else "Disconnected",
        database="Connected" if db_ok else "Disconnected",
        virus_scanner=("Disabled" if not scanner.enabled else "Connected" if scanner_ok else "Disconnected"),
    )

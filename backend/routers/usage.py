from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_tenant_id
from services.quota import usage_report

router = APIRouter(tags=["Usage"])


class Limits(BaseModel):
    scans: Optional[int]
    tokens: Optional[int]


class UsageResponse(BaseModel):
    period_start: datetime
    scans: int
    fallback_scans: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    average_latency_ms: float
    limits: Limits
    remaining: Limits


@router.get("/usage", response_model=UsageResponse)
async def get_usage(tenant_id: str = Depends(get_tenant_id)):
    """AI usage this month for the caller's tenant, with quota limits and what is left.

    Token counts are estimates (about 4 characters per token) until the AI provider reports exact counts.
    """
    return await usage_report(tenant_id)

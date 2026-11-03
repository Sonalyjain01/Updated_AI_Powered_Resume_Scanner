"""Token, cost and latency accounting for AI calls.

Token counts come from the provider when it reports them (see llm_provider.LLMReply).
Otherwise they are estimated at about 4 characters per token and marked `estimated`.

Prices are US dollars per million tokens. The defaults are the list prices for gpt-4o at the
time of writing; check your provider's current price list and override with:
  LLM_PRICE_INPUT_PER_MTOK, LLM_PRICE_OUTPUT_PER_MTOK
"""
import logging
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_PRICES: Dict[str, Tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
}


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text or "") / 4)


def price_per_mtok(model: str) -> Tuple[float, float]:
    """(input, output) dollars per million tokens for a model; (0, 0) when unknown"""
    env_in, env_out = os.getenv("LLM_PRICE_INPUT_PER_MTOK"), os.getenv("LLM_PRICE_OUTPUT_PER_MTOK")
    if env_in and env_out:
        return float(env_in), float(env_out)
    prices = DEFAULT_PRICES.get(model)
    if prices is None:
        logger.warning(f"No price known for model '{model}'; cost will show as 0. Set LLM_PRICE_INPUT_PER_MTOK and LLM_PRICE_OUTPUT_PER_MTOK.")
        return 0.0, 0.0
    return prices


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = price_per_mtok(model)
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


@dataclass
class UsageTracker:
    """Collects the AI calls made for one scan"""

    model: str = "unknown"
    calls: List[dict] = field(default_factory=list)

    def record(self, purpose: str, prompt: str, system_message: str, reply: Optional[str],
               latency_ms: float, error: Optional[str] = None) -> None:
        reported_in = getattr(reply, "input_tokens", None)
        reported_out = getattr(reply, "output_tokens", None)
        estimated = reported_in is None or reported_out is None
        input_tokens = estimate_tokens(system_message) + estimate_tokens(prompt) if reported_in is None else reported_in
        output_tokens = estimate_tokens(reply or "") if reported_out is None else reported_out
        self.calls.append({
            "purpose": purpose,
            "model": self.model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated": estimated,
            "latency_ms": round(latency_ms, 1),
            "success": error is None,
            "error": error,
            "cost_usd": cost_usd(self.model, input_tokens, output_tokens) if error is None or reply else 0.0,
        })

    @property
    def input_tokens(self) -> int:
        return sum(c["input_tokens"] for c in self.calls)

    @property
    def output_tokens(self) -> int:
        return sum(c["output_tokens"] for c in self.calls)

    @property
    def total_cost_usd(self) -> float:
        return sum(c["cost_usd"] for c in self.calls)

    @property
    def total_latency_ms(self) -> float:
        return sum(c["latency_ms"] for c in self.calls)

    def to_record(self, scan_id: str, tenant_id: str, created_at, used_fallback: bool) -> dict:
        return {
            "scan_id": scan_id,
            "tenant_id": tenant_id,
            "created_at": created_at,
            "model": self.model,
            "call_count": len(self.calls),
            "failed_calls": sum(1 for c in self.calls if not c["success"]),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "cost_usd": round(self.total_cost_usd, 6),
            "latency_ms": round(self.total_latency_ms, 1),
            "estimated": any(c["estimated"] for c in self.calls),
            "used_fallback": used_fallback,
            "calls": self.calls,
        }

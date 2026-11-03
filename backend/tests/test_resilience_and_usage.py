import asyncio

import pytest

import usage as usage_module
from ai_processor import AIResumeProcessor
from llm_provider import LLMProvider, LLMReply
from resilience import CircuitBreaker, CircuitOpenError
from tests.conftest import GOOD_EXTRACTION, GOOD_MATCH, FakeProvider
from usage import UsageTracker, cost_usd, estimate_tokens


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class TestCircuitBreaker:
    def make(self, threshold=3, cooldown=30):
        clock = Clock()
        return CircuitBreaker(failure_threshold=threshold, cooldown_seconds=cooldown, clock=clock), clock

    def test_stays_closed_below_the_threshold(self):
        breaker, _ = self.make()
        for _ in range(2):
            breaker.before_call()
            breaker.record_failure()
        breaker.before_call()  # still allowed
        assert breaker.state == "closed"

    def test_opens_after_consecutive_failures_and_fails_fast(self):
        breaker, _ = self.make()
        for _ in range(3):
            breaker.before_call()
            breaker.record_failure()
        assert breaker.state == "open"
        with pytest.raises(CircuitOpenError):
            breaker.before_call()

    def test_a_success_resets_the_count(self):
        breaker, _ = self.make()
        for _ in range(2):
            breaker.before_call()
            breaker.record_failure()
        breaker.before_call()
        breaker.record_success()
        for _ in range(2):
            breaker.before_call()
            breaker.record_failure()
        assert breaker.state == "closed"

    def test_allows_one_trial_after_the_cooldown(self):
        breaker, clock = self.make()
        for _ in range(3):
            breaker.before_call()
            breaker.record_failure()
        clock.now = 31
        assert breaker.state == "half_open"
        breaker.before_call()  # the trial
        with pytest.raises(CircuitOpenError):
            breaker.before_call()  # others wait for its result

    def test_successful_trial_closes_and_failed_trial_reopens(self):
        breaker, clock = self.make()
        for _ in range(3):
            breaker.before_call()
            breaker.record_failure()
        clock.now = 31
        breaker.before_call()
        breaker.record_failure()
        assert breaker.state == "open"
        clock.now = 62
        breaker.before_call()
        breaker.record_success()
        assert breaker.state == "closed"


class SlowProvider(LLMProvider):
    name = "slow"

    async def complete(self, prompt, system_message, request_id=None):
        await asyncio.sleep(5)
        return "never"


class TestProviderProtection:
    async def test_slow_call_times_out_and_scan_falls_back(self, monkeypatch):
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "0.05")
        p = AIResumeProcessor(provider=SlowProvider())
        data, fallback = await p.extract_resume_data("python " * 40)
        assert fallback is True and "python" in data["skills"]

    async def test_timeout_is_recorded_as_a_failed_call(self, monkeypatch):
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "0.05")
        p = AIResumeProcessor(provider=SlowProvider())
        tracker = p.new_usage_tracker()
        await p.extract_resume_data("python " * 40, usage=tracker)
        assert tracker.calls[0]["success"] is False and tracker.calls[0]["error"] == "timeout"

    async def test_repeated_failures_stop_calls_to_the_provider(self):
        provider = FakeProvider([RuntimeError("down")] * 20)
        p = AIResumeProcessor(provider=provider, breaker=CircuitBreaker(failure_threshold=2, cooldown_seconds=60))
        for _ in range(4):
            await p.extract_resume_data("python " * 40)
        assert len(provider.calls) == 2  # the third and fourth scans never reached the provider

    async def test_open_circuit_still_gives_a_flagged_fallback(self):
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=60)
        p = AIResumeProcessor(provider=FakeProvider([RuntimeError("down")]), breaker=breaker)
        await p.extract_resume_data("python " * 40)
        result = await p.calculate_match_score("r", "python", {"skills": ["python"]})
        assert result.used_fallback is True

    async def test_bad_json_does_not_count_against_the_provider(self):
        provider = FakeProvider(["not json", "still not json"] * 5)
        p = AIResumeProcessor(provider=provider, breaker=CircuitBreaker(failure_threshold=2, cooldown_seconds=60))
        for _ in range(3):
            await p.extract_resume_data("python " * 40)
        assert p.breaker.state == "closed"


class TestUsageTracking:
    def test_estimate_is_about_four_characters_per_token(self):
        assert estimate_tokens("a" * 400) == 100 and estimate_tokens("") == 0

    def test_gpt4o_cost(self):
        assert cost_usd("gpt-4o", 1_000_000, 1_000_000) == pytest.approx(12.50)

    def test_price_can_be_overridden(self, monkeypatch):
        monkeypatch.setenv("LLM_PRICE_INPUT_PER_MTOK", "1")
        monkeypatch.setenv("LLM_PRICE_OUTPUT_PER_MTOK", "2")
        assert cost_usd("anything", 1_000_000, 1_000_000) == pytest.approx(3.0)

    def test_unknown_model_costs_zero_with_a_warning(self, caplog):
        assert cost_usd("mystery-model", 1000, 1000) == 0.0
        assert "No price known" in caplog.text

    def test_estimated_usage_is_marked(self):
        tracker = UsageTracker(model="gpt-4o")
        tracker.record("extract", "p" * 400, "s" * 40, "r" * 80, 12.34)
        call = tracker.calls[0]
        assert call["estimated"] is True and call["input_tokens"] == 110 and call["output_tokens"] == 20

    def test_provider_reported_usage_is_used_as_is(self):
        tracker = UsageTracker(model="gpt-4o")
        tracker.record("extract", "prompt", "system", LLMReply("text", input_tokens=500, output_tokens=40), 5)
        call = tracker.calls[0]
        assert call["estimated"] is False and (call["input_tokens"], call["output_tokens"]) == (500, 40)
        assert call["cost_usd"] == pytest.approx(500 * 2.5 / 1e6 + 40 * 10 / 1e6)

    def test_reply_behaves_like_a_string(self):
        assert LLMReply("hello", 1, 1) == "hello" and LLMReply("a b").split() == ["a", "b"]

    async def test_every_call_including_retries_is_recorded_with_latency(self):
        provider = FakeProvider(["nope", GOOD_EXTRACTION, GOOD_MATCH])
        p = AIResumeProcessor(provider=provider)
        tracker = p.new_usage_tracker()
        data, _ = await p.extract_resume_data("python " * 40, usage=tracker)
        await p.calculate_match_score("r", "jd", data, usage=tracker)
        assert [c["purpose"] for c in tracker.calls] == ["extract", "extract_retry", "match"]
        assert all(c["success"] and c["latency_ms"] >= 0 for c in tracker.calls)
        record = tracker.to_record("scan-1", "tenant-a", "2026-01-01", False)
        assert record["call_count"] == 3 and record["total_tokens"] == record["input_tokens"] + record["output_tokens"]
        assert record["tenant_id"] == "tenant-a" and record["estimated"] is True

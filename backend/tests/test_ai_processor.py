import json

import pytest

from ai_processor import MAX_RESUME_CHARS, AIResumeProcessor
from scoring import ScoringCriteria
from tests.conftest import GOOD_EXTRACTION, GOOD_MATCH, FakeProvider, match_reply

RESUME = "python " * 40


def processor(*replies):
    provider = FakeProvider(list(replies))
    return AIResumeProcessor(provider=provider), provider


class TestExtraction:
    async def test_clean_json(self):
        p, provider = processor(GOOD_EXTRACTION)
        data, fallback = await p.extract_resume_data(RESUME, "r1")
        assert data == {"skills": ["python"], "education": ["BSc"], "experience": ["dev"]}
        assert fallback is False
        assert len(provider.calls) == 1

    async def test_json_inside_code_fence_and_prose(self):
        p, _ = processor("Here you go:\n```json\n" + GOOD_EXTRACTION + "\n```\nHope that helps")
        data, fallback = await p.extract_resume_data(RESUME)
        assert data["skills"] == ["python"] and fallback is False

    async def test_invalid_reply_is_retried_once_with_the_error(self):
        p, provider = processor("not json at all", GOOD_EXTRACTION)
        data, fallback = await p.extract_resume_data(RESUME)
        assert fallback is False and len(provider.calls) == 2
        assert "rejected" in provider.calls[1][0]

    async def test_wrong_shape_is_retried(self):
        p, provider = processor(json.dumps({"skills": "python"}), GOOD_EXTRACTION)
        _, fallback = await p.extract_resume_data(RESUME)
        assert fallback is False and len(provider.calls) == 2

    async def test_two_bad_replies_use_flagged_fallback(self):
        p, provider = processor("nope", "still nope")
        data, fallback = await p.extract_resume_data(RESUME)
        assert fallback is True and len(provider.calls) == 2
        assert "python" in data["skills"]

    async def test_provider_error_uses_flagged_fallback(self):
        p, _ = processor(RuntimeError("provider down"))
        _, fallback = await p.extract_resume_data(RESUME)
        assert fallback is True


class TestMatching:
    async def test_valid_reply_gives_score_and_breakdown(self):
        p, _ = processor(GOOD_MATCH)
        result = await p.calculate_match_score("resume", "jd", {"skills": []})
        assert (result.score, result.summary, result.used_fallback) == (82.0, "ok", False)
        assert [c.name for c in result.breakdown.criteria] == ["skills", "experience", "education"]
        assert result.breakdown.matched_skills == ["python"]
        assert result.breakdown.missing_skills == ["kubernetes"]

    async def test_overall_score_follows_the_weights(self):
        reply = match_reply(skills=100, experience=50, education=0)
        p, _ = processor(reply, reply)
        default = await p.calculate_match_score("r", "jd", {"skills": []})  # 50/30/20
        skills_only = await p.calculate_match_score(
            "r", "jd", {"skills": []}, criteria=ScoringCriteria(skills_weight=100, experience_weight=0, education_weight=0)
        )
        assert default.score == 65.0 and skills_only.score == 100.0

    async def test_model_cannot_set_the_overall_score(self):
        reply = json.dumps({**json.loads(match_reply(skills=10, experience=10, education=10)), "match_score": 99})
        p, _ = processor(reply)
        assert (await p.calculate_match_score("r", "jd", {"skills": []})).score == 10.0

    async def test_user_chosen_skills_are_assessed_in_order(self):
        criteria = ScoringCriteria(required_skills=["Docker", "Python"])
        reply = match_reply(required=[{"skill": "python", "found": True, "evidence": "e"}])
        p, provider = processor(reply)
        result = await p.calculate_match_score("r", "jd", {"skills": []}, criteria=criteria)
        assert [(s.skill, s.found) for s in result.breakdown.skills] == [("Docker", False), ("Python", True)]
        assert "did not report" in result.breakdown.skills[0].evidence
        assert result.breakdown.custom_required_skills is True
        assert '["Docker", "Python"]' in provider.calls[0][0]

    @pytest.mark.parametrize("field", ["skills_score", "experience_score", "education_score"])
    @pytest.mark.parametrize("bad", [150, -5])
    async def test_out_of_range_rating_is_retried_not_clamped(self, field, bad):
        broken = json.loads(match_reply())
        broken[field] = bad
        p, provider = processor(json.dumps(broken), GOOD_MATCH)
        result = await p.calculate_match_score("resume", "jd", {"skills": []})
        assert result.score == 82.0 and result.used_fallback is False and len(provider.calls) == 2

    async def test_missing_rating_is_not_defaulted(self):
        broken = json.loads(match_reply())
        del broken["education_score"]
        p, provider = processor(json.dumps(broken), GOOD_MATCH)
        result = await p.calculate_match_score("resume", "jd", {"skills": []})
        assert result.used_fallback is False and len(provider.calls) == 2

    async def test_fallback_when_ai_is_down(self):
        p, _ = processor(RuntimeError("down"))
        result = await p.calculate_match_score("resume", "python developer", {"skills": ["python", "rust"]})
        assert result.used_fallback is True and result.breakdown is None
        assert result.score == 50  # one of two skills appears in the job description
        assert "1 matching skills out of 2" in result.summary

    async def test_fallback_score_is_capped_at_85(self):
        p, _ = processor(RuntimeError("down"))
        assert (await p.calculate_match_score("r", "python", {"skills": ["python"]})).score == 85

    async def test_long_resume_is_truncated_and_model_is_told(self):
        text = "A" * (MAX_RESUME_CHARS + 500)
        p, provider = processor(GOOD_MATCH)
        await p.calculate_match_score(text, "jd", {"skills": []})
        prompt = provider.calls[0][0]
        assert "Resume truncated" in prompt
        assert "A" * MAX_RESUME_CHARS in prompt and "A" * (MAX_RESUME_CHARS + 1) not in prompt

    async def test_text_beyond_old_2000_char_limit_is_sent(self):
        text = "A" * 5000 + "LATE_MARKER"
        p, provider = processor(GOOD_MATCH)
        await p.calculate_match_score(text, "jd", {"skills": []})
        assert "LATE_MARKER" in provider.calls[0][0]
        assert "Resume truncated" not in provider.calls[0][0]


class TestRequestContext:
    async def test_request_id_is_passed_to_every_call(self):
        p, provider = processor(GOOD_EXTRACTION, GOOD_MATCH)
        await p.extract_resume_data(RESUME, "scan-A")
        await p.calculate_match_score("r", "jd", {"skills": []}, "scan-A")
        assert [rid for _, rid in provider.calls] == ["scan-A", "scan-A"]


class TestConnection:
    async def test_connected(self):
        p, _ = processor("AI Service Connected")
        assert await p.test_connection() is True

    async def test_provider_error_reports_disconnected(self):
        p, _ = processor(RuntimeError("down"))
        assert await p.test_connection() is False

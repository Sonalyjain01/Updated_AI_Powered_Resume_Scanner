import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple, Type, TypeVar
from dotenv import load_dotenv
import logging
from typing import Optional
from pydantic import BaseModel, ValidationError

from llm_provider import LLMProvider, get_llm_provider
from models import AIExtractionOutput, AIMatchOutput
from resilience import CircuitBreaker, breaker_from_env, llm_timeout_seconds
from scoring import (
    CRITERIA, ScoreBreakdown, ScoringCriteria, align_skill_assessments, build_breakdown,
)
from usage import UsageTracker

T = TypeVar("T", bound=BaseModel)

load_dotenv()

logger = logging.getLogger(__name__)

# Roughly 3,000 tokens; covers a long multi-page resume. Longer text is cut and the model is told.
MAX_RESUME_CHARS = 12000

SYSTEM_MESSAGE = "You are an expert AI assistant specialized in resume analysis and job matching. You provide accurate, structured analysis of resumes against job descriptions."

@dataclass
class MatchResult:
    score: float
    summary: str
    breakdown: Optional[ScoreBreakdown]
    used_fallback: bool


class AIResumeProcessor:
    def __init__(self, provider: Optional[LLMProvider] = None, breaker: Optional[CircuitBreaker] = None):
        self.provider = provider or get_llm_provider()
        self.breaker = breaker or breaker_from_env()
        logger.info(f"AI Resume Processor initialized with provider '{self.provider.name}'")

    def new_usage_tracker(self) -> UsageTracker:
        return UsageTracker(model=getattr(self.provider, "model", "unknown"))

    async def _ask(self, prompt: str, request_id: Optional[str] = None,
                   usage: Optional[UsageTracker] = None, purpose: str = "call") -> str:
        """One isolated model call, with a timeout, the circuit breaker, and usage accounting.

        Nothing is remembered between calls.
        """
        self.breaker.before_call()  # raises CircuitOpenError while the provider is paused
        started = time.perf_counter()
        try:
            reply = await asyncio.wait_for(
                self.provider.complete(prompt, SYSTEM_MESSAGE, request_id),
                timeout=llm_timeout_seconds(),
            )
        except Exception as e:
            self.breaker.record_failure()
            error = "timeout" if isinstance(e, asyncio.TimeoutError) else type(e).__name__
            if usage is not None:
                usage.record(purpose, prompt, SYSTEM_MESSAGE, None, (time.perf_counter() - started) * 1000, error=error)
            raise
        self.breaker.record_success()
        if usage is not None:
            usage.record(purpose, prompt, SYSTEM_MESSAGE, reply, (time.perf_counter() - started) * 1000)
        return reply

    @staticmethod
    def _extract_json_text(raw: str) -> str:
        """Pull the JSON object out of a reply that may have code fences or extra prose"""
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("Reply contains no JSON object")
        return text[start:end + 1]

    async def _ask_structured(self, prompt: str, schema: Type[T], request_id: Optional[str] = None,
                              usage: Optional[UsageTracker] = None, purpose: str = "call") -> T:
        """Ask for JSON matching `schema`, validate it, and retry once with the error if it fails"""
        schema_json = json.dumps(schema.model_json_schema())
        full_prompt = f"{prompt}\n\nReturn a single JSON object that validates against this JSON Schema:\n{schema_json}"

        raw = await self._ask(full_prompt, request_id, usage, purpose)
        try:
            return schema.model_validate_json(self._extract_json_text(raw))
        except (ValueError, ValidationError) as first_error:
            logger.warning(f"Structured output invalid, retrying once: {first_error}")
            retry_prompt = (
                f"{full_prompt}\n\nYour previous reply was rejected:\n{raw[:1500]}\n\n"
                f"Problem: {first_error}\n"
                "Reply again with only the corrected JSON object."
            )
            raw = await self._ask(retry_prompt, request_id, usage, f"{purpose}_retry")
            # A second failure raises, and the caller falls back to the keyword method
            return schema.model_validate_json(self._extract_json_text(raw))

    async def extract_resume_data(self, resume_text: str, request_id: Optional[str] = None,
                                  usage: Optional[UsageTracker] = None) -> Tuple[Dict[str, List[str]], bool]:
        """Extract skills, education, and experience from resume text.

        Returns (data, used_fallback). used_fallback is True when the keyword method replaced the AI.
        """
        try:
            extraction_prompt = f"""
            Analyze the following resume text and extract structured information. 
            Return ONLY a valid JSON object with the following format:
            {{
                "skills": ["skill1", "skill2", "skill3"],
                "education": ["degree/institution details"],
                "experience": ["job title - company - duration/description"]
            }}
            
            Guidelines:
            - Extract relevant technical and soft skills
            - Include education degrees, institutions, and years if available
            - Summarize work experience with job titles, companies, and key responsibilities
            - Be concise but comprehensive
            - Return valid JSON only, no additional text
            
            Resume Text:
            {resume_text}
            """
            
            result = await self._ask_structured(extraction_prompt, AIExtractionOutput, request_id, usage, "extract")
            return result.model_dump(), False

        except Exception as e:
            logger.error(f"Error in AI extraction: {str(e)}")
            return self._fallback_extraction(resume_text), True

    def _fallback_extraction(self, resume_text: str) -> Dict[str, List[str]]:
        """Fallback extraction using basic NLP if AI fails"""
        import re
        
        # Basic keyword extraction
        skill_keywords = ['python', 'javascript', 'java', 'react', 'sql', 'aws', 'docker', 
                         'machine learning', 'data analysis', 'project management']
        
        skills = [skill for skill in skill_keywords 
                 if skill.lower() in resume_text.lower()]
        
        # Extract education patterns
        education_patterns = [
            r'(bachelor|master|phd|b\.s\.|m\.s\.|ph\.d\.)[^.]*',
            r'university[^.]*',
            r'college[^.]*'
        ]
        education = []
        for pattern in education_patterns:
            matches = re.findall(pattern, resume_text, re.IGNORECASE)
            education.extend(matches[:2])  # Limit to 2 matches
        
        # Extract experience (basic)
        experience = ["Experience details extracted from resume"]
        if "years" in resume_text.lower():
            exp_match = re.search(r'(\d+)\s+years?', resume_text, re.IGNORECASE)
            if exp_match:
                experience = [f"{exp_match.group(1)} years of experience mentioned"]
        
        return {
            "skills": skills[:10],  # Limit to top 10
            "education": education[:3],  # Limit to 3
            "experience": experience[:5]  # Limit to 5
        }

    async def calculate_match_score(self, resume_text: str, job_description: str,
                                    extracted_data: Dict[str, List[str]],
                                    request_id: Optional[str] = None,
                                    criteria: Optional[ScoringCriteria] = None,
                                    usage: Optional[UsageTracker] = None) -> MatchResult:
        """Score a resume against a job description, with a per-criterion and per-skill breakdown.

        The model rates skills, experience and education from 0 to 100 and reports on each
        required skill. The overall score is computed here from `criteria` weights. When the AI
        cannot answer, a keyword estimate is returned with used_fallback=True and no breakdown.
        """
        criteria = criteria or ScoringCriteria()
        resume_for_prompt = resume_text[:MAX_RESUME_CHARS]
        if len(resume_text) > MAX_RESUME_CHARS:
            resume_for_prompt += f"{chr(10)}[Resume truncated: first {MAX_RESUME_CHARS} of {len(resume_text)} characters shown]"

        if criteria.required_skills:
            skills_instruction = (
                "Assess exactly these required skills, one entry each, using these exact names: "
                + json.dumps(criteria.required_skills)
            )
        else:
            skills_instruction = (
                "Pick up to 8 of the most important skills the job description asks for and assess each one."
            )

        try:
            matching_prompt = f"""
            You are scoring a resume against a job description. Rate three criteria from 0 to 100:
            - skills_score: how well the resume's technical and soft skills cover what the job asks for
            - experience_score: relevance, seniority and industry fit of the work history
            - education_score: how well the education meets the job's requirements (if the job states
              none, rate how relevant the education is to the role)

            Also fill required_skills. {skills_instruction}
            For each skill set found to true only if the resume shows it, and put a short quote or
            fact from the resume in evidence. If it is not shown, set found to false and leave evidence empty.

            analysis_summary: two or three sentences on the main strengths and gaps.
            Do not return an overall score; it is calculated separately.

            Extracted Resume Data:
            Skills: {extracted_data.get('skills', [])}
            Education: {extracted_data.get('education', [])}
            Experience: {extracted_data.get('experience', [])}

            Job Description:
            {job_description}

            Full Resume Text:
            {resume_for_prompt}
            """

            result = await self._ask_structured(matching_prompt, AIMatchOutput, request_id, usage, "match")
            skills = align_skill_assessments(result.required_skills, criteria.required_skills)
            scores = {
                "skills": result.skills_score,
                "experience": result.experience_score,
                "education": result.education_score,
            }
            score, breakdown = build_breakdown(criteria, scores, skills)
            return MatchResult(score, result.analysis_summary, breakdown, False)

        except Exception as e:
            logger.error(f"Error in AI matching: {str(e)}")
            score, summary = self._fallback_matching(extracted_data, job_description)
            return MatchResult(score, summary, None, True)

    def _fallback_matching(self, extracted_data: Dict[str, List[str]], 
                          job_description: str) -> Tuple[float, str]:
        """Fallback matching using basic keyword comparison"""
        skills = extracted_data.get('skills', [])
        jd_lower = job_description.lower()
        
        # Count skill matches
        skill_matches = sum(1 for skill in skills if skill.lower() in jd_lower)
        total_skills = len(skills) if skills else 1
        
        # Basic score calculation
        skill_score = (skill_matches / total_skills) * 100
        base_score = min(skill_score, 85)  # Cap at 85 for fallback
        
        summary = f"Resume analysis completed. Found {skill_matches} matching skills out of {total_skills} identified skills."
        
        return base_score, summary

    async def test_connection(self) -> bool:
        """Test AI service connection"""
        try:
            response = await self._ask("Respond with 'AI Service Connected' and nothing else.", "healthcheck")
            return "connected" in response.lower()
        except Exception as e:
            logger.error(f"AI connection test failed: {str(e)}")
            return False
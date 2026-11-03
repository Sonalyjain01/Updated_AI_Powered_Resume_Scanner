"""Explainable scoring: adjustable weights and a per-criterion, per-skill breakdown.

The model rates each criterion from 0 to 100 and reports whether each required skill was
found. The overall score is then computed here from the caller's weights, so the same ratings
always give the same score and the user can see exactly how it was reached.
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

CRITERIA = ("skills", "experience", "education")
MAX_REQUIRED_SKILLS = 20


class ScoringCriteria(BaseModel):
    """What the user wants the score to emphasise. Weights are relative, not percentages."""

    skills_weight: float = Field(50, ge=0, le=100)
    experience_weight: float = Field(30, ge=0, le=100)
    education_weight: float = Field(20, ge=0, le=100)
    required_skills: List[str] = Field(default_factory=list)

    @field_validator("required_skills")
    @classmethod
    def clean_skills(cls, skills: List[str]) -> List[str]:
        seen, cleaned = set(), []
        for skill in skills:
            skill = " ".join(str(skill).split())
            if not skill or skill.lower() in seen:
                continue
            if len(skill) > 60:
                raise ValueError(f"Required skill is too long: '{skill[:20]}...'")
            seen.add(skill.lower())
            cleaned.append(skill)
        if len(cleaned) > MAX_REQUIRED_SKILLS:
            raise ValueError(f"At most {MAX_REQUIRED_SKILLS} required skills are allowed")
        return cleaned

    @model_validator(mode="after")
    def weights_must_not_all_be_zero(self):
        if self.skills_weight + self.experience_weight + self.education_weight <= 0:
            raise ValueError("At least one scoring weight must be above zero")
        return self

    def weights(self) -> Dict[str, float]:
        """Weights as fractions that sum to 1"""
        raw = {
            "skills": self.skills_weight,
            "experience": self.experience_weight,
            "education": self.education_weight,
        }
        total = sum(raw.values())
        return {name: value / total for name, value in raw.items()}


class SkillAssessment(BaseModel):
    skill: str
    found: bool
    evidence: str = ""


class CriterionScore(BaseModel):
    name: str
    score: float = Field(..., ge=0, le=100, description="How well the resume meets this criterion")
    weight: float = Field(..., ge=0, le=1, description="Share of the overall score, as a fraction")
    contribution: float = Field(..., ge=0, le=100, description="Points this criterion adds to the overall score")


class ScoreBreakdown(BaseModel):
    criteria: List[CriterionScore]
    skills: List[SkillAssessment] = Field(default_factory=list)
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    custom_required_skills: bool = Field(default=False, description="True when the user supplied the skill list")


def build_breakdown(
    criteria: ScoringCriteria,
    scores: Dict[str, float],
    skills: List[SkillAssessment],
) -> "tuple[float, ScoreBreakdown]":
    """Combine the model's ratings with the user's weights; returns (overall score, breakdown)"""
    weights = criteria.weights()
    rows = [
        CriterionScore(
            name=name,
            score=round(scores[name], 1),
            weight=round(weights[name], 4),
            contribution=round(scores[name] * weights[name], 1),
        )
        for name in CRITERIA
    ]
    overall = round(max(0.0, min(100.0, sum(scores[name] * weights[name] for name in CRITERIA))), 1)
    breakdown = ScoreBreakdown(
        criteria=rows,
        skills=skills,
        matched_skills=[s.skill for s in skills if s.found],
        missing_skills=[s.skill for s in skills if not s.found],
        custom_required_skills=bool(criteria.required_skills),
    )
    return overall, breakdown


def align_skill_assessments(
    reported: List[SkillAssessment], requested: List[str]
) -> List[SkillAssessment]:
    """When the user chose the skills, report on exactly those, in their order and wording.

    A skill the model skipped is shown as not found, with a note saying so, rather than dropped.
    """
    if not requested:
        return reported
    by_name = {item.skill.strip().lower(): item for item in reported}
    aligned = []
    for skill in requested:
        item = by_name.get(skill.lower())
        if item is None:
            aligned.append(SkillAssessment(skill=skill, found=False, evidence="The AI did not report on this skill."))
        else:
            aligned.append(SkillAssessment(skill=skill, found=item.found, evidence=item.evidence))
    return aligned


def parse_criteria(raw: Optional[str]) -> ScoringCriteria:
    """Read the `criteria` form field (a JSON object); empty means the defaults"""
    if raw is None or not raw.strip():
        return ScoringCriteria()
    return ScoringCriteria.model_validate_json(raw)

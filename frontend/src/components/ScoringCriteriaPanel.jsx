import React, { useState } from "react";
import { ChevronDown, ChevronUp, SlidersHorizontal } from "lucide-react";

export const DEFAULT_CRITERIA = {
  skillsWeight: 50,
  experienceWeight: 30,
  educationWeight: 20,
  requiredSkillsText: "",
};

const WEIGHTS = [
  { key: "skillsWeight", label: "Skills" },
  { key: "experienceWeight", label: "Experience" },
  { key: "educationWeight", label: "Education" },
];

// Turn the form state into the object the API expects.
export const criteriaToPayload = (criteria) => ({
  skills_weight: Number(criteria.skillsWeight),
  experience_weight: Number(criteria.experienceWeight),
  education_weight: Number(criteria.educationWeight),
  required_skills: criteria.requiredSkillsText
    .split(/[,\n]/)
    .map((skill) => skill.trim())
    .filter(Boolean),
});

export const isDefaultCriteria = (criteria) =>
  WEIGHTS.every(({ key }) => criteria[key] === DEFAULT_CRITERIA[key]) && !criteria.requiredSkillsText.trim();

const ScoringCriteriaPanel = ({ value, onChange, disabled }) => {
  const [open, setOpen] = useState(false);
  const total = WEIGHTS.reduce((sum, { key }) => sum + Number(value[key]), 0);

  return (
    <div className="bg-white rounded-2xl shadow-lg p-8">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="w-full flex items-center justify-between text-left"
      >
        <span className="text-2xl font-bold text-gray-900 flex items-center">
          <SlidersHorizontal size={24} className="mr-3 text-blue-600" />
          Scoring criteria
          {!isDefaultCriteria(value) && (
            <span className="ml-3 text-xs font-medium bg-blue-100 text-blue-700 rounded-full px-2 py-1">Customised</span>
          )}
        </span>
        {open ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
      </button>

      {open && (
        <div className="mt-6 space-y-6">
          <div>
            <p className="text-sm text-gray-600 mb-4">
              Choose how much each area counts toward the score. The weights are relative, so 2, 1 and 1 means skills count for half.
            </p>
            <div className="space-y-4">
              {WEIGHTS.map(({ key, label }) => {
                const share = total > 0 ? Math.round((Number(value[key]) / total) * 100) : 0;
                return (
                  <div key={key} className="grid grid-cols-[6rem_1fr_3rem] items-center gap-4">
                    <label htmlFor={key} className="font-medium text-gray-700">{label}</label>
                    <input
                      id={key}
                      type="range"
                      min="0"
                      max="100"
                      step="5"
                      value={value[key]}
                      disabled={disabled}
                      onChange={(e) => onChange({ ...value, [key]: Number(e.target.value) })}
                      className="w-full"
                    />
                    <span className="text-sm text-gray-600 text-right" aria-label={`${label} share`}>{share}%</span>
                  </div>
                );
              })}
            </div>
            {total === 0 && (
              <p role="alert" className="text-sm text-red-700 mt-3">At least one weight must be above zero.</p>
            )}
          </div>

          <div>
            <label htmlFor="requiredSkills" className="block font-medium text-gray-700 mb-1">Required skills (optional)</label>
            <textarea
              id="requiredSkills"
              rows={2}
              value={value.requiredSkillsText}
              disabled={disabled}
              onChange={(e) => onChange({ ...value, requiredSkillsText: e.target.value })}
              placeholder="Python, FastAPI, Docker"
              className="w-full p-3 border border-gray-300 rounded-xl resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-sm text-gray-500 mt-1">
              Separate with commas or new lines, up to 20. Each one is checked and shown as found or missing. Leave empty to let the AI pick the key skills from the job description.
            </p>
          </div>

          <button
            type="button"
            onClick={() => onChange(DEFAULT_CRITERIA)}
            disabled={disabled || isDefaultCriteria(value)}
            className="text-sm text-blue-700 hover:underline disabled:text-gray-400 disabled:no-underline"
          >
            Reset to defaults
          </button>
        </div>
      )}
    </div>
  );
};

export default ScoringCriteriaPanel;

import React from "react";
import { CheckCircle, XCircle } from "lucide-react";

const LABELS = { skills: "Skills", experience: "Experience", education: "Education" };

const barColor = (score) => {
  if (score >= 80) return "bg-green-500";
  if (score >= 60) return "bg-yellow-500";
  return "bg-red-500";
};

// Shows how the overall score was reached: each area's rating, its weight, and each required skill.
const ScoreBreakdown = ({ breakdown, matchScore }) => {
  if (!breakdown) return null;

  return (
    <div className="bg-white rounded-2xl shadow-lg p-8 mb-8">
      <h3 className="text-2xl font-bold text-gray-900 mb-2">How this score was reached</h3>
      <p className="text-gray-600 mb-6">
        Each area is rated from 0 to 100, then combined using its weight to give {Math.round(matchScore)}%.
      </p>

      <div className="space-y-5 mb-8">
        {breakdown.criteria.map((row) => (
          <div key={row.name}>
            <div className="flex justify-between text-sm mb-1">
              <span className="font-medium text-gray-800">
                {LABELS[row.name] || row.name}
                <span className="text-gray-500 font-normal"> · weight {Math.round(row.weight * 100)}%</span>
              </span>
              <span className="text-gray-700 tabular-nums">
                {Math.round(row.score)}/100 <span className="text-gray-500">(adds {row.contribution.toFixed(1)})</span>
              </span>
            </div>
            <div
              className="h-3 rounded-full bg-gray-100 overflow-hidden"
              role="progressbar"
              aria-valuenow={Math.round(row.score)}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${LABELS[row.name] || row.name} rating`}
            >
              <div className={`h-full ${barColor(row.score)}`} style={{ width: `${row.score}%` }} />
            </div>
          </div>
        ))}
      </div>

      {breakdown.skills.length > 0 && (
        <div>
          <h4 className="font-semibold text-gray-900 mb-1">
            {breakdown.custom_required_skills ? "Your required skills" : "Key skills from the job description"}
          </h4>
          <p className="text-sm text-gray-600 mb-3">
            {breakdown.matched_skills.length} of {breakdown.skills.length} found in the resume.
          </p>
          <ul className="divide-y divide-gray-100">
            {breakdown.skills.map((item) => (
              <li key={item.skill} className="py-3 flex items-start gap-3">
                {item.found ? (
                  <CheckCircle size={20} className="text-green-600 mt-0.5 shrink-0" aria-label="Found" />
                ) : (
                  <XCircle size={20} className="text-red-500 mt-0.5 shrink-0" aria-label="Missing" />
                )}
                <div className="min-w-0">
                  <p className="font-medium text-gray-900">{item.skill}</p>
                  {item.evidence && <p className="text-sm text-gray-600 break-words">{item.evidence}</p>}
                  {!item.found && !item.evidence && <p className="text-sm text-gray-500">Not found in the resume.</p>}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default ScoreBreakdown;

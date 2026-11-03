import { apiClient } from "../lib/apiClient";

export const scansApi = {
  async history({ limit = 10, skip = 0 } = {}) {
    const { data } = await apiClient.get("/scan_history", { params: { limit, skip } });
    return data; // { scans, total_count }
  },

  async get(scanId) {
    const { data } = await apiClient.get(`/scan/${encodeURIComponent(scanId)}`);
    return data;
  },

  async remove(scanId) {
    const { data } = await apiClient.delete(`/scan/${encodeURIComponent(scanId)}`);
    return data;
  },

  // Queue a scan. Returns { job_id, status, status_url } straight away.
  // criteria is optional: { skills_weight, experience_weight, education_weight, required_skills }.
  // The idempotency key makes a retried request return the same job instead of a second scan.
  async enqueue({ resumeFile, jobDescription, criteria, idempotencyKey }) {
    const formData = new FormData();
    formData.append("resume_file", resumeFile);
    formData.append("job_description", jobDescription);
    if (criteria) {
      formData.append("criteria", JSON.stringify(criteria));
    }
    const { data } = await apiClient.post("/scans", formData, {
      headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {},
    });
    return data;
  },

  // Status of a queued scan; `result` is filled in once status is "succeeded".
  async job(jobId) {
    const { data } = await apiClient.get(`/jobs/${encodeURIComponent(jobId)}`);
    return data;
  },
};

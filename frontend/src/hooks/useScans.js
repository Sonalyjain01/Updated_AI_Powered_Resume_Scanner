import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { scansApi } from "../api/scans";
import { ApiError } from "../lib/apiClient";

export const scanKeys = {
  all: ["scans"],
  history: (limit) => ["scans", "history", limit],
  detail: (id) => ["scans", "detail", id],
};

export const useScanHistory = ({ limit = 10 } = {}) =>
  useQuery({
    queryKey: scanKeys.history(limit),
    queryFn: () => scansApi.history({ limit }),
    select: (data) => data.scans || [],
  });

export const useScan = (scanId) =>
  useQuery({
    queryKey: scanKeys.detail(scanId),
    queryFn: () => scansApi.get(scanId),
    enabled: Boolean(scanId),
    // A scan that just finished is seeded into the cache; keep it without refetching.
    staleTime: 5 * 60 * 1000,
    retry: (count, error) => error.status !== 404 && count < 2,
  });

const POLL_START_MS = 1000;
const POLL_MAX_MS = 5000;
const GIVE_UP_AFTER_MS = 10 * 60 * 1000;

const newIdempotencyKey = () =>
  typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Queue a scan, then poll its job until it finishes. `onStatus({ status, queue_position })`
// is called as the job moves along, so the page can say what is happening.
export const runScanJob = async ({ onStatus, ...input }) => {
  const accepted = await scansApi.enqueue({ ...input, idempotencyKey: newIdempotencyKey() });
  const startedAt = Date.now();
  let delay = POLL_START_MS;

  for (;;) {
    const job = await scansApi.job(accepted.job_id);
    onStatus?.(job);
    if (job.status === "succeeded") return job.result;
    if (job.status === "failed") {
      throw new ApiError(job.error?.detail || "The analysis failed.", { status: job.error?.status_code });
    }
    if (Date.now() - startedAt > GIVE_UP_AFTER_MS) {
      throw new ApiError("The analysis is taking longer than expected. Check Scan History in a few minutes.");
    }
    await wait(delay);
    delay = Math.min(delay * 1.5, POLL_MAX_MS);
  }
};

export const useRunScan = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: runScanJob,
    onSuccess: (result) => {
      // Seed the detail cache so the results page works even if the scan was not saved.
      queryClient.setQueryData(scanKeys.detail(result.id), result);
      queryClient.invalidateQueries({ queryKey: ["scans", "history"] });
    },
  });
};

export const useDeleteScan = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: scansApi.remove,
    onSuccess: (_data, scanId) => {
      queryClient.removeQueries({ queryKey: scanKeys.detail(scanId) });
      queryClient.invalidateQueries({ queryKey: ["scans", "history"] });
    },
  });
};

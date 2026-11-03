import axios from "axios";
import { tokenStore, UNAUTHORIZED_EVENT } from "./auth";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

export class ApiError extends Error {
  constructor(message, { status = null, isNetworkError = false, requestId = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.isNetworkError = isNetworkError;
    this.requestId = requestId; // quote this to support: it matches the server's log lines
  }
}

export const apiClient = axios.create({
  baseURL: `${BACKEND_URL}/api/v1`,
  timeout: 150000, // a scan makes up to four AI calls, each allowed 30 seconds by the server
});

// Attach the bearer token when there is one.
apiClient.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

const RETRYABLE_STATUS = new Set([502, 503, 504]);
const MAX_RETRIES = 2;
const BASE_DELAY_MS = 500;

// Only requests that are safe to repeat are retried: reads, deletes, and writes that carry an
// Idempotency-Key (the server returns the original result instead of doing the work twice).
// A plain upload without a key is never replayed, because each attempt costs AI calls.
const isRetryable = (error) => {
  const method = (error.config?.method || "").toLowerCase();
  const hasKey = Boolean(error.config?.headers?.get?.("Idempotency-Key"));
  if (!["get", "head", "delete"].includes(method) && !hasKey) return false;
  if (!error.response) return error.code !== "ERR_CANCELED";
  return RETRYABLE_STATUS.has(error.response.status);
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const toApiError = (error) => {
  if (!error.response) {
    return new ApiError(
      "Could not reach the server. Check your connection and try again.",
      { isNetworkError: true }
    );
  }
  const { status, data, headers } = error.response;
  const requestId = headers?.["x-request-id"] || null;
  const detail = typeof data?.detail === "string" ? data.detail : null;
  let message = detail || `Request failed (${status})`;
  if (status >= 500 && requestId) {
    message += ` (reference ${requestId})`;
  }
  return new ApiError(message, { status, requestId });
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;

    if (config && isRetryable(error)) {
      config.__retryCount = (config.__retryCount || 0) + 1;
      if (config.__retryCount <= MAX_RETRIES) {
        await sleep(BASE_DELAY_MS * 2 ** (config.__retryCount - 1));
        return apiClient(config);
      }
    }

    if (error.response?.status === 401 && tokenStore.get()) {
      tokenStore.clear();
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }

    return Promise.reject(toApiError(error));
  }
);

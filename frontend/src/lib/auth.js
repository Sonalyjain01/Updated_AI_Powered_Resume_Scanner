// Token storage and the auth switch.
//
// Sign-in screens and route protection are off unless REACT_APP_AUTH_ENABLED=true.
// Turn it on together with AUTH_REQUIRED=true on the backend (see backend/.env.example).

const TOKEN_KEY = "resume_scanner_token";

export const AUTH_ENABLED = process.env.REACT_APP_AUTH_ENABLED === "true";

export const tokenStore = {
  get() {
    try {
      return window.localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token) {
    try {
      window.localStorage.setItem(TOKEN_KEY, token);
    } catch {
      // Storage blocked: the session lasts until reload.
    }
  },
  clear() {
    try {
      window.localStorage.removeItem(TOKEN_KEY);
    } catch {
      // Nothing to clear.
    }
  },
};

// Fired by the API client when the server rejects the token.
export const UNAUTHORIZED_EVENT = "resume-scanner:unauthorized";

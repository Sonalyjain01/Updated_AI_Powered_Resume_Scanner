import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { authApi } from "../api/auth";
import { AUTH_ENABLED, tokenStore, UNAUTHORIZED_EVENT } from "../lib/auth";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const queryClient = useQueryClient();
  const [token, setToken] = useState(() => tokenStore.get());

  const startSession = useCallback((accessToken) => {
    queryClient.clear(); // a new session must never show the previous one's data
    tokenStore.set(accessToken);
    setToken(accessToken);
  }, [queryClient]);

  const login = useCallback(async (credentials) => {
    const { access_token: accessToken } = await authApi.login(credentials);
    startSession(accessToken);
  }, [startSession]);

  const register = useCallback(async (details) => {
    const { access_token: accessToken } = await authApi.register(details);
    startSession(accessToken);
  }, [startSession]);

  const logout = useCallback(() => {
    tokenStore.clear();
    setToken(null);
    queryClient.clear(); // never show one user's scans to the next
  }, [queryClient]);

  // The API client clears the token on a 401 and tells us here.
  useEffect(() => {
    const onUnauthorized = () => {
      setToken(null);
      queryClient.clear();
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, [queryClient]);

  const value = useMemo(
    () => ({
      authEnabled: AUTH_ENABLED,
      isAuthenticated: !AUTH_ENABLED || Boolean(token),
      login,
      register,
      logout,
    }),
    [token, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
};

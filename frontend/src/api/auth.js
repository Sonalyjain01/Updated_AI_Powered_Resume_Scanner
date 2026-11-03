import { apiClient } from "../lib/apiClient";

export const authApi = {
  // Both return { access_token, expires_in, user, organization, role }
  async login({ email, password }) {
    const { data } = await apiClient.post("/auth/login", { email, password });
    return data;
  },

  async register({ email, password, name, organizationName }) {
    const { data } = await apiClient.post("/auth/register", {
      email,
      password,
      name,
      organization_name: organizationName || null,
    });
    return data;
  },

  // { user, organization, role, auth_required }
  async me() {
    const { data } = await apiClient.get("/auth/me");
    return data;
  },

  async logoutEverywhere() {
    await apiClient.post("/auth/logout-all");
  },

  // Returns a fresh token; every other session is signed out.
  async changePassword({ currentPassword, newPassword }) {
    const { data } = await apiClient.post("/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return data;
  },

  async exportMyData() {
    const { data } = await apiClient.get("/auth/me/export");
    return data;
  },

  // Permanently deletes the account (and the organisation, if you are its only member).
  async deleteAccount({ password }) {
    const { data } = await apiClient.post("/auth/delete-account", { password });
    return data;
  },
};

export const organizationApi = {
  async current() {
    const { data } = await apiClient.get("/orgs/current");
    return data;
  },

  async exportData() {
    const { data } = await apiClient.get("/orgs/current/export");
    return data;
  },

  // Permanently deletes every scan, stored file and usage record of the organisation.
  async eraseData({ organizationName }) {
    const { data } = await apiClient.post("/orgs/current/erase-data", { organization_name: organizationName });
    return data;
  },

  async usage() {
    const { data } = await apiClient.get("/usage");
    return data;
  },
};

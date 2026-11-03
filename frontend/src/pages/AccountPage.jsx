import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Loader2, ShieldAlert } from "lucide-react";
import { Button } from "../components/ui/button";
import { authApi, organizationApi } from "../api/auth";
import { useAuth } from "../context/AuthContext";

const downloadJson = (filename, data) => {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
};

const input = "w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500";

const Card = ({ title, children }) => (
  <div className="bg-white rounded-2xl shadow-lg p-8">
    <h2 className="text-xl font-bold text-gray-900 mb-4">{title}</h2>
    {children}
  </div>
);

const AccountPage = () => {
  const { logout, authEnabled } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: authApi.me });
  const { data: usage } = useQuery({ queryKey: ["usage"], queryFn: organizationApi.usage });

  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState(null); // { kind: "ok" | "error", text }
  const [eraseName, setEraseName] = useState("");
  const [deletePassword, setDeletePassword] = useState("");

  const run = async (key, action, okText) => {
    setBusy(key);
    setMessage(null);
    try {
      await action();
      if (okText) setMessage({ kind: "ok", text: okText });
    } catch (err) {
      setMessage({ kind: "error", text: err.message });
    } finally {
      setBusy("");
    }
  };

  if (!authEnabled || !me?.user) {
    return (
      <section className="py-16">
        <div className="max-w-3xl mx-auto px-6 text-gray-600">
          {me ? "Accounts are not in use on this server." : <Loader2 className="animate-spin" aria-label="Loading" />}
        </div>
      </section>
    );
  }

  const org = me.organization;
  const isAdmin = me.role === "owner" || me.role === "admin";
  const plan = org.plan;
  const limit = (value) => (value ? value.toLocaleString() : "unlimited");

  return (
    <section className="py-16">
      <div className="max-w-3xl mx-auto px-6 space-y-8">
        {message && (
          <p role={message.kind === "error" ? "alert" : "status"}
             className={`rounded-xl border p-4 ${message.kind === "error" ? "bg-red-50 border-red-200 text-red-800" : "bg-green-50 border-green-200 text-green-800"}`}>
            {message.text}
          </p>
        )}

        <Card title="Your account">
          <dl className="grid grid-cols-[8rem_1fr] gap-y-2 text-gray-700">
            <dt className="text-gray-500">Name</dt><dd>{me.user.name}</dd>
            <dt className="text-gray-500">Email</dt><dd className="break-all">{me.user.email}</dd>
            <dt className="text-gray-500">Organisation</dt><dd>{org.name} <span className="text-gray-500">({me.role})</span></dd>
            <dt className="text-gray-500">Plan</dt><dd>{plan.name}</dd>
          </dl>
          {usage && (
            <p className="mt-4 text-sm text-gray-600">
              This month: {usage.scans} of {limit(plan.scans_per_month)} scans.
              {plan.retention_days > 0 && ` Scans are deleted automatically after ${plan.retention_days} days.`}
            </p>
          )}
          <div className="mt-6 flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => run("signout", async () => { await authApi.logoutEverywhere(); logout(); navigate("/login"); })} disabled={busy !== ""}>
              Sign out of all devices
            </Button>
          </div>
        </Card>

        <Card title="Your data">
          <p className="text-gray-600 mb-4">
            Download a copy of everything stored about you{isAdmin ? ", or about your organisation, including all its scans" : ""} as a JSON file.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" disabled={busy !== ""}
              onClick={() => run("export-me", async () => downloadJson("my-data.json", await authApi.exportMyData()), "Your data was downloaded.")}>
              {busy === "export-me" ? <Loader2 size={16} className="mr-2 animate-spin" /> : <Download size={16} className="mr-2" />}
              Download my data
            </Button>
            {isAdmin && (
              <Button variant="outline" disabled={busy !== ""}
                onClick={() => run("export-org", async () => downloadJson("organization-data.json", await organizationApi.exportData()), "Your organisation's data was downloaded.")}>
                {busy === "export-org" ? <Loader2 size={16} className="mr-2 animate-spin" /> : <Download size={16} className="mr-2" />}
                Download organisation data
              </Button>
            )}
          </div>
        </Card>

        <div className="rounded-2xl border border-red-200 bg-red-50 p-8 space-y-8">
          <h2 className="text-xl font-bold text-red-900 flex items-center"><ShieldAlert size={22} className="mr-2" />Delete data</h2>

          {me.role === "owner" && (
            <form className="space-y-3" onSubmit={(e) => {
              e.preventDefault();
              run("erase", async () => {
                const result = await organizationApi.eraseData({ organizationName: eraseName });
                setEraseName("");
                queryClient.invalidateQueries({ queryKey: ["scans"] });
                queryClient.invalidateQueries({ queryKey: ["usage"] });
                setMessage({ kind: "ok", text: `Deleted ${result.scans} scans and ${result.files} stored files.` });
              });
            }}>
              <h3 className="font-semibold text-red-900">Delete all scans and resume files</h3>
              <p className="text-sm text-red-800">Permanently removes every scan, stored resume file and usage record of {org.name}. Accounts stay. This cannot be undone.</p>
              <label htmlFor="eraseName" className="block text-sm text-red-900">Type <strong>{org.name}</strong> to confirm</label>
              <input id="eraseName" value={eraseName} onChange={(e) => setEraseName(e.target.value)} className={input} autoComplete="off" />
              <Button type="submit" disabled={busy !== "" || eraseName.trim() !== org.name} className="bg-red-700 text-white hover:bg-red-800">
                {busy === "erase" ? <Loader2 size={16} className="mr-2 animate-spin" /> : null}Delete all scans
              </Button>
            </form>
          )}

          <form className="space-y-3" onSubmit={(e) => {
            e.preventDefault();
            run("delete", async () => {
              await authApi.deleteAccount({ password: deletePassword });
              logout();
              navigate("/", { replace: true });
            });
          }}>
            <h3 className="font-semibold text-red-900">Delete my account</h3>
            <p className="text-sm text-red-800">
              Permanently deletes your account. If you are the only member of {org.name}, the organisation and everything in it is deleted too. Deleted data also leaves our backups within 14 days. This cannot be undone.
            </p>
            <label htmlFor="deletePassword" className="block text-sm text-red-900">Your password</label>
            <input id="deletePassword" type="password" value={deletePassword} onChange={(e) => setDeletePassword(e.target.value)} className={input} autoComplete="current-password" />
            <Button type="submit" disabled={busy !== "" || !deletePassword} className="bg-red-700 text-white hover:bg-red-800">
              {busy === "delete" ? <Loader2 size={16} className="mr-2 animate-spin" /> : null}Delete my account
            </Button>
          </form>
        </div>
      </div>
    </section>
  );
};

export default AccountPage;

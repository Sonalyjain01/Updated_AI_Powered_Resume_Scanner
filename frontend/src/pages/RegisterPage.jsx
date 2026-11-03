import React, { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Brain, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { useAuth } from "../context/AuthContext";

const field = "w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500";

const RegisterPage = () => {
  const { authEnabled, isAuthenticated, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", organizationName: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!authEnabled || isAuthenticated) {
    return <Navigate to="/app" replace />;
  }

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await register(form);
      navigate("/app", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-purple-50 px-6 py-12">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-lg p-8">
        <Link to="/" className="flex items-center space-x-3 mb-8">
          <div className="w-10 h-10 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
            <Brain size={24} className="text-white" />
          </div>
          <span className="text-xl font-bold text-gray-900">AI Resume Scanner</span>
        </Link>

        <h1 className="text-2xl font-bold text-gray-900 mb-1">Create your account</h1>
        <p className="text-sm text-gray-600 mb-6">You start on the free plan with your own private workspace.</p>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">Your name</label>
            <input id="name" required autoComplete="name" value={form.name} onChange={set("name")} className={field} />
          </div>
          <div>
            <label htmlFor="organizationName" className="block text-sm font-medium text-gray-700 mb-1">Company or team (optional)</label>
            <input id="organizationName" autoComplete="organization" value={form.organizationName} onChange={set("organizationName")} className={field} />
          </div>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input id="email" type="email" required autoComplete="email" value={form.email} onChange={set("email")} className={field} />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input id="password" type="password" required minLength={10} autoComplete="new-password" value={form.password} onChange={set("password")} className={field} />
            <p className="text-xs text-gray-500 mt-1">At least 10 characters.</p>
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{error}</p>
          )}

          <Button type="submit" disabled={submitting} className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white">
            {submitting ? <Loader2 size={18} className="mr-2 animate-spin" /> : null}
            Create account
          </Button>
        </form>

        <p className="text-sm text-gray-600 mt-6 text-center">
          Already have an account? <Link to="/login" className="text-blue-700 hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
};

export default RegisterPage;

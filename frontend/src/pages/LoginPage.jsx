import React, { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Brain, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { useAuth } from "../context/AuthContext";

const LoginPage = () => {
  const { authEnabled, isAuthenticated, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const destination = location.state?.from || "/app";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!authEnabled || isAuthenticated) {
    return <Navigate to={destination} replace />;
  }

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login({ email, password });
      navigate(destination, { replace: true });
    } catch (err) {
      setError(err.status === 401 ? "Email or password is incorrect." : err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-purple-50 px-6">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-lg p-8">
        <Link to="/" className="flex items-center space-x-3 mb-8">
          <div className="w-10 h-10 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
            <Brain size={24} className="text-white" />
          </div>
          <span className="text-xl font-bold text-gray-900">AI Resume Scanner</span>
        </Link>

        <h1 className="text-2xl font-bold text-gray-900 mb-6">Sign in</h1>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{error}</p>
          )}

          <Button type="submit" disabled={submitting} className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white">
            {submitting ? <Loader2 size={18} className="mr-2 animate-spin" /> : null}
            Sign in
          </Button>
        </form>

        <p className="text-sm text-gray-600 mt-6 text-center">
          New here? <Link to="/register" className="text-blue-700 hover:underline">Create an account</Link>
        </p>
      </div>
    </div>
  );
};

export default LoginPage;

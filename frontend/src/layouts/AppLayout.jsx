import React from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import Header from "../components/Header";
import Hero from "../components/Hero";
import Footer from "../components/Footer";
import { useAuth } from "../context/AuthContext";
import { useScanHistory } from "../hooks/useScans";

const sectionFromPath = (pathname) => {
  if (pathname.startsWith("/app/history")) return "history";
  if (pathname.startsWith("/app/results")) return "results";
  if (pathname.startsWith("/app/account")) return "account";
  return "upload";
};

const SECTION_PATHS = { upload: "/app", history: "/app/history", account: "/app/account" };

// Shell for the signed-in app: header, hero banner, page, footer.
const AppLayout = () => {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { authEnabled, logout } = useAuth();
  const { data: scans } = useScanHistory();

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      <Header
        currentSection={sectionFromPath(pathname)}
        setCurrentSection={(section) => navigate(SECTION_PATHS[section] || "/app")}
        scanCount={scans ? scans.length : 0}
        showAccount={authEnabled}
        onLogout={authEnabled ? () => { logout(); navigate("/", { replace: true }); } : undefined}
      />
      <Hero currentSection={sectionFromPath(pathname)} />
      <Outlet />
      <Footer />
    </div>
  );
};

export default AppLayout;

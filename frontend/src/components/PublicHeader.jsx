import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Brain, Menu, X } from "lucide-react";
import { Button } from "./ui/button";
import { useAuth } from "../context/AuthContext";

const links = [
  { href: "#overview", label: "Overview" },
  { href: "#features", label: "Features" },
  { href: "#tech-stack", label: "Tech Stack" },
  { href: "#demo", label: "Demo" },
  { href: "#contact", label: "Contact" },
];

// Header for the public marketing site. The in-app header lives in Header.jsx.
const PublicHeader = () => {
  const { authEnabled, isAuthenticated } = useAuth();
  const [isScrolled, setIsScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setIsScrolled(window.scrollY > 50);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const ctaLabel = authEnabled && !isAuthenticated ? "Sign in" : "Open app";
  const ctaTarget = authEnabled && !isAuthenticated ? "/login" : "/app";

  return (
    <header className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
      isScrolled ? "bg-white/95 backdrop-blur-md shadow-lg border-b border-gray-200" : "bg-transparent"
    }`}>
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
            <Brain size={24} className="text-white" />
          </div>
          <span className="text-xl font-bold text-gray-900">AI Resume Scanner</span>
        </Link>

        <nav className="hidden md:flex items-center space-x-8">
          {links.map((link) => (
            <a key={link.href} href={link.href} className="text-gray-600 hover:text-gray-900 font-medium">
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden md:block">
          <Button asChild className="bg-gradient-to-r from-blue-600 to-purple-600 text-white">
            <Link to={ctaTarget}>{ctaLabel}</Link>
          </Button>
        </div>

        <button className="md:hidden" aria-label="Toggle menu" onClick={() => setMenuOpen(!menuOpen)}>
          {menuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {menuOpen && (
        <nav className="md:hidden bg-white border-t border-gray-200 px-6 py-4 flex flex-col space-y-3">
          {links.map((link) => (
            <a key={link.href} href={link.href} onClick={() => setMenuOpen(false)} className="text-gray-700 font-medium">
              {link.label}
            </a>
          ))}
          <Button asChild className="bg-gradient-to-r from-blue-600 to-purple-600 text-white">
            <Link to={ctaTarget}>{ctaLabel}</Link>
          </Button>
        </nav>
      )}
    </header>
  );
};

export default PublicHeader;

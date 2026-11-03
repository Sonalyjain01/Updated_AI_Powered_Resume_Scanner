import React, { useState, useEffect } from "react";
import { Button } from "./ui/button";
import { Brain, Upload, FileText, History, Menu, X, LogOut, User } from "lucide-react";

// In-app header. `onLogout` is passed only when sign-in is enabled.
const Header = ({ currentSection, setCurrentSection, scanCount, onLogout, showAccount }) => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const navItems = [
    { id: 'upload', label: 'Upload Resume', icon: Upload },
    { id: 'history', label: `History ${scanCount > 0 ? `(${scanCount})` : ''}`, icon: History },
    ...(showAccount ? [{ id: 'account', label: 'Account', icon: User }] : []),
  ];

  return (
    <header className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
      isScrolled ? 'bg-white/95 backdrop-blur-md shadow-lg border-b border-gray-200' : 'bg-transparent'
    }`}>
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          <div 
            onClick={() => setCurrentSection('upload')}
            className="flex items-center space-x-3 cursor-pointer hover:scale-105 transition-transform duration-200"
          >
            <div className="w-10 h-10 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
              <Brain size={24} className="text-white" />
            </div>
            <div>
              <div className="text-xl font-bold text-gray-900">AI Resume Scanner</div>
              <div className="text-xs text-gray-500">Powered by GPT-4o</div>
            </div>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center space-x-8">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  setCurrentSection(item.id);
                  setIsMobileMenuOpen(false);
                }}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-all duration-200 ${
                  currentSection === item.id
                    ? 'bg-blue-100 text-blue-700 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <item.icon size={18} />
                <span className="font-medium">{item.label}</span>
              </button>
            ))}
          </nav>

          <div className="hidden md:flex items-center space-x-4">
            <div className="flex items-center space-x-2 text-sm text-gray-500">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span>AI Service Active</span>
            </div>
            <Button
              onClick={() => setCurrentSection('upload')}
              className="bg-gradient-to-r from-blue-600 to-purple-600 text-white hover:from-blue-700 hover:to-purple-700 transition-all duration-200 hover:scale-105 shadow-lg"
            >
              <Upload size={18} className="mr-2" />
              New Scan
            </Button>
            {onLogout && (
              <Button onClick={onLogout} variant="outline">
                <LogOut size={18} className="mr-2" />
                Sign out
              </Button>
            )}
          </div>

          {/* Mobile Menu Button */}
          <button
            className="md:hidden"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          >
            {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* Mobile Navigation */}
        {isMobileMenuOpen && (
          <nav className="md:hidden mt-4 pb-4 border-t border-gray-200">
            <div className="flex flex-col space-y-3 pt-4">
              {navItems.map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    setCurrentSection(item.id);
                    setIsMobileMenuOpen(false);
                  }}
                  className={`flex items-center space-x-2 px-4 py-3 rounded-lg transition-all duration-200 ${
                    currentSection === item.id
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  }`}
                >
                  <item.icon size={18} />
                  <span className="font-medium">{item.label}</span>
                </button>
              ))}
              <Button
                onClick={() => {
                  setCurrentSection('upload');
                  setIsMobileMenuOpen(false);
                }}
                className="mt-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white"
              >
                <Upload size={18} className="mr-2" />
                New Scan
              </Button>
            </div>
          </nav>
        )}
      </div>
    </header>
  );
};

export default Header;
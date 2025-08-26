import React from "react";
import { Github, Linkedin, Mail, ArrowUp } from "lucide-react";

const Footer = () => {
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-black text-white py-16">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-12 mb-12">
          {/* Brand */}
          <div>
            <h3 className="text-2xl font-light mb-4">Resume Scanner AI</h3>
            <p className="text-gray-400 mb-6">
              Intelligent Resume Screening using AI & NLP. 
              Transforming the hiring process with 87% accuracy.
            </p>
            <div className="flex space-x-4">
              <a
                href="https://github.com/Sonalyjain01"
                target="_blank"
                rel="noopener noreferrer"
                className="w-10 h-10 bg-gray-800 rounded-lg flex items-center justify-center hover:bg-gray-700 transition-colors duration-200"
              >
                <Github size={20} />
              </a>
              <a
                href="https://www.linkedin.com/in/sonaly-jain-5a6740227/"
                target="_blank"
                rel="noopener noreferrer"
                className="w-10 h-10 bg-gray-800 rounded-lg flex items-center justify-center hover:bg-gray-700 transition-colors duration-200"
              >
                <Linkedin size={20} />
              </a>
              <a
                href="mailto:sonalyjn1912@gmail.com"
                className="w-10 h-10 bg-gray-800 rounded-lg flex items-center justify-center hover:bg-gray-700 transition-colors duration-200"
              >
                <Mail size={20} />
              </a>
            </div>
          </div>

          {/* Project Links */}
          <div>
            <h4 className="text-lg font-medium mb-4">Project</h4>
            <ul className="space-y-3 text-gray-400">
              <li>
                <a href="#overview" className="hover:text-white transition-colors duration-200">
                  Overview
                </a>
              </li>
              <li>
                <a href="#features" className="hover:text-white transition-colors duration-200">
                  Features
                </a>
              </li>
              <li>
                <a href="#tech-stack" className="hover:text-white transition-colors duration-200">
                  Technology Stack
                </a>
              </li>
              <li>
                <a href="#results" className="hover:text-white transition-colors duration-200">
                  Results
                </a>
              </li>
              <li>
                <a href="#demo" className="hover:text-white transition-colors duration-200">
                  Demo
                </a>
              </li>
            </ul>
          </div>

          {/* Tech Stack */}
          <div>
            <h4 className="text-lg font-medium mb-4">Built With</h4>
            <div className="flex flex-wrap gap-2">
              {['Python', 'GPT Models', 'spaCy', 'NLP', 'FastAPI', 'Render'].map((tech, index) => (
                <span
                  key={index}
                  className="px-3 py-1 bg-gray-800 rounded-full text-sm text-gray-300"
                >
                  {tech}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom section */}
        <div className="border-t border-gray-800 pt-8">
          <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
            <div className="text-gray-400 text-sm">
              © {currentYear} Sonaly Jain. Built with passion for AI innovation.
            </div>
            
            <button
              onClick={scrollToTop}
              className="flex items-center space-x-2 text-gray-400 hover:text-white transition-colors duration-200"
            >
              <ArrowUp size={16} />
              <span className="text-sm">Back to top</span>
            </button>
          </div>
        </div>

        {/* Bottom accent */}
        <div className="mt-8 pt-8 text-center">
          <div className="inline-flex items-center space-x-2 text-gray-500 text-sm">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span>System deployed and ready for integration</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
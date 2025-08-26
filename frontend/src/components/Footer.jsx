import React from "react";
import { Brain, Github, Linkedin, Mail, Heart } from "lucide-react";

const Footer = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-gray-900 text-white py-12">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
          {/* Brand */}
          <div>
            <div className="flex items-center space-x-3 mb-4">
              <div className="w-10 h-10 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
                <Brain size={24} className="text-white" />
              </div>
              <div>
                <div className="text-xl font-bold">AI Resume Scanner</div>
                <div className="text-xs text-gray-400">Powered by GPT-4o</div>
              </div>
            </div>
            <p className="text-gray-400 mb-4">
              Intelligent resume screening using cutting-edge AI technology. 
              Get 87% accuracy in matching resumes to job descriptions.
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

          {/* Features */}
          <div>
            <h4 className="text-lg font-semibold mb-4">Features</h4>
            <ul className="space-y-3 text-gray-400">
              <li>AI-Powered Resume Analysis</li>
              <li>Job Description Matching</li>
              <li>Skills & Experience Extraction</li>
              <li>87% Match Accuracy</li>
              <li>PDF & DOCX Support</li>
              <li>Instant Results</li>
            </ul>
          </div>

          {/* Technology */}
          <div>
            <h4 className="text-lg font-semibold mb-4">Built With</h4>
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                {['React', 'FastAPI', 'GPT-4o', 'MongoDB', 'TailwindCSS'].map((tech, index) => (
                  <span
                    key={index}
                    className="px-3 py-1 bg-gray-800 rounded-full text-sm text-gray-300"
                  >
                    {tech}
                  </span>
                ))}
              </div>
              <div className="mt-4">
                <div className="flex items-center space-x-2 text-sm">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-gray-400">AI Service Active</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom section */}
        <div className="border-t border-gray-800 pt-8">
          <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
            <div className="text-gray-400 text-sm">
              © {currentYear} AI Resume Scanner. Built by Sonaly Jain.
            </div>
            
            <div className="flex items-center space-x-2 text-gray-400 text-sm">
              <span>Made with</span>
              <Heart size={16} className="text-red-500" />
              <span>for better hiring</span>
            </div>
          </div>
        </div>

        {/* Project Info */}
        <div className="mt-8 pt-8 border-t border-gray-800 text-center">
          <div className="inline-flex items-center space-x-2 text-gray-500 text-sm">
            <Brain size={16} className="text-blue-400" />
            <span>Powered by OpenAI GPT-4o • Deployed on Render • Open Source</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
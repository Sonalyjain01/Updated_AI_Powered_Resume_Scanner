import React from "react";
import { Brain, Zap, Target, FileText } from "lucide-react";

const Hero = ({ currentSection }) => {
  const getHeroContent = () => {
    switch (currentSection) {
      case 'upload':
        return {
          title: "AI-Powered Resume Scanner",
          subtitle: "Intelligent Resume Screening using AI & NLP",
          description: "Upload your resume and job description to get instant AI-powered matching analysis with 87% accuracy.",
          icon: Brain,
          gradient: "from-blue-600 to-purple-600"
        };
      case 'results':
        return {
          title: "Scan Results",
          subtitle: "AI Analysis Complete",
          description: "Your resume has been analyzed using advanced GPT-4o models and NLP techniques.",
          icon: Target,
          gradient: "from-green-600 to-blue-600"
        };
      case 'history':
        return {
          title: "Scan History",
          subtitle: "Your Previous Analyses",
          description: "View and manage your previous resume scans and match results.",
          icon: FileText,
          gradient: "from-purple-600 to-pink-600"
        };
      default:
        return {
          title: "AI-Powered Resume Scanner",
          subtitle: "Intelligent Resume Screening using AI & NLP",
          description: "Upload your resume and job description to get instant AI-powered matching analysis.",
          icon: Brain,
          gradient: "from-blue-600 to-purple-600"
        };
    }
  };

  const content = getHeroContent();
  const IconComponent = content.icon;

  return (
    <section className="pt-32 pb-16 relative overflow-hidden">
      {/* Background Elements */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-20 left-20 w-32 h-32 bg-blue-200 rounded-full opacity-20 animate-pulse"></div>
        <div className="absolute top-40 right-20 w-24 h-24 bg-purple-200 rounded-full opacity-20 animate-pulse delay-1000"></div>
        <div className="absolute bottom-20 left-1/4 w-16 h-16 bg-green-200 rounded-full opacity-20 animate-pulse delay-2000"></div>
      </div>

      <div className="max-w-7xl mx-auto px-6 text-center">
        <div className="flex justify-center mb-6">
          <div className={`w-20 h-20 bg-gradient-to-r ${content.gradient} rounded-2xl flex items-center justify-center shadow-lg`}>
            <IconComponent size={32} className="text-white" />
          </div>
        </div>

        <h1 className="text-5xl md:text-6xl font-bold text-gray-900 mb-4 leading-tight">
          {content.title}
        </h1>

        <p className="text-xl md:text-2xl text-gray-600 mb-6 font-light">
          {content.subtitle}
        </p>

        <p className="text-lg text-gray-500 max-w-2xl mx-auto mb-8">
          {content.description}
        </p>

        {/* Stats */}
        <div className="flex flex-col sm:flex-row items-center justify-center space-y-4 sm:space-y-0 sm:space-x-12">
          <div className="flex items-center space-x-2">
            <Zap size={20} className="text-green-500" />
            <span className="text-lg font-semibold text-gray-700">87% Accuracy</span>
          </div>
          <div className="flex items-center space-x-2">
            <Brain size={20} className="text-blue-500" />
            <span className="text-lg font-semibold text-gray-700">GPT-4o Powered</span>
          </div>
          <div className="flex items-center space-x-2">
            <Target size={20} className="text-purple-500" />
            <span className="text-lg font-semibold text-gray-700">Instant Results</span>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;
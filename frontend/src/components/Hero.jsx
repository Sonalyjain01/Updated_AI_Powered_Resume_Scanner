import React, { useEffect, useState } from "react";
import { Button } from "./ui/button";
import { ArrowDown, Bot, Brain, Zap } from "lucide-react";

const Hero = () => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    setIsVisible(true);
  }, []);

  const scrollToOverview = () => {
    const element = document.getElementById("overview");
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <section id="hero" className="min-h-screen flex items-center justify-center relative overflow-hidden bg-white">
      {/* Subtle background pattern */}
      <div className="absolute inset-0 opacity-5">
        <div className="absolute top-20 left-20 w-32 h-32 rounded-full border border-gray-300"></div>
        <div className="absolute bottom-40 right-20 w-24 h-24 rounded-full border border-gray-300"></div>
        <div className="absolute top-1/2 left-1/4 w-16 h-16 rounded-full border border-gray-300"></div>
      </div>

      <div className="max-w-7xl mx-auto px-6 text-center relative z-10">
        <div className={`transition-all duration-1000 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          {/* Project badge */}
          <div className="inline-flex items-center space-x-2 bg-gray-50 rounded-full px-4 py-2 mb-8">
            <Brain size={16} className="text-blue-600" />
            <span className="text-sm font-normal text-gray-600">AI-Powered Project</span>
          </div>

          {/* Main headline */}
          <h1 className="text-6xl md:text-8xl font-light leading-tight mb-6 tracking-tight">
            AI-Powered
            <br />
            <span className="text-blue-600">Resume Scanner</span>
            <br />
            System
          </h1>

          {/* Tagline */}
          <p className="text-xl md:text-2xl font-light text-gray-600 mb-12 max-w-3xl mx-auto">
            Intelligent Resume Screening using AI & NLP
          </p>

          {/* Key stats */}
          <div className="flex flex-col md:flex-row items-center justify-center space-y-4 md:space-y-0 md:space-x-12 mb-12">
            <div className="flex items-center space-x-2">
              <Zap size={20} className="text-green-500" />
              <span className="text-lg font-normal">87% Accuracy</span>
            </div>
            <div className="flex items-center space-x-2">
              <Bot size={20} className="text-blue-500" />
              <span className="text-lg font-normal">GPT-Powered</span>
            </div>
            <div className="flex items-center space-x-2">
              <Brain size={20} className="text-purple-500" />
              <span className="text-lg font-normal">NLP Processing</span>
            </div>
          </div>

          {/* CTA buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center space-y-4 sm:space-y-0 sm:space-x-6">
            <Button
              onClick={scrollToOverview}
              size="lg"
              className="bg-black text-white hover:bg-gray-800 transition-all duration-200 hover:scale-105 px-8 py-4 text-lg"
            >
              Explore Project
            </Button>
            <Button
              onClick={() => document.getElementById("demo").scrollIntoView({ behavior: "smooth" })}
              variant="outline"
              size="lg"
              className="border-2 border-gray-300 hover:border-gray-400 transition-all duration-200 hover:scale-105 px-8 py-4 text-lg"
            >
              View Demo
            </Button>
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-1/2 transform -translate-x-1/2 animate-bounce">
          <button
            onClick={scrollToOverview}
            className="flex flex-col items-center space-y-2 text-gray-400 hover:text-gray-600 transition-colors duration-200"
          >
            <ArrowDown size={24} />
            <span className="text-sm">Scroll to explore</span>
          </button>
        </div>
      </div>
    </section>
  );
};

export default Hero;
import React, { useEffect, useRef, useState } from "react";
import { FileSearch, Brain, Target, Code, Cloud, Zap } from "lucide-react";

const Features = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [activeFeature, setActiveFeature] = useState(0);
  const sectionRef = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
        }
      },
      { threshold: 0.2 }
    );

    if (sectionRef.current) {
      observer.observe(sectionRef.current);
    }

    return () => observer.disconnect();
  }, []);

  const features = [
    {
      icon: FileSearch,
      title: "Resume Parsing",
      description: "Advanced NLP techniques extract structured data from unstructured resume formats",
      details: [
        "Extract skills, education, and experience sections",
        "Handle multiple resume formats (PDF, DOCX)",
        "Intelligent section recognition and categorization",
        "Clean and normalize extracted data"
      ]
    },
    {
      icon: Brain,
      title: "Keyword Matching",
      description: "Smart keyword analysis identifies relevant skills and qualifications",
      details: [
        "Context-aware keyword extraction",
        "Synonym and related term recognition",
        "Industry-specific vocabulary handling",
        "Weighted importance scoring"
      ]
    },
    {
      icon: Target,
      title: "Job Description Matching",
      description: "AI-powered matching algorithm compares resumes against job requirements",
      details: [
        "GPT-based semantic understanding",
        "Multi-dimensional similarity scoring",
        "Experience level assessment",
        "Skills gap analysis"
      ]
    },
    {
      icon: Code,
      title: "REST API Integration",
      description: "Clean API endpoints for seamless integration with existing HR systems",
      details: [
        "RESTful API design principles",
        "JSON request/response format",
        "Authentication and rate limiting",
        "Comprehensive documentation"
      ]
    },
    {
      icon: Cloud,
      title: "Cloud Deployment",
      description: "Deployed on Render with scalable infrastructure and reliable uptime",
      details: [
        "Auto-scaling based on demand",
        "99.9% uptime guarantee",
        "Global CDN distribution",
        "Monitoring and logging"
      ]
    },
    {
      icon: Zap,
      title: "Real-time Processing",
      description: "Fast processing pipeline delivers results in seconds, not minutes",
      details: [
        "Optimized processing algorithms",
        "Parallel processing capability",
        "Caching for improved performance",
        "Batch processing support"
      ]
    }
  ];

  return (
    <section id="features" ref={sectionRef} className="py-24 bg-gray-50">
      <div className="max-w-7xl mx-auto px-6">
        <div className={`transition-all duration-1000 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          {/* Section header */}
          <div className="text-center mb-16">
            <h2 className="text-5xl font-light mb-6">Key Features</h2>
            <p className="text-xl font-light text-gray-600 max-w-3xl mx-auto">
              Comprehensive functionality designed to streamline the entire resume screening workflow
            </p>
          </div>

          {/* Features grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-16">
            {features.map((feature, index) => (
              <div
                key={index}
                className={`bg-white rounded-2xl p-8 shadow-sm hover:shadow-lg transition-all duration-300 cursor-pointer hover:-translate-y-1 ${
                  activeFeature === index ? 'ring-2 ring-blue-200 shadow-lg' : ''
                } ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
                style={{ transitionDelay: `${index * 150}ms` }}
                onClick={() => setActiveFeature(index)}
              >
                <div className="w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center mb-6">
                  <feature.icon size={24} className="text-blue-600" />
                </div>
                <h3 className="text-xl font-medium mb-4">{feature.title}</h3>
                <p className="text-gray-600 mb-4">{feature.description}</p>
                
                {activeFeature === index && (
                  <div className="border-t pt-4 mt-4">
                    <ul className="space-y-2">
                      {feature.details.map((detail, detailIndex) => (
                        <li
                          key={detailIndex}
                          className="flex items-start space-x-2 text-sm text-gray-600"
                        >
                          <div className="w-1.5 h-1.5 bg-blue-600 rounded-full mt-2 flex-shrink-0"></div>
                          <span>{detail}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Feature highlight */}
          <div className="bg-white rounded-2xl p-12 shadow-sm text-center">
            <h3 className="text-3xl font-light mb-6">Complete Solution</h3>
            <p className="text-lg text-gray-600 mb-8 max-w-4xl mx-auto">
              From parsing unstructured resumes to delivering ranked candidates, 
              our system provides end-to-end automation for the screening process.
            </p>
            <div className="flex flex-wrap justify-center gap-4">
              {["Python", "spaCy", "GPT Models", "NLP", "REST API", "Cloud"].map((tech, index) => (
                <span
                  key={index}
                  className="px-4 py-2 bg-gray-100 rounded-full text-sm font-medium text-gray-700"
                >
                  {tech}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Features;
import React, { useEffect, useRef, useState } from "react";
import { Play, Code, Eye, Download, ExternalLink } from "lucide-react";
import { Button } from "./ui/button";

const Demo = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [selectedTab, setSelectedTab] = useState('overview');
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

  const demoTabs = [
    { id: 'overview', label: 'System Overview', icon: Eye },
    { id: 'api', label: 'API Demo', icon: Code },
    { id: 'results', label: 'Sample Results', icon: Download }
  ];

  const sampleApiResponse = {
    "job_id": "ai-engineer-2024",
    "processed_resumes": 25,
    "top_candidates": [
      {
        "candidate_id": "resume_001",
        "match_score": 87.5,
        "key_skills": ["Python", "Machine Learning", "NLP", "TensorFlow"],
        "experience_years": 5,
        "education_match": "Strong",
        "summary": "Excellent match with required AI/ML skills and relevant experience"
      },
      {
        "candidate_id": "resume_002", 
        "match_score": 82.3,
        "key_skills": ["Python", "Deep Learning", "Computer Vision", "PyTorch"],
        "experience_years": 4,
        "education_match": "Good",
        "summary": "Strong technical background with complementary skills"
      },
      {
        "candidate_id": "resume_003",
        "match_score": 78.9,
        "key_skills": ["Python", "Data Science", "NLP", "Scikit-learn"],
        "experience_years": 3,
        "education_match": "Good", 
        "summary": "Good foundation with growth potential"
      }
    ],
    "processing_time": "2.3 seconds",
    "accuracy_confidence": "87%"
  };

  const renderTabContent = () => {
    switch (selectedTab) {
      case 'overview':
        return (
          <div className="space-y-6">
            <div className="bg-gray-900 rounded-lg p-6 text-white">
              <h4 className="text-lg font-medium mb-4 flex items-center">
                <Play size={20} className="mr-2 text-green-400" />
                System Workflow Demo
              </h4>
              <div className="space-y-4 text-sm">
                <div className="flex items-center space-x-3">
                  <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                  <span>Resume Upload & Parsing</span>
                  <span className="text-green-400 ml-auto">✓ Complete</span>
                </div>
                <div className="flex items-center space-x-3">
                  <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                  <span>NLP Processing & Feature Extraction</span>
                  <span className="text-green-400 ml-auto">✓ Complete</span>
                </div>
                <div className="flex items-center space-x-3">
                  <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                  <span>Job Description Analysis</span>
                  <span className="text-green-400 ml-auto">✓ Complete</span>
                </div>
                <div className="flex items-center space-x-3">
                  <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse"></div>
                  <span>AI-Powered Matching & Scoring</span>
                  <span className="text-yellow-400 ml-auto">Processing...</span>
                </div>
                <div className="flex items-center space-x-3">
                  <div className="w-2 h-2 bg-gray-500 rounded-full"></div>
                  <span>Candidate Ranking & Report Generation</span>
                  <span className="text-gray-400 ml-auto">Pending</span>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-blue-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-light text-blue-600">25</div>
                <div className="text-sm text-gray-600">Resumes Processed</div>
              </div>
              <div className="bg-green-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-light text-green-600">2.3s</div>
                <div className="text-sm text-gray-600">Processing Time</div>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-light text-purple-600">87%</div>
                <div className="text-sm text-gray-600">Match Accuracy</div>
              </div>
            </div>
          </div>
        );
      case 'api':
        return (
          <div className="space-y-6">
            <div className="bg-gray-900 rounded-lg p-6 text-white overflow-x-auto">
              <h4 className="text-lg font-medium mb-4 flex items-center">
                <Code size={20} className="mr-2 text-blue-400" />
                Sample API Response
              </h4>
              <pre className="text-sm text-green-400">
                {JSON.stringify(sampleApiResponse, null, 2)}
              </pre>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-gray-50 p-4 rounded-lg">
                <h5 className="font-medium mb-2">Endpoint</h5>
                <code className="text-sm bg-gray-800 text-green-400 px-2 py-1 rounded">
                  POST /api/screen-resumes
                </code>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg">
                <h5 className="font-medium mb-2">Response Time</h5>
                <div className="text-lg font-light text-green-600">~2.3 seconds</div>
              </div>
            </div>
          </div>
        );
      case 'results':
        return (
          <div className="space-y-6">
            <div className="space-y-4">
              {sampleApiResponse.top_candidates.map((candidate, index) => (
                <div key={index} className="bg-white border border-gray-200 rounded-lg p-6">
                  <div className="flex justify-between items-start mb-4">
                    <h5 className="font-medium">Candidate #{index + 1}</h5>
                    <div className="text-2xl font-light text-green-600">
                      {candidate.match_score}%
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div>
                      <div className="text-sm text-gray-600 mb-1">Key Skills</div>
                      <div className="flex flex-wrap gap-2">
                        {candidate.key_skills.map((skill, skillIndex) => (
                          <span
                            key={skillIndex}
                            className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-600 mb-1">Experience</div>
                      <div className="text-sm">{candidate.experience_years} years</div>
                      <div className="text-sm text-gray-600 mb-1 mt-2">Education Match</div>
                      <div className="text-sm">{candidate.education_match}</div>
                    </div>
                  </div>
                  <div className="text-sm text-gray-600 mb-1">AI Summary</div>
                  <div className="text-sm">{candidate.summary}</div>
                </div>
              ))}
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <section id="demo" ref={sectionRef} className="py-24 bg-white">
      <div className="max-w-7xl mx-auto px-6">
        <div className={`transition-all duration-1000 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          {/* Section header */}
          <div className="text-center mb-16">
            <h2 className="text-5xl font-light mb-6">Live Demo & Integration</h2>
            <p className="text-xl font-light text-gray-600 max-w-3xl mx-auto">
              Explore the system capabilities and see how it processes resumes 
              in real-time with sample data and API responses
            </p>
          </div>

          {/* Demo tabs */}
          <div className="max-w-5xl mx-auto">
            <div className="flex flex-wrap justify-center mb-8 border border-gray-200 rounded-lg p-1 bg-gray-50">
              {demoTabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setSelectedTab(tab.id)}
                  className={`flex items-center space-x-2 px-6 py-3 rounded-md transition-all duration-200 ${
                    selectedTab === tab.id
                      ? 'bg-white shadow-sm text-black'
                      : 'text-gray-600 hover:text-black'
                  }`}
                >
                  <tab.icon size={18} />
                  <span>{tab.label}</span>
                </button>
              ))}
            </div>

            {/* Demo content */}
            <div className="bg-gray-50 rounded-2xl p-8 min-h-[500px]">
              {renderTabContent()}
            </div>

            {/* Action buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center space-y-4 sm:space-y-0 sm:space-x-6 mt-12">
              <Button
                size="lg"
                className="bg-black text-white hover:bg-gray-800 transition-all duration-200 hover:scale-105 px-8 py-4"
                onClick={() => window.open('https://github.com/Sonalyjain01', '_blank')}
              >
                <ExternalLink size={20} className="mr-2" />
                View Source Code
              </Button>
              <Button
                variant="outline"
                size="lg"
                className="border-2 border-gray-300 hover:border-gray-400 transition-all duration-200 hover:scale-105 px-8 py-4"
                onClick={() => document.getElementById("contact").scrollIntoView({ behavior: "smooth" })}
              >
                Request Integration
              </Button>
            </div>

            {/* Note */}
            <div className="text-center mt-8">
              <p className="text-gray-600">
                This demo showcases the system's capabilities with sample data. 
                The actual system is deployed and ready for integration via REST API.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Demo;
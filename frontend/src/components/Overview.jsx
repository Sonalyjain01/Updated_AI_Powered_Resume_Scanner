import React, { useEffect, useRef, useState } from "react";
import { FileText, Target, Users, Clock } from "lucide-react";

const Overview = () => {
  const [isVisible, setIsVisible] = useState(false);
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

  const problemPoints = [
    {
      icon: Clock,
      title: "Time-Consuming Manual Review",
      description: "HR teams spend hours manually reviewing hundreds of resumes"
    },
    {
      icon: Users,
      title: "Inconsistent Evaluation",
      description: "Human bias and fatigue lead to inconsistent candidate assessment"
    },
    {
      icon: Target,
      title: "Missed Qualified Candidates",
      description: "Important qualifications often overlooked in manual screening"
    },
    {
      icon: FileText,
      title: "Unstructured Data Processing",
      description: "Difficulty extracting and comparing key information across resume formats"
    }
  ];

  return (
    <section id="overview" ref={sectionRef} className="py-24 bg-gray-50">
      <div className="max-w-7xl mx-auto px-6">
        <div className={`transition-all duration-1000 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          {/* Section header */}
          <div className="text-center mb-16">
            <h2 className="text-5xl font-light mb-6">Project Overview</h2>
            <p className="text-xl font-light text-gray-600 max-w-3xl mx-auto">
              A comprehensive solution that revolutionizes the resume screening process 
              through advanced AI and natural language processing techniques.
            </p>
          </div>

          {/* Main description */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center mb-20">
            <div>
              <h3 className="text-3xl font-light mb-6">The Challenge</h3>
              <p className="text-lg text-gray-600 mb-6 leading-relaxed">
                Traditional resume screening is a bottleneck in the hiring process. 
                Recruiters spend countless hours manually reviewing resumes, often 
                missing qualified candidates due to time constraints and human limitations.
              </p>
              <p className="text-lg text-gray-600 leading-relaxed">
                Our AI-powered system addresses these challenges by automating the 
                initial screening process while maintaining accuracy and fairness 
                in candidate evaluation.
              </p>
            </div>

            <div className="space-y-6">
              {problemPoints.map((point, index) => (
                <div 
                  key={index}
                  className={`flex items-start space-x-4 p-4 bg-white rounded-lg shadow-sm hover:shadow-md transition-all duration-300 ${
                    isVisible ? `opacity-100 translate-x-0` : 'opacity-0 translate-x-10'
                  }`}
                  style={{ transitionDelay: `${index * 150}ms` }}
                >
                  <div className="flex-shrink-0 w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center">
                    <point.icon size={24} className="text-blue-600" />
                  </div>
                  <div>
                    <h4 className="text-lg font-medium mb-2">{point.title}</h4>
                    <p className="text-gray-600">{point.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Solution approach */}
          <div className="bg-white rounded-2xl p-12 shadow-sm">
            <h3 className="text-3xl font-light mb-8 text-center">Our Solution</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="text-center">
                <div className="w-16 h-16 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-4">
                  <FileText size={28} className="text-green-600" />
                </div>
                <h4 className="text-xl font-medium mb-3">Smart Parsing</h4>
                <p className="text-gray-600">
                  Extract key sections (skills, education, experience) using advanced NLP techniques
                </p>
              </div>
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Target size={28} className="text-blue-600" />
                </div>
                <h4 className="text-xl font-medium mb-3">Intelligent Matching</h4>
                <p className="text-gray-600">
                  Match resumes to job descriptions with GPT-based models and keyword analysis
                </p>
              </div>
              <div className="text-center">
                <div className="w-16 h-16 bg-purple-50 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Users size={28} className="text-purple-600" />
                </div>
                <h4 className="text-xl font-medium mb-3">Accurate Ranking</h4>
                <p className="text-gray-600">
                  Rank candidates objectively based on job requirements and qualifications
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Overview;
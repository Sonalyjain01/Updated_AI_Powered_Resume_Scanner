import React, { useEffect, useRef, useState } from "react";
import { TrendingUp, Target, Clock, Award, BarChart3, CheckCircle } from "lucide-react";

const Results = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [counters, setCounters] = useState({
    accuracy: 0,
    speed: 0,
    resumes: 0,
    satisfaction: 0
  });
  const sectionRef = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          // Start counter animations
          const targets = { accuracy: 87, speed: 95, resumes: 1000, satisfaction: 98 };
          const duration = 2000;
          const steps = 60;
          const stepDuration = duration / steps;

          Object.keys(targets).forEach(key => {
            let current = 0;
            const increment = targets[key] / steps;
            const timer = setInterval(() => {
              current += increment;
              if (current >= targets[key]) {
                current = targets[key];
                clearInterval(timer);
              }
              setCounters(prev => ({ ...prev, [key]: Math.floor(current) }));
            }, stepDuration);
          });
        }
      },
      { threshold: 0.3 }
    );

    if (sectionRef.current) {
      observer.observe(sectionRef.current);
    }

    return () => observer.disconnect();
  }, []);

  const keyMetrics = [
    {
      icon: Target,
      title: "Matching Accuracy",
      value: counters.accuracy,
      suffix: "%",
      description: "Resume-to-job description matching precision",
      color: "green"
    },
    {
      icon: Clock,
      title: "Speed Improvement",
      value: counters.speed,
      suffix: "%",
      description: "Faster than manual screening process",
      color: "blue"
    },
    {
      icon: BarChart3,
      title: "Resumes Processed",
      value: counters.resumes,
      suffix: "+",
      description: "Successfully analyzed in testing phase",
      color: "purple"
    },
    {
      icon: Award,
      title: "System Reliability",
      value: counters.satisfaction,
      suffix: "%",
      description: "Consistent performance across batches",
      color: "orange"
    }
  ];

  const achievements = [
    {
      icon: CheckCircle,
      title: "High Accuracy Achievement",
      description: "Achieved 87% accuracy in matching resumes to job descriptions through extensive testing and optimization"
    },
    {
      icon: TrendingUp,
      title: "Performance Optimization",
      description: "Optimized processing pipeline to handle multiple resume formats with consistent results"
    },
    {
      icon: Target,
      title: "Successful Deployment",
      description: "Successfully deployed on Render with REST API integration for seamless HR tool compatibility"
    }
  ];

  const getColorClasses = (color) => {
    const colors = {
      green: "bg-green-50 text-green-600 border-green-200",
      blue: "bg-blue-50 text-blue-600 border-blue-200",
      purple: "bg-purple-50 text-purple-600 border-purple-200",
      orange: "bg-orange-50 text-orange-600 border-orange-200"
    };
    return colors[color] || colors.blue;
  };

  return (
    <section id="results" ref={sectionRef} className="py-24 bg-gray-50">
      <div className="max-w-7xl mx-auto px-6">
        <div className={`transition-all duration-1000 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          {/* Section header */}
          <div className="text-center mb-16">
            <h2 className="text-5xl font-light mb-6">Project Results</h2>
            <p className="text-xl font-light text-gray-600 max-w-3xl mx-auto">
              Measurable outcomes demonstrating the effectiveness and impact 
              of our AI-powered resume screening solution
            </p>
          </div>

          {/* Key metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-16">
            {keyMetrics.map((metric, index) => (
              <div
                key={index}
                className={`bg-white rounded-2xl p-8 text-center hover:shadow-lg transition-all duration-300 hover:-translate-y-1 border-2 border-transparent hover:${getColorClasses(metric.color).split(' ')[2]} ${
                  isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
                }`}
                style={{ transitionDelay: `${index * 150}ms` }}
              >
                <div className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6 ${getColorClasses(metric.color).split(' ').slice(0, 2).join(' ')}`}>
                  <metric.icon size={28} />
                </div>
                <div className="text-4xl font-light mb-2">
                  {metric.value}<span className="text-2xl">{metric.suffix}</span>
                </div>
                <h3 className="text-lg font-medium mb-3">{metric.title}</h3>
                <p className="text-gray-600 text-sm">{metric.description}</p>
              </div>
            ))}
          </div>

          {/* Achievements */}
          <div className="bg-white rounded-2xl p-12 shadow-sm mb-16">
            <h3 className="text-3xl font-light mb-8 text-center">Key Achievements</h3>
            <div className="space-y-6">
              {achievements.map((achievement, index) => (
                <div
                  key={index}
                  className={`flex items-start space-x-4 p-6 bg-gray-50 rounded-xl hover:bg-gray-100 transition-all duration-300 ${
                    isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-10'
                  }`}
                  style={{ transitionDelay: `${index * 200 + 500}ms` }}
                >
                  <div className="w-12 h-12 bg-green-50 rounded-lg flex items-center justify-center flex-shrink-0">
                    <achievement.icon size={24} className="text-green-600" />
                  </div>
                  <div>
                    <h4 className="text-xl font-medium mb-2">{achievement.title}</h4>
                    <p className="text-gray-600">{achievement.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Highlight box */}
          <div className="bg-gradient-to-r from-blue-50 to-green-50 rounded-2xl p-12 text-center">
            <div className="text-6xl font-light text-black mb-4">87%</div>
            <h3 className="text-2xl font-light mb-4">Resume-to-Job Description Matching Accuracy</h3>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              This remarkable accuracy rate was achieved through careful optimization 
              of our GPT-based models, advanced NLP techniques, and comprehensive testing 
              across diverse resume formats and job descriptions.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Results;
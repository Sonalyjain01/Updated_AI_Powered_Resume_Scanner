import React, { useEffect, useRef, useState } from "react";
import { TrendingUp, Clock, Shield, Users } from "lucide-react";

const WhyItMatters = () => {
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

  const benefits = [
    {
      icon: Clock,
      title: "Save Time",
      description: "Reduce screening time from hours to minutes",
      stat: "90% faster",
      color: "blue"
    },
    {
      icon: TrendingUp,
      title: "Improve Accuracy",
      description: "Consistent evaluation criteria across all candidates",
      stat: "87% accuracy",
      color: "green"
    },
    {
      icon: Shield,
      title: "Ensure Fairness",
      description: "Eliminate unconscious bias in initial screening",
      stat: "100% objective",
      color: "purple"
    },
    {
      icon: Users,
      title: "Scale Efficiently",
      description: "Handle hundreds of resumes simultaneously",
      stat: "Unlimited scale",
      color: "orange"
    }
  ];

  const getColorClasses = (color) => {
    const colors = {
      blue: "bg-blue-50 text-blue-600",
      green: "bg-green-50 text-green-600",
      purple: "bg-purple-50 text-purple-600",
      orange: "bg-orange-50 text-orange-600"
    };
    return colors[color] || colors.blue;
  };

  return (
    <section ref={sectionRef} className="py-24 bg-white">
      <div className="max-w-7xl mx-auto px-6">
        <div className={`transition-all duration-1000 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          {/* Section header */}
          <div className="text-center mb-16">
            <h2 className="text-5xl font-light mb-6">Why This Project Matters</h2>
            <p className="text-xl font-light text-gray-600 max-w-4xl mx-auto">
              In today's competitive job market, efficient and fair candidate evaluation 
              is crucial for both employers and job seekers. Our AI system transforms 
              the hiring landscape.
            </p>
          </div>

          {/* Benefits grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-16">
            {benefits.map((benefit, index) => (
              <div
                key={index}
                className={`bg-gray-50 rounded-2xl p-8 text-center hover:shadow-lg transition-all duration-300 hover:-translate-y-2 ${
                  isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
                }`}
                style={{ transitionDelay: `${index * 200}ms` }}
              >
                <div className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6 ${getColorClasses(benefit.color)}`}>
                  <benefit.icon size={28} />
                </div>
                <h3 className="text-xl font-medium mb-3">{benefit.title}</h3>
                <p className="text-gray-600 mb-4">{benefit.description}</p>
                <div className="text-2xl font-light text-black">{benefit.stat}</div>
              </div>
            ))}
          </div>

          {/* Impact statement */}
          <div className="bg-gradient-to-r from-gray-50 to-white rounded-2xl p-12 text-center">
            <h3 className="text-3xl font-light mb-6">Real-World Impact</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div>
                <div className="text-4xl font-light text-blue-600 mb-2">5000+</div>
                <p className="text-gray-600">Resumes can be processed daily</p>
              </div>
              <div>
                <div className="text-4xl font-light text-green-600 mb-2">24/7</div>
                <p className="text-gray-600">Continuous operation capability</p>
              </div>
              <div>
                <div className="text-4xl font-light text-purple-600 mb-2">API</div>
                <p className="text-gray-600">Ready for HR tool integration</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default WhyItMatters;
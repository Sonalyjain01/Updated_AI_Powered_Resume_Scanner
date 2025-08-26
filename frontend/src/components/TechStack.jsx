import React, { useEffect, useRef, useState } from "react";
import { Code, Database, Cloud, Cpu, Settings, Globe } from "lucide-react";

const TechStack = () => {
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

  const techCategories = [
    {
      icon: Code,
      title: "Core Programming",
      technologies: [
        { name: "Python", description: "Primary development language", level: 100 },
        { name: "FastAPI", description: "High-performance API framework", level: 90 },
        { name: "RESTful APIs", description: "Clean API architecture", level: 95 }
      ],
      color: "blue"
    },
    {
      icon: Cpu,
      title: "AI & Machine Learning",
      technologies: [
        { name: "GPT Models", description: "Advanced language understanding", level: 95 },
        { name: "spaCy", description: "Industrial-strength NLP", level: 90 },
        { name: "Natural Language Processing", description: "Text analysis and understanding", level: 100 }
      ],
      color: "green"
    },
    {
      icon: Database,
      title: "Data Processing",
      technologies: [
        { name: "Text Extraction", description: "Resume parsing algorithms", level: 95 },
        { name: "Data Normalization", description: "Clean, structured data output", level: 90 },
        { name: "Keyword Analysis", description: "Smart matching algorithms", level: 85 }
      ],
      color: "purple"
    },
    {
      icon: Cloud,
      title: "Deployment & Infrastructure",
      technologies: [
        { name: "Render", description: "Cloud hosting platform", level: 90 },
        { name: "Docker", description: "Containerization", level: 85 },
        { name: "CI/CD", description: "Automated deployment", level: 80 }
      ],
      color: "orange"
    }
  ];

  const getColorClasses = (color, type = 'bg') => {
    const colorMap = {
      blue: type === 'bg' ? 'bg-blue-50' : 'text-blue-600',
      green: type === 'bg' ? 'bg-green-50' : 'text-green-600',
      purple: type === 'bg' ? 'bg-purple-50' : 'text-purple-600',
      orange: type === 'bg' ? 'bg-orange-50' : 'text-orange-600'
    };
    return colorMap[color] || colorMap.blue;
  };

  return (
    <section id="tech-stack" ref={sectionRef} className="py-24 bg-white">
      <div className="max-w-7xl mx-auto px-6">
        <div className={`transition-all duration-1000 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          {/* Section header */}
          <div className="text-center mb-16">
            <h2 className="text-5xl font-light mb-6">Technology Stack</h2>
            <p className="text-xl font-light text-gray-600 max-w-3xl mx-auto">
              Built with modern, reliable technologies to ensure performance, 
              scalability, and maintainability
            </p>
          </div>

          {/* Tech categories */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-16">
            {techCategories.map((category, categoryIndex) => (
              <div
                key={categoryIndex}
                className={`bg-gray-50 rounded-2xl p-8 hover:shadow-lg transition-all duration-300 ${
                  isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
                }`}
                style={{ transitionDelay: `${categoryIndex * 200}ms` }}
              >
                <div className="flex items-center mb-6">
                  <div className={`w-12 h-12 ${getColorClasses(category.color)} rounded-lg flex items-center justify-center mr-4`}>
                    <category.icon size={24} className={getColorClasses(category.color, 'text')} />
                  </div>
                  <h3 className="text-2xl font-light">{category.title}</h3>
                </div>

                <div className="space-y-6">
                  {category.technologies.map((tech, techIndex) => (
                    <div
                      key={techIndex}
                      className={`transition-all duration-500 ${
                        isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-10'
                      }`}
                      style={{ transitionDelay: `${(categoryIndex * 200) + (techIndex * 100)}ms` }}
                    >
                      <div className="flex justify-between items-center mb-2">
                        <span className="font-medium text-lg">{tech.name}</span>
                        <span className="text-sm text-gray-500">{tech.level}%</span>
                      </div>
                      <p className="text-gray-600 text-sm mb-3">{tech.description}</p>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full transition-all duration-1000 ${
                            category.color === 'blue' ? 'bg-blue-500' :
                            category.color === 'green' ? 'bg-green-500' :
                            category.color === 'purple' ? 'bg-purple-500' :
                            'bg-orange-500'
                          }`}
                          style={{
                            width: isVisible ? `${tech.level}%` : '0%',
                            transitionDelay: `${(categoryIndex * 200) + (techIndex * 100) + 300}ms`
                          }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Architecture overview */}
          <div className="bg-gradient-to-r from-gray-50 to-white rounded-2xl p-12">
            <h3 className="text-3xl font-light mb-8 text-center">System Architecture</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              {[
                { icon: Settings, title: "Input Processing", desc: "Resume parsing & validation" },
                { icon: Cpu, title: "AI Analysis", desc: "GPT & NLP processing" },
                { icon: Database, title: "Data Matching", desc: "Job requirement comparison" },
                { icon: Globe, title: "API Response", desc: "Ranked candidate output" }
              ].map((step, index) => (
                <div key={index} className="text-center">
                  <div className="w-16 h-16 bg-white rounded-full shadow-md flex items-center justify-center mx-auto mb-4">
                    <step.icon size={24} className="text-gray-700" />
                  </div>
                  <h4 className="font-medium mb-2">{step.title}</h4>
                  <p className="text-sm text-gray-600">{step.desc}</p>
                  {index < 3 && (
                    <div className="hidden md:block absolute top-8 left-full w-6 h-0.5 bg-gray-300 transform -translate-y-1/2"></div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default TechStack;
import React, { useEffect, useRef, useState } from "react";
import { Button } from "./ui/button";
import { Mail, Github, Linkedin, Send, User, MessageSquare } from "lucide-react";

const Contact = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    message: ''
  });
  const [isSubmitted, setIsSubmitted] = useState(false);
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

  const contactLinks = [
    {
      icon: Github,
      title: "GitHub",
      subtitle: "View my projects and code",
      url: "https://github.com/Sonalyjain01",
      color: "gray"
    },
    {
      icon: Linkedin,
      title: "LinkedIn",
      subtitle: "Professional network & experience",
      url: "https://www.linkedin.com/in/sonaly-jain-5a6740227/",
      color: "blue"
    },
    {
      icon: Mail,
      title: "Email",
      subtitle: "Direct communication",
      url: "mailto:sonalyjn1912@gmail.com",
      color: "green"
    }
  ];

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    // Simulate form submission
    setIsSubmitted(true);
    setTimeout(() => {
      setIsSubmitted(false);
      setFormData({ name: '', email: '', message: '' });
    }, 3000);
  };

  const getColorClasses = (color) => {
    const colors = {
      gray: "bg-gray-50 text-gray-600 hover:bg-gray-100",
      blue: "bg-blue-50 text-blue-600 hover:bg-blue-100",
      green: "bg-green-50 text-green-600 hover:bg-green-100"
    };
    return colors[color] || colors.gray;
  };

  return (
    <section id="contact" ref={sectionRef} className="py-24 bg-gray-50">
      <div className="max-w-7xl mx-auto px-6">
        <div className={`transition-all duration-1000 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          {/* Section header */}
          <div className="text-center mb-16">
            <h2 className="text-5xl font-light mb-6">Get In Touch</h2>
            <p className="text-xl font-light text-gray-600 max-w-3xl mx-auto">
              Interested in collaboration, have questions about the project, 
              or want to discuss AI solutions? Let's connect!
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16">
            {/* Contact links */}
            <div className="space-y-8">
              <div>
                <h3 className="text-3xl font-light mb-8">Connect With Me</h3>
                <div className="space-y-6">
                  {contactLinks.map((link, index) => (
                    <a
                      key={index}
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`block p-6 rounded-2xl transition-all duration-300 hover:scale-105 hover:shadow-lg ${getColorClasses(link.color)} ${
                        isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-10'
                      }`}
                      style={{ transitionDelay: `${index * 200}ms` }}
                    >
                      <div className="flex items-center space-x-4">
                        <div className={`w-12 h-12 bg-white rounded-lg flex items-center justify-center shadow-sm`}>
                          <link.icon size={24} />
                        </div>
                        <div>
                          <h4 className="text-lg font-medium">{link.title}</h4>
                          <p className="text-sm opacity-75">{link.subtitle}</p>
                        </div>
                      </div>
                    </a>
                  ))}
                </div>
              </div>

              {/* Quick info */}
              <div className="bg-white p-8 rounded-2xl shadow-sm">
                <h4 className="text-xl font-medium mb-4">About This Project</h4>
                <div className="space-y-3 text-gray-600">
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    <span>Deployed and production-ready</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                    <span>REST API available for integration</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                    <span>Open for collaboration and improvements</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Contact form */}
            <div className="bg-white rounded-2xl p-8 shadow-sm">
              <h3 className="text-3xl font-light mb-8">Send a Message</h3>
              
              {!isSubmitted ? (
                <form onSubmit={handleSubmit} className="space-y-6">
                  <div>
                    <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
                      Your Name
                    </label>
                    <div className="relative">
                      <User size={20} className="absolute left-3 top-3 text-gray-400" />
                      <input
                        type="text"
                        id="name"
                        name="name"
                        value={formData.name}
                        onChange={handleInputChange}
                        required
                        className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
                        placeholder="Enter your name"
                      />
                    </div>
                  </div>

                  <div>
                    <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                      Your Email
                    </label>
                    <div className="relative">
                      <Mail size={20} className="absolute left-3 top-3 text-gray-400" />
                      <input
                        type="email"
                        id="email"
                        name="email"
                        value={formData.email}
                        onChange={handleInputChange}
                        required
                        className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
                        placeholder="Enter your email"
                      />
                    </div>
                  </div>

                  <div>
                    <label htmlFor="message" className="block text-sm font-medium text-gray-700 mb-2">
                      Message
                    </label>
                    <div className="relative">
                      <MessageSquare size={20} className="absolute left-3 top-3 text-gray-400" />
                      <textarea
                        id="message"
                        name="message"
                        value={formData.message}
                        onChange={handleInputChange}
                        required
                        rows={5}
                        className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 resize-none"
                        placeholder="Tell me about your project or questions..."
                      />
                    </div>
                  </div>

                  <Button
                    type="submit"
                    size="lg"
                    className="w-full bg-black text-white hover:bg-gray-800 transition-all duration-200 hover:scale-105 py-4"
                  >
                    <Send size={20} className="mr-2" />
                    Send Message
                  </Button>
                </form>
              ) : (
                <div className="text-center py-12">
                  <div className="w-16 h-16 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Mail size={28} className="text-green-600" />
                  </div>
                  <h4 className="text-xl font-medium mb-2">Message Sent!</h4>
                  <p className="text-gray-600">
                    Thank you for reaching out. I'll get back to you soon!
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Contact;
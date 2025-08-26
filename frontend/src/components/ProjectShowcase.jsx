import React, { useState, useEffect } from "react";
import Header from "./Header";
import Hero from "./Hero";
import Overview from "./Overview";
import WhyItMatters from "./WhyItMatters";
import Features from "./Features";
import TechStack from "./TechStack";
import Results from "./Results";
import Demo from "./Demo";
import Contact from "./Contact";
import Footer from "./Footer";

const ProjectShowcase = () => {
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    setIsLoaded(true);
  }, []);

  return (
    <div className={`min-h-screen bg-white transition-opacity duration-1000 ${isLoaded ? 'opacity-100' : 'opacity-0'}`}>
      <Header />
      <Hero />
      <Overview />
      <WhyItMatters />
      <Features />
      <TechStack />
      <Results />
      <Demo />
      <Contact />
      <Footer />
    </div>
  );
};

export default ProjectShowcase;
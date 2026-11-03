import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import PublicHeader from "./PublicHeader";
import Hero from "./Hero";
import Overview from "./Overview";
import Features from "./Features";
import TechStack from "./TechStack";
import Results from "./Results";
import Demo from "./Demo";
import Contact from "./Contact";
import Footer from "./Footer";
import { Button } from "./ui/button";

// Public marketing site, served at "/". The scanner itself lives under "/app".
const ProjectShowcase = () => {
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    setIsLoaded(true);
  }, []);

  return (
    <div className={`min-h-screen bg-white transition-opacity duration-1000 ${isLoaded ? 'opacity-100' : 'opacity-0'}`}>
      <PublicHeader />
      <Hero />
      <div className="flex justify-center -mt-4 pb-12">
        <Button asChild size="lg" className="bg-gradient-to-r from-blue-600 to-purple-600 text-white">
          <Link to="/app">Try the scanner</Link>
        </Button>
      </div>
      <Overview />
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

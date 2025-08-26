import React, { useState, useEffect } from "react";
import Header from "./Header";
import Hero from "./Hero";
import UploadSection from "./UploadSection";
import ResultsSection from "./ResultsSection";
import HistorySection from "./HistorySection";
import Footer from "./Footer";

const ResumeScanner = () => {
  const [currentSection, setCurrentSection] = useState('upload');
  const [scanResult, setScanResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [scanHistory, setScanHistory] = useState([]);

  const handleScanComplete = (result) => {
    setScanResult(result);
    setCurrentSection('results');
    // Refresh history
    fetchScanHistory();
  };

  const handleNewScan = () => {
    setScanResult(null);
    setCurrentSection('upload');
  };

  const fetchScanHistory = async () => {
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${BACKEND_URL}/api/scan_history?limit=10`);
      if (response.ok) {
        const data = await response.json();
        setScanHistory(data.scans || []);
      }
    } catch (error) {
      console.error('Error fetching scan history:', error);
    }
  };

  useEffect(() => {
    fetchScanHistory();
  }, []);

  const renderMainContent = () => {
    switch (currentSection) {
      case 'upload':
        return (
          <UploadSection 
            onScanComplete={handleScanComplete}
            isLoading={isLoading}
            setIsLoading={setIsLoading}
          />
        );
      case 'results':
        return (
          <ResultsSection 
            scanResult={scanResult}
            onNewScan={handleNewScan}
          />
        );
      case 'history':
        return (
          <HistorySection 
            scanHistory={scanHistory}
            onRefresh={fetchScanHistory}
            onSelectScan={(scan) => {
              setScanResult(scan);
              setCurrentSection('results');
            }}
          />
        );
      default:
        return <UploadSection onScanComplete={handleScanComplete} />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      <Header 
        currentSection={currentSection}
        setCurrentSection={setCurrentSection}
        scanCount={scanHistory.length}
      />
      <Hero currentSection={currentSection} />
      {renderMainContent()}
      <Footer />
    </div>
  );
};

export default ResumeScanner;
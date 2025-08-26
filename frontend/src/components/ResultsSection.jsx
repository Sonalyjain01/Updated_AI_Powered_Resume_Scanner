import React from "react";
import { Button } from "./ui/button";
import { 
  Target, 
  Brain, 
  FileText, 
  GraduationCap, 
  Briefcase, 
  Zap,
  Download,
  Share2,
  ArrowLeft
} from "lucide-react";

const ResultsSection = ({ scanResult, onNewScan }) => {
  if (!scanResult) {
    return (
      <div className="py-16 text-center">
        <p className="text-gray-500">No scan results available.</p>
      </div>
    );
  }

  const getScoreColor = (score) => {
    if (score >= 80) return "text-green-600 bg-green-100";
    if (score >= 60) return "text-yellow-600 bg-yellow-100";
    return "text-red-600 bg-red-100";
  };

  const getScoreGradient = (score) => {
    if (score >= 80) return "from-green-500 to-emerald-500";
    if (score >= 60) return "from-yellow-500 to-orange-500";
    return "from-red-500 to-pink-500";
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <section className="py-16">
      <div className="max-w-6xl mx-auto px-6">
        {/* Header */}
        <div className="text-center mb-12">
          <Button
            onClick={onNewScan}
            variant="outline"
            className="mb-6 hover:bg-blue-50"
          >
            <ArrowLeft size={18} className="mr-2" />
            New Scan
          </Button>
          
          <h2 className="text-3xl font-bold text-gray-900 mb-4">Resume Analysis Results</h2>
          <p className="text-gray-600">Analysis completed on {formatDate(scanResult.created_at)}</p>
        </div>

        {/* Match Score Card */}
        <div className="bg-white rounded-2xl shadow-lg p-8 mb-8">
          <div className="text-center">
            <div className={`inline-flex items-center justify-center w-32 h-32 rounded-full bg-gradient-to-r ${getScoreGradient(scanResult.match_score)} mb-6`}>
              <span className="text-4xl font-bold text-white">
                {Math.round(scanResult.match_score)}%
              </span>
            </div>
            
            <h3 className="text-2xl font-bold text-gray-900 mb-4">Match Score</h3>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              {scanResult.analysis_summary}
            </p>
            
            <div className="flex justify-center space-x-4 mt-6">
              <Button variant="outline" className="hover:bg-gray-50">
                <Download size={18} className="mr-2" />
                Export Report
              </Button>
              <Button variant="outline" className="hover:bg-gray-50">
                <Share2 size={18} className="mr-2" />
                Share Results
              </Button>
            </div>
          </div>
        </div>

        {/* Detailed Analysis */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
          {/* Skills */}
          <div className="bg-white rounded-2xl shadow-lg p-6">
            <div className="flex items-center mb-6">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mr-4">
                <Zap size={24} className="text-blue-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900">Skills Identified</h3>
            </div>
            
            <div className="space-y-3">
              {scanResult.extracted_data.skills.length > 0 ? (
                scanResult.extracted_data.skills.map((skill, index) => (
                  <div
                    key={index}
                    className="bg-blue-50 px-3 py-2 rounded-lg text-blue-800 font-medium"
                  >
                    {skill}
                  </div>
                ))
              ) : (
                <p className="text-gray-500 italic">No specific skills identified</p>
              )}
            </div>
          </div>

          {/* Education */}
          <div className="bg-white rounded-2xl shadow-lg p-6">
            <div className="flex items-center mb-6">
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mr-4">
                <GraduationCap size={24} className="text-green-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900">Education</h3>
            </div>
            
            <div className="space-y-3">
              {scanResult.extracted_data.education.length > 0 ? (
                scanResult.extracted_data.education.map((edu, index) => (
                  <div
                    key={index}
                    className="bg-green-50 px-3 py-2 rounded-lg text-green-800"
                  >
                    {edu}
                  </div>
                ))
              ) : (
                <p className="text-gray-500 italic">No education details identified</p>
              )}
            </div>
          </div>

          {/* Experience */}
          <div className="bg-white rounded-2xl shadow-lg p-6">
            <div className="flex items-center mb-6">
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mr-4">
                <Briefcase size={24} className="text-purple-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900">Experience</h3>
            </div>
            
            <div className="space-y-3">
              {scanResult.extracted_data.experience.length > 0 ? (
                scanResult.extracted_data.experience.map((exp, index) => (
                  <div
                    key={index}
                    className="bg-purple-50 px-3 py-2 rounded-lg text-purple-800"
                  >
                    {exp}
                  </div>
                ))
              ) : (
                <p className="text-gray-500 italic">No experience details identified</p>
              )}
            </div>
          </div>
        </div>

        {/* File Info and Job Description */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* File Information */}
          <div className="bg-white rounded-2xl shadow-lg p-6">
            <div className="flex items-center mb-6">
              <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center mr-4">
                <FileText size={24} className="text-gray-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900">Resume File</h3>
            </div>
            
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">Filename:</span>
                <span className="font-medium">{scanResult.filename}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Scan ID:</span>
                <span className="font-mono text-sm">{scanResult.id.slice(0, 8)}...</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">AI Model:</span>
                <span className="font-medium">GPT-4o</span>
              </div>
            </div>
          </div>

          {/* Job Description Preview */}
          <div className="bg-white rounded-2xl shadow-lg p-6">
            <div className="flex items-center mb-6">
              <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center mr-4">
                <Target size={24} className="text-orange-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900">Job Description</h3>
            </div>
            
            <div className="bg-gray-50 rounded-lg p-4 max-h-40 overflow-y-auto">
              <p className="text-gray-700 text-sm leading-relaxed">
                {scanResult.job_description.length > 300
                  ? `${scanResult.job_description.substring(0, 300)}...`
                  : scanResult.job_description
                }
              </p>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="text-center mt-12">
          <div className="space-x-4">
            <Button
              onClick={onNewScan}
              className="bg-gradient-to-r from-blue-600 to-purple-600 text-white px-8 py-3 hover:from-blue-700 hover:to-purple-700 transition-all duration-200 hover:scale-105 shadow-lg"
            >
              <FileText size={18} className="mr-2" />
              Scan Another Resume
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default ResultsSection;
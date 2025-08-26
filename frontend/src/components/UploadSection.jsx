import React, { useState, useRef } from "react";
import { Button } from "./ui/button";
import { Upload, FileText, Loader2, AlertCircle, CheckCircle } from "lucide-react";

const UploadSection = ({ onScanComplete, isLoading, setIsLoading }) => {
  const [resumeFile, setResumeFile] = useState(null);
  const [jobDescription, setJobDescription] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (file) => {
    setError("");
    
    // Validate file type
    const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    if (!allowedTypes.includes(file.type)) {
      setError("Please upload a PDF or DOCX file only.");
      return;
    }

    // Validate file size (10MB max)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      setError("File size must be less than 10MB.");
      return;
    }

    setResumeFile(file);
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!resumeFile) {
      setError("Please upload a resume file.");
      return;
    }

    if (!jobDescription.trim()) {
      setError("Please enter a job description.");
      return;
    }

    if (jobDescription.trim().length < 50) {
      setError("Job description must be at least 50 characters long.");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const formData = new FormData();
      formData.append('resume_file', resumeFile);
      formData.append('job_description', jobDescription);

      const response = await fetch(`${BACKEND_URL}/api/scan_resume`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Scan failed');
      }

      const result = await response.json();
      onScanComplete(result);
      
      // Reset form
      setResumeFile(null);
      setJobDescription("");
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

    } catch (err) {
      setError(err.message || 'An error occurred during scanning');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="py-16">
      <div className="max-w-4xl mx-auto px-6">
        <form onSubmit={handleSubmit} className="space-y-8">
          {/* File Upload Area */}
          <div className="bg-white rounded-2xl shadow-lg p-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center">
              <Upload size={24} className="mr-3 text-blue-600" />
              Upload Resume
            </h2>
            
            <div
              className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 ${
                dragActive
                  ? 'border-blue-500 bg-blue-50'
                  : resumeFile
                  ? 'border-green-500 bg-green-50'
                  : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx"
                onChange={handleFileInputChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                disabled={isLoading}
              />
              
              {resumeFile ? (
                <div className="space-y-4">
                  <CheckCircle size={48} className="mx-auto text-green-500" />
                  <div>
                    <p className="text-lg font-semibold text-green-700">File Selected</p>
                    <p className="text-gray-600">{resumeFile.name}</p>
                    <p className="text-sm text-gray-500">
                      {(resumeFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setResumeFile(null);
                      if (fileInputRef.current) fileInputRef.current.value = "";
                    }}
                    disabled={isLoading}
                  >
                    Choose Different File
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  <FileText size={48} className="mx-auto text-gray-400" />
                  <div>
                    <p className="text-lg font-semibold text-gray-700">
                      Drop your resume here or click to browse
                    </p>
                    <p className="text-gray-500">Supports PDF and DOCX files up to 10MB</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Job Description */}
          <div className="bg-white rounded-2xl shadow-lg p-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center">
              <FileText size={24} className="mr-3 text-purple-600" />
              Job Description
            </h2>
            
            <textarea
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="Paste the job description here... Include required skills, experience, qualifications, and any other relevant details for the position."
              className="w-full h-48 p-4 border border-gray-300 rounded-xl resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
              disabled={isLoading}
            />
            
            <div className="flex justify-between items-center mt-4">
              <p className="text-sm text-gray-500">
                {jobDescription.length}/50 characters minimum
              </p>
              {jobDescription.length >= 50 && (
                <CheckCircle size={16} className="text-green-500" />
              )}
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center space-x-3">
              <AlertCircle size={20} className="text-red-500 flex-shrink-0" />
              <p className="text-red-700">{error}</p>
            </div>
          )}

          {/* Submit Button */}
          <div className="text-center">
            <Button
              type="submit"
              disabled={!resumeFile || !jobDescription.trim() || jobDescription.length < 50 || isLoading}
              className="bg-gradient-to-r from-blue-600 to-purple-600 text-white px-8 py-4 text-lg font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-200 hover:scale-105 shadow-lg disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              {isLoading ? (
                <>
                  <Loader2 size={20} className="mr-2 animate-spin" />
                  Analyzing Resume...
                </>
              ) : (
                <>
                  <Upload size={20} className="mr-2" />
                  Scan Resume
                </>
              )}
            </Button>
          </div>

          {/* Loading Progress */}
          {isLoading && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-6">
              <div className="flex items-center space-x-3 mb-4">
                <Loader2 size={20} className="text-blue-600 animate-spin" />
                <p className="text-blue-700 font-semibold">AI Analysis in Progress</p>
              </div>
              <div className="space-y-2 text-sm text-blue-600">
                <p>• Extracting text from resume...</p>
                <p>• Analyzing skills and experience with GPT-4o...</p>
                <p>• Calculating job match score...</p>
                <p>• Generating analysis report...</p>
              </div>
            </div>
          )}
        </form>
      </div>
    </section>
  );
};

export default UploadSection;
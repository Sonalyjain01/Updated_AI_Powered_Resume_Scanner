import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "./ui/button";
import { scanKeys, useDeleteScan, useScanHistory } from "../hooks/useScans";
import { 
  History, 
  FileText, 
  Target, 
  Calendar,
  Search,
  RefreshCw,
  Trash2,
  Eye
} from "lucide-react";

const HistorySection = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, error, refetch, isFetching } = useScanHistory();
  const deleteScan = useDeleteScan();
  const [searchTerm, setSearchTerm] = useState("");

  const scanHistory = data || [];
  const historyError = error?.message || deleteScan.error?.message || null;
  const isRefreshing = isFetching;
  const onRefresh = () => refetch();

  const onSelectScan = (scan) => {
    queryClient.setQueryData(scanKeys.detail(scan.id), scan);
    navigate(`/app/results/${scan.id}`);
  };

  const filteredHistory = scanHistory.filter(scan =>
    scan.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
    scan.job_description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleRefresh = () => onRefresh();

  const getScoreColor = (score) => {
    if (score >= 80) return "text-green-600 bg-green-100";
    if (score >= 60) return "text-yellow-600 bg-yellow-100";
    return "text-red-600 bg-red-100";
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handleDeleteScan = (scanId) => {
    deleteScan.mutate(scanId);
  };

  return (
    <section className="py-16">
      <div className="max-w-6xl mx-auto px-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8">
          <div>
            <h2 className="text-3xl font-bold text-gray-900 mb-2">Scan History</h2>
            <p className="text-gray-600">View and manage your previous resume analyses</p>
          </div>
          
          <Button
            onClick={handleRefresh}
            variant="outline"
            disabled={isRefreshing}
            className="mt-4 sm:mt-0 hover:bg-blue-50"
          >
            <RefreshCw size={18} className={`mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        {/* Search and Stats */}
        <div className="bg-white rounded-2xl shadow-lg p-6 mb-8">
          <div className="flex flex-col lg:flex-row gap-6">
            {/* Search */}
            <div className="flex-1">
              <div className="relative">
                <Search size={20} className="absolute left-3 top-3 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search by filename or job description..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Stats */}
            <div className="flex space-x-6">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">{scanHistory.length}</div>
                <div className="text-sm text-gray-500">Total Scans</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">
                  {scanHistory.length > 0 
                    ? Math.round(scanHistory.reduce((sum, scan) => sum + scan.match_score, 0) / scanHistory.length)
                    : 0
                  }%
                </div>
                <div className="text-sm text-gray-500">Avg. Match</div>
              </div>
            </div>
          </div>
        </div>

        {/* History List */}
        {historyError && (
          <div role="alert" className="flex items-center justify-between gap-4 bg-red-50 border border-red-300 text-red-900 rounded-xl p-4 mb-6">
            <p>{historyError}</p>
            <Button variant="outline" size="sm" onClick={onRefresh}>Try again</Button>
          </div>
        )}

        {filteredHistory.length === 0 && !historyError ? (
          <div className="bg-white rounded-2xl shadow-lg p-12 text-center">
            <History size={48} className="mx-auto text-gray-300 mb-4" />
            <h3 className="text-xl font-semibold text-gray-600 mb-2">
              {scanHistory.length === 0 ? "No scans yet" : "No matching results"}
            </h3>
            <p className="text-gray-500">
              {scanHistory.length === 0 
                ? "Start by uploading your first resume for analysis"
                : "Try adjusting your search terms"
              }
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredHistory.map((scan) => (
              <div key={scan.id} className="bg-white rounded-2xl shadow-lg p-6 hover:shadow-xl transition-shadow duration-200">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-start space-x-4">
                      <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                        <FileText size={24} className="text-blue-600" />
                      </div>
                      
                      <div className="flex-1 min-w-0">
                        <h3 className="text-lg font-semibold text-gray-900 truncate mb-1">
                          {scan.filename}
                        </h3>
                        
                        <p className="text-gray-600 text-sm mb-2 line-clamp-2">
                          {scan.job_description.length > 100
                            ? `${scan.job_description.substring(0, 100)}...`
                            : scan.job_description
                          }
                        </p>
                        
                        <div className="flex items-center space-x-4 text-sm text-gray-500">
                          <div className="flex items-center space-x-1">
                            <Calendar size={14} />
                            <span>{formatDate(scan.created_at)}</span>
                          </div>
                          
                          <div className="flex items-center space-x-1">
                            <Target size={14} />
                            <span>{scan.extracted_data.skills.length} skills</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-4 mt-4 lg:mt-0">
                    {/* Match Score */}
                    <div className={`px-4 py-2 rounded-lg font-semibold ${getScoreColor(scan.match_score)}`}>
                      {Math.round(scan.match_score)}%
                    </div>
                    {scan.is_fallback && (
                      <span title={scan.fallback_notice} className="px-2 py-1 rounded-md text-xs font-medium bg-amber-100 text-amber-800">
                        Estimate
                      </span>
                    )}

                    {/* Actions */}
                    <div className="flex space-x-2">
                      <Button
                        onClick={() => onSelectScan(scan)}
                        variant="outline"
                        size="sm"
                        className="hover:bg-blue-50"
                      >
                        <Eye size={16} className="mr-1" />
                        View
                      </Button>
                      
                      <Button
                        onClick={() => handleDeleteScan(scan.id)}
                        variant="outline"
                        size="sm"
                        className="hover:bg-red-50 hover:text-red-600 hover:border-red-200"
                      >
                        <Trash2 size={16} />
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Quick Summary */}
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <p className="text-sm text-gray-600 italic">
                    {scan.analysis_summary.length > 150
                      ? `${scan.analysis_summary.substring(0, 150)}...`
                      : scan.analysis_summary
                    }
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Load More (placeholder for future pagination) */}
        {filteredHistory.length >= 10 && (
          <div className="text-center mt-8">
            <Button variant="outline" className="hover:bg-gray-50">
              Load More Results
            </Button>
          </div>
        )}
      </div>
    </section>
  );
};

export default HistorySection;
import React from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import ResultsSection from "../components/ResultsSection";
import { Button } from "../components/ui/button";
import { useScan } from "../hooks/useScans";

const ResultsPage = () => {
  const { scanId } = useParams();
  const navigate = useNavigate();
  const { data: scan, isPending, error } = useScan(scanId);

  if (isPending) {
    return (
      <div className="py-24 flex justify-center text-blue-600">
        <Loader2 size={32} className="animate-spin" aria-label="Loading scan" />
      </div>
    );
  }

  if (error || !scan) {
    return (
      <section className="py-24 text-center">
        <p className="text-lg text-gray-700 mb-6">
          {error?.status === 404 ? "This scan no longer exists." : error?.message || "The scan could not be loaded."}
        </p>
        <Button asChild>
          <Link to="/app">Start a new scan</Link>
        </Button>
      </section>
    );
  }

  return <ResultsSection scanResult={scan} onNewScan={() => navigate("/app")} />;
};

export default ResultsPage;

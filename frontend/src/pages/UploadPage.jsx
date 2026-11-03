import React from "react";
import { useNavigate } from "react-router-dom";
import UploadSection from "../components/UploadSection";

const UploadPage = () => {
  const navigate = useNavigate();
  return <UploadSection onScanComplete={(result) => navigate(`/app/results/${result.id}`)} />;
};

export default UploadPage;

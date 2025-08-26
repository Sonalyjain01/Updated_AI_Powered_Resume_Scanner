import React from "react";
import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import ResumeScanner from "./components/ResumeScanner";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ResumeScanner />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
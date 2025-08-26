import React from "react";
import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import ProjectShowcase from "./components/ProjectShowcase";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ProjectShowcase />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
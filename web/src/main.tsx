import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./styles.css";
import Projets from "./pages/Projets";
import Projet from "./pages/Projet";
import Apercu from "./pages/Apercu";
import Visuels from "./pages/Visuels";

createRoot(document.getElementById("racine")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Projets />} />
        <Route path="/projets/:slug" element={<Projet />} />
        <Route path="/projets/:slug/visuels" element={<Visuels />} />
        <Route path="/projets/:slug/apercu" element={<Apercu />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);

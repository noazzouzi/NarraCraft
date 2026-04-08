import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import FranchiseLibrary from "./pages/FranchiseLibrary";
import NewShort from "./pages/NewShort";
import History from "./pages/History";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/franchises" replace />} />
          <Route path="/franchises" element={<FranchiseLibrary />} />
          <Route path="/new" element={<NewShort />} />
          <Route path="/new/:id" element={<NewShort />} />
          <Route path="/history" element={<History />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

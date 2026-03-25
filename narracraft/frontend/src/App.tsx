import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/components/ThemeProvider";
import { Sidebar } from "@/components/Sidebar";
import { CommandPalette } from "@/components/CommandPalette";
import { Toaster } from "@/components/Toaster";
import Dashboard from "@/pages/Dashboard";
import Onboarding from "@/pages/Onboarding";
import AssetLibrary from "@/pages/AssetLibrary";
import TopicDiscovery from "@/pages/TopicDiscovery";
import TopicQueue from "@/pages/TopicQueue";
import Pipeline from "@/pages/Pipeline";
import Analytics from "@/pages/Analytics";
import Settings from "@/pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <Sidebar />
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/franchises" element={<Onboarding />} />
          <Route path="/assets" element={<AssetLibrary />} />
          <Route path="/discover" element={<TopicDiscovery />} />
          <Route path="/queue" element={<TopicQueue />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
        <CommandPalette />
        <Toaster />
      </ThemeProvider>
    </BrowserRouter>
  );
}

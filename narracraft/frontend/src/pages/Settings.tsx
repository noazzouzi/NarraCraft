import { useEffect, useState } from "react";
import { api, type LLMStatus } from "@/api/client";
import { Save, CheckCircle, AlertCircle, Loader2 } from "lucide-react";

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [llmStatus, setLlmStatus] = useState<LLMStatus | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getSettings().then(setSettings).catch(console.error);
    api.llmStatus().then(setLlmStatus).catch(console.error);
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      await api.updateSettings(settings);
      const status = await api.llmStatus();
      setLlmStatus(status);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const update = (key: string, value: string) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  return (
    <div className="p-8 max-w-2xl">
      <h2 className="text-2xl font-bold mb-8">Settings</h2>

      {/* LLM Provider */}
      <section className="mb-8">
        <h3 className="text-lg font-semibold mb-4">LLM Provider</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Provider</label>
            <select
              value={settings.llm_provider || "gemini_flash"}
              onChange={(e) => update("llm_provider", e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            >
              <option value="gemini_flash">Gemini 2.5 Flash (20 RPD free)</option>
              <option value="gemini_flash_lite">Gemini 2.5 Flash-Lite (20 RPD free)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Gemini API Key</label>
            <input
              type="password"
              value={settings.gemini_api_key || ""}
              onChange={(e) => update("gemini_api_key", e.target.value)}
              placeholder="Get key from aistudio.google.com"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Free — no credit card needed.{" "}
              <a
                href="https://aistudio.google.com/app/apikey"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:underline"
              >
                Get your key here
              </a>
            </p>
          </div>

          {/* Status indicator */}
          {llmStatus && (
            <div
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${
                llmStatus.configured
                  ? "bg-green-900/30 text-green-400"
                  : "bg-yellow-900/30 text-yellow-400"
              }`}
            >
              {llmStatus.configured ? (
                <>
                  <CheckCircle size={16} />
                  Connected — {llmStatus.model} ({llmStatus.rpd_limit} RPD free tier)
                </>
              ) : (
                <>
                  <AlertCircle size={16} />
                  {llmStatus.message || "Not configured"}
                </>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Theme */}
      <section className="mb-8">
        <h3 className="text-lg font-semibold mb-4">Appearance</h3>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Theme</label>
          <select
            value={settings.theme || "dark"}
            onChange={(e) => update("theme", e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="dark">Dark</option>
            <option value="light">Light</option>
          </select>
        </div>
      </section>

      {/* Save */}
      {error && (
        <div className="mb-4 px-3 py-2 bg-red-900/30 text-red-400 rounded-lg text-sm">
          {error}
        </div>
      )}

      <button
        onClick={handleSave}
        disabled={saving}
        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
      >
        {saving ? (
          <Loader2 size={16} className="animate-spin" />
        ) : saved ? (
          <CheckCircle size={16} />
        ) : (
          <Save size={16} />
        )}
        {saving ? "Saving..." : saved ? "Saved!" : "Save Settings"}
      </button>
    </div>
  );
}

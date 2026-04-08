import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  api,
  type Franchise,
  type Short,
  type TopicSuggestion,
  type Character,
} from "@/api/client";
import {
  Loader2,
  ChevronRight,
  ChevronLeft,
  Copy,
  CheckCircle,
  ExternalLink,
  Sparkles,
  Film,
  Upload,
} from "lucide-react";

const STEPS = ["Topic", "Script", "Characters", "Scenes", "Publish"];

export default function NewShort() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [short, setShort] = useState<Short | null>(null);
  const [franchises, setFranchises] = useState<Franchise[]>([]);
  const [selectedFranchise, setSelectedFranchise] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listFranchises().then(setFranchises).catch(console.error);
    if (id) {
      api.getShort(Number(id)).then(setShort).catch(console.error);
    }
  }, [id]);

  const currentStep = short?.current_step || 1;

  const createAndStart = async () => {
    if (!selectedFranchise) return;
    setLoading(true);
    setError("");
    try {
      const s = await api.createShort(selectedFranchise);
      navigate(`/new/${s.id}`, { replace: true });
      setShort(s);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // --- No short yet: franchise selection ---
  if (!short) {
    return (
      <div className="p-8 max-w-2xl">
        <h2 className="text-2xl font-bold mb-6">New Short</h2>
        <p className="text-gray-400 mb-4">Select a franchise to start:</p>

        {franchises.length === 0 ? (
          <p className="text-gray-500">
            No franchises yet.{" "}
            <a href="/franchises" className="text-blue-400 hover:underline">
              Add one first
            </a>
            .
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 mb-6">
              {franchises.map((f) => (
                <button
                  key={f.id}
                  onClick={() => setSelectedFranchise(f.id)}
                  className={`p-3 rounded-lg border text-left text-sm transition-colors ${
                    selectedFranchise === f.id
                      ? "border-blue-500 bg-blue-900/20"
                      : "border-gray-800 bg-gray-900 hover:border-gray-600"
                  }`}
                >
                  <p className="font-medium">{f.name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{f.category}</p>
                </button>
              ))}
            </div>

            {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

            <button
              onClick={createAndStart}
              disabled={!selectedFranchise || loading}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              Start Short
            </button>
          </>
        )}
      </div>
    );
  }

  // --- Wizard with steps ---
  return (
    <div className="p-8 max-w-3xl">
      {/* Step indicator */}
      <div className="flex items-center gap-1 mb-8">
        {STEPS.map((name, i) => {
          const stepNum = i + 1;
          const isActive = stepNum === currentStep;
          const isDone = stepNum < currentStep;
          return (
            <div key={name} className="flex items-center">
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  isActive
                    ? "bg-blue-600 text-white"
                    : isDone
                    ? "bg-green-900/30 text-green-400"
                    : "bg-gray-800 text-gray-500"
                }`}
              >
                {isDone ? <CheckCircle size={12} /> : <span>{stepNum}</span>}
                {name}
              </div>
              {i < STEPS.length - 1 && (
                <ChevronRight size={14} className="text-gray-700 mx-1" />
              )}
            </div>
          );
        })}
      </div>

      {/* Step content */}
      {currentStep === 1 && <StepTopic short={short} onUpdate={setShort} />}
      {currentStep === 2 && <StepScript short={short} onUpdate={setShort} />}
      {currentStep === 3 && <StepCharacters short={short} onUpdate={setShort} />}
      {currentStep === 4 && <StepScenes short={short} onUpdate={setShort} />}
      {currentStep === 5 && <StepPublish short={short} onUpdate={setShort} />}
    </div>
  );
}

// --- Step 1: Topic ---
function StepTopic({ short, onUpdate }: { short: Short; onUpdate: (s: Short) => void }) {
  const [topics, setTopics] = useState<TopicSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<TopicSuggestion | null>(null);
  const [generating, setGenerating] = useState(false);

  const suggestTopics = async () => {
    setLoading(true);
    try {
      const result = await api.generateTopics(short.id);
      setTopics(result.topics || []);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setLoading(false);
    }
  };

  const confirmTopic = async () => {
    if (!selected) return;
    setGenerating(true);
    try {
      const updated = await api.generateScript(
        short.id,
        selected.title,
        selected.hook,
        selected.characters
      );
      onUpdate(updated);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div>
      <h3 className="text-lg font-semibold mb-2">Step 1 — Choose a Topic</h3>
      <p className="text-sm text-gray-400 mb-4">
        {short.franchise_name} — Let the LLM suggest topics, then pick one.
      </p>

      {topics.length === 0 ? (
        <button
          onClick={suggestTopics}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
          {loading ? "Generating topics..." : "Suggest Topics"}
        </button>
      ) : (
        <>
          <div className="space-y-2 mb-6">
            {topics.map((t, i) => (
              <button
                key={i}
                onClick={() => setSelected(t)}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  selected === t
                    ? "border-blue-500 bg-blue-900/20"
                    : "border-gray-800 bg-gray-900 hover:border-gray-600"
                }`}
              >
                <p className="font-medium text-sm">{t.title}</p>
                <p className="text-xs text-gray-400 mt-1">{t.hook}</p>
                <div className="flex gap-2 mt-1">
                  {t.characters.map((c) => (
                    <span key={c} className="text-xs text-gray-500 bg-gray-800 px-1.5 py-0.5 rounded">
                      {c}
                    </span>
                  ))}
                </div>
              </button>
            ))}
          </div>

          <button
            onClick={confirmTopic}
            disabled={!selected || generating}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
          >
            {generating ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <ChevronRight size={16} />
            )}
            {generating ? "Generating script..." : "Select & Generate Script"}
          </button>
        </>
      )}
    </div>
  );
}

// --- Step 2: Script ---
function StepScript({ short, onUpdate }: { short: Short; onUpdate: (s: Short) => void }) {
  const script = short.script_json ? JSON.parse(short.script_json) : null;

  const goNext = async () => {
    // Veo 3 prompts are already generated with the script — just move to next step
    // If any scenes are missing prompts, generate them via template fallback
    const hasAllPrompts = short.scenes.every((s) => s.veo3_prompt);
    if (!hasAllPrompts) {
      const updated = await api.generatePrompts(short.id);
      onUpdate(updated);
    } else {
      const updated = await api.getShort(short.id);
      onUpdate(updated);
    }
  };

  return (
    <div>
      <h3 className="text-lg font-semibold mb-2">Step 2 — Review Script</h3>
      <p className="text-sm text-gray-400 mb-4">Topic: {short.topic}</p>

      {script?.scenes ? (
        <>
          <div className="space-y-3 mb-6">
            {script.scenes.map((scene: any, i: number) => (
              <div key={i} className="p-3 bg-gray-900 rounded-lg border border-gray-800">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-mono bg-gray-800 px-1.5 py-0.5 rounded">
                    S{scene.scene_number}
                  </span>
                  <span className="text-xs text-blue-400">{scene.character_name}</span>
                  <span className="text-xs text-gray-600">{scene.camera_angle}</span>
                </div>
                <p className="text-sm">"{scene.dialogue}"</p>
                <p className="text-xs text-gray-500 mt-1">
                  {scene.expression} — {scene.environment}
                </p>
              </div>
            ))}
          </div>

          <button
            onClick={goNext}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-medium transition-colors"
          >
            <ChevronRight size={16} />
            Continue to Characters
          </button>
        </>
      ) : (
        <p className="text-gray-500">No script generated yet.</p>
      )}
    </div>
  );
}

// --- Step 3: Characters ---
function StepCharacters({ short, onUpdate }: { short: Short; onUpdate: (s: Short) => void }) {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    // Get unique character IDs from scenes
    const charIds = [...new Set(short.scenes.map((s) => s.character_id).filter(Boolean))];
    if (charIds.length === 0) return;
    // Fetch franchise to get characters
    api.getFranchise(short.franchise_id).then((f) => {
      setCharacters(f.characters.filter((c) => charIds.includes(c.id)));
    });
  }, [short]);

  const allHaveImages = characters.length > 0 && characters.every((c) => c.image_path);

  const copyPrompt = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleUpload = async (charId: string, file: File) => {
    await api.uploadCharacterImage(charId, file);
    const f = await api.getFranchise(short.franchise_id);
    setCharacters(f.characters.filter((c) => short.scenes.some((s) => s.character_id === c.id)));
  };

  const goNext = async () => {
    await api.updateShort(short.id, { current_step: 4 } as any);
    const updated = await api.getShort(short.id);
    onUpdate(updated);
  };

  return (
    <div>
      <h3 className="text-lg font-semibold mb-2">Step 3 — Character References</h3>
      <p className="text-sm text-gray-400 mb-4">
        Generate character images in Google Flow. Copy the prompt, paste in Flow, upload the result.
      </p>

      <div className="space-y-4 mb-6">
        {characters.map((char) => {
          const prompt = [char.appearance, char.outfit].filter(Boolean).join(". ");
          return (
            <div key={char.id} className="p-4 bg-gray-900 rounded-lg border border-gray-800">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-12 h-12 rounded-lg overflow-hidden bg-gray-800 flex items-center justify-center flex-shrink-0">
                  {char.image_path ? (
                    <img src={`/images/${char.image_path}`} className="w-full h-full object-cover" />
                  ) : (
                    <Film size={18} className="text-gray-600" />
                  )}
                </div>
                <div>
                  <p className="font-medium">{char.name}</p>
                  <p className="text-xs text-gray-500">
                    {char.image_path ? (
                      <span className="text-green-400">Image uploaded</span>
                    ) : (
                      <span className="text-yellow-400">Needs image</span>
                    )}
                  </p>
                </div>
              </div>

              {/* Prompt */}
              {prompt && (
                <div className="mb-3">
                  <p className="text-xs text-gray-500 mb-1">Character Prompt (for Google Flow)</p>
                  <div className="p-2 bg-gray-800 rounded text-xs text-gray-300 max-h-24 overflow-y-auto">
                    {prompt}
                  </div>
                  <button
                    onClick={() => copyPrompt(prompt, char.id)}
                    className="flex items-center gap-1 mt-1 text-xs text-gray-400 hover:text-white transition-colors"
                  >
                    {copied === char.id ? (
                      <CheckCircle size={12} className="text-green-400" />
                    ) : (
                      <Copy size={12} />
                    )}
                    {copied === char.id ? "Copied!" : "Copy Prompt"}
                  </button>
                </div>
              )}

              {/* Upload */}
              {!char.image_path && (
                <label className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-xs font-medium cursor-pointer transition-colors w-fit">
                  <Upload size={12} /> Upload Image
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && handleUpload(char.id, e.target.files[0])}
                  />
                </label>
              )}
            </div>
          );
        })}
      </div>

      <button
        onClick={goNext}
        disabled={!allHaveImages}
        className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
      >
        <ChevronRight size={16} />
        {allHaveImages ? "Continue to Scenes" : "Upload all character images first"}
      </button>
    </div>
  );
}

// --- Step 4: Scenes ---
function StepScenes({ short, onUpdate }: { short: Short; onUpdate: (s: Short) => void }) {
  const [copied, setCopied] = useState<number | null>(null);

  const copyPrompt = (text: string, id: number) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const markDone = async (sceneId: number) => {
    await api.updateScene(sceneId, { status: "done" });
    const updated = await api.getShort(short.id);
    onUpdate(updated);
  };

  const updateFlowUrl = async (sceneId: number, url: string) => {
    await api.updateScene(sceneId, { flow_url: url });
  };

  const allDone = short.scenes.length > 0 && short.scenes.every((s) => s.status === "done");

  const goNext = async () => {
    await api.updateShort(short.id, { current_step: 5, status: "assembled" } as any);
    const updated = await api.getShort(short.id);
    onUpdate(updated);
  };

  return (
    <div>
      <h3 className="text-lg font-semibold mb-2">Step 4 — Generate Scene Videos</h3>
      <p className="text-sm text-gray-400 mb-4">
        For each scene: copy the Veo 3 prompt, upload the character reference as ingredient in Flow/Veo 3, generate, mark done.
      </p>

      <div className="space-y-3 mb-6">
        {short.scenes.map((scene) => (
          <div
            key={scene.id}
            className={`p-4 bg-gray-900 rounded-lg border transition-colors ${
              scene.status === "done" ? "border-green-800" : "border-gray-800"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono bg-gray-800 px-1.5 py-0.5 rounded">
                  S{scene.scene_number}
                </span>
                <span className="text-xs text-blue-400">{scene.character_name}</span>
                {scene.status === "done" && (
                  <CheckCircle size={14} className="text-green-400" />
                )}
              </div>
            </div>

            <p className="text-sm mb-2">"{scene.dialogue}"</p>

            {/* Veo 3 Prompt */}
            {scene.veo3_prompt && (
              <div className="mb-2">
                <p className="text-xs text-gray-500 mb-1">Veo 3 R2V Prompt</p>
                <div className="p-2 bg-gray-800 rounded text-xs text-gray-300 max-h-32 overflow-y-auto whitespace-pre-wrap">
                  {scene.veo3_prompt}
                </div>
                <button
                  onClick={() => copyPrompt(scene.veo3_prompt!, scene.id)}
                  className="flex items-center gap-1 mt-1 text-xs text-gray-400 hover:text-white transition-colors"
                >
                  {copied === scene.id ? (
                    <CheckCircle size={12} className="text-green-400" />
                  ) : (
                    <Copy size={12} />
                  )}
                  {copied === scene.id ? "Copied!" : "Copy Prompt"}
                </button>
              </div>
            )}

            {/* Flow URL + Mark Done */}
            <div className="flex items-center gap-2 mt-2">
              <input
                placeholder="Flow URL (optional)"
                defaultValue={scene.flow_url || ""}
                onBlur={(e) => updateFlowUrl(scene.id, e.target.value)}
                className="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-500"
              />
              {scene.status !== "done" && (
                <button
                  onClick={() => markDone(scene.id)}
                  className="flex items-center gap-1 px-2 py-1 bg-green-700 hover:bg-green-600 rounded text-xs font-medium transition-colors"
                >
                  <CheckCircle size={12} /> Done
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <button
        onClick={goNext}
        disabled={!allDone}
        className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
      >
        <ChevronRight size={16} />
        {allDone ? "Continue to Publish" : "Mark all scenes as done first"}
      </button>
    </div>
  );
}

// --- Step 5: Publish ---
function StepPublish({ short, onUpdate }: { short: Short; onUpdate: (s: Short) => void }) {
  const [copied, setCopied] = useState<string | null>(null);
  const navigate = useNavigate();

  const metadata = short.upload_metadata_json ? JSON.parse(short.upload_metadata_json) : {};

  const copyText = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  const markPublished = async () => {
    await api.updateShort(short.id, { status: "published" } as any);
    navigate("/history");
  };

  const fields = [
    { key: "youtube_title", label: "YouTube Title" },
    { key: "youtube_description", label: "YouTube Description" },
    { key: "tiktok_caption", label: "TikTok Caption" },
    { key: "instagram_caption", label: "Instagram Caption" },
  ];

  return (
    <div>
      <h3 className="text-lg font-semibold mb-2">Step 5 — Assemble & Publish</h3>

      {/* Checklist */}
      <div className="mb-6 p-4 bg-gray-900 rounded-lg border border-gray-800">
        <p className="text-sm font-medium mb-3">Assembly Checklist</p>
        <div className="space-y-2 text-sm text-gray-400">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" className="rounded" /> Import all scene clips into CapCut
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" className="rounded" /> Add captions / subtitles
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" className="rounded" /> Add background music
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" className="rounded" /> Export final video (9:16, 1080p)
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" className="rounded" /> Upload to TikTok
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" className="rounded" /> Upload to YouTube Shorts
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" className="rounded" /> Upload to Instagram Reels
          </label>
        </div>
      </div>

      {/* Upload Metadata */}
      <div className="space-y-3 mb-6">
        {fields.map(({ key, label }) => {
          const value = metadata[key] || "";
          if (!value) return null;
          return (
            <div key={key} className="p-3 bg-gray-900 rounded-lg border border-gray-800">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs text-gray-500">{label}</p>
                <button
                  onClick={() => copyText(value, key)}
                  className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors"
                >
                  {copied === key ? (
                    <CheckCircle size={12} className="text-green-400" />
                  ) : (
                    <Copy size={12} />
                  )}
                  {copied === key ? "Copied!" : "Copy"}
                </button>
              </div>
              <p className="text-sm">{value}</p>
            </div>
          );
        })}

        {metadata.youtube_tags && (
          <div className="p-3 bg-gray-900 rounded-lg border border-gray-800">
            <p className="text-xs text-gray-500 mb-1">YouTube Tags</p>
            <div className="flex flex-wrap gap-1">
              {metadata.youtube_tags.map((tag: string, i: number) => (
                <span key={i} className="text-xs bg-gray-800 px-2 py-0.5 rounded text-gray-300">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Mark Published */}
      <button
        onClick={markPublished}
        className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-medium transition-colors"
      >
        <CheckCircle size={16} /> Mark as Published
      </button>
    </div>
  );
}

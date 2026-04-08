import { useEffect, useState, useRef } from "react";
import {
  api,
  type Franchise,
  type FranchiseWithCharacters,
  type Character,
} from "@/api/client";
import {
  Plus,
  Loader2,
  Trash2,
  Upload,
  ExternalLink,
  ChevronLeft,
  Copy,
  CheckCircle,
  User,
  Gamepad2,
  Tv,
  ImageIcon,
} from "lucide-react";

export default function FranchiseLibrary() {
  const [franchises, setFranchises] = useState<Franchise[]>([]);
  const [selected, setSelected] = useState<FranchiseWithCharacters | null>(null);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [addingChar, setAddingChar] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCategory, setNewCategory] = useState("gaming");
  const [newCharName, setNewCharName] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    loadFranchises();
  }, []);

  const loadFranchises = async () => {
    setLoading(true);
    try {
      const list = await api.listFranchises();
      setFranchises(list);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const selectFranchise = async (id: string) => {
    try {
      const data = await api.getFranchise(id);
      setSelected(data);
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddFranchise = async () => {
    if (!newName.trim()) return;
    setAdding(true);
    try {
      const result = await api.createFranchise(newName.trim(), newCategory);
      setNewName("");
      setShowAdd(false);
      await loadFranchises();
      // Auto-navigate to the new franchise (characters are already created)
      await selectFranchise(result.id);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setAdding(false);
    }
  };

  const handleDeleteFranchise = async (id: string) => {
    if (!confirm("Delete this franchise and all its characters?")) return;
    await api.deleteFranchise(id);
    setSelected(null);
    await loadFranchises();
  };

  const handleAddCharacter = async () => {
    if (!newCharName.trim() || !selected) return;
    setAddingChar(true);
    try {
      await api.addCharacter(selected.id, newCharName.trim());
      setNewCharName("");
      await selectFranchise(selected.id);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setAddingChar(false);
    }
  };

  const handleDeleteCharacter = async (id: string) => {
    if (!confirm("Delete this character?")) return;
    await api.deleteCharacter(id);
    if (selected) await selectFranchise(selected.id);
  };

  const handleUploadImage = async (characterId: string, file: File) => {
    try {
      await api.uploadCharacterImage(characterId, file);
      if (selected) await selectFranchise(selected.id);
    } catch (e: any) {
      alert(e.message);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  // --- Detail View ---
  if (selected) {
    return (
      <div className="p-8">
        <button
          onClick={() => setSelected(null)}
          className="flex items-center gap-1 text-sm text-gray-400 hover:text-white mb-6 transition-colors"
        >
          <ChevronLeft size={16} /> Back to Library
        </button>

        <div className="flex items-start justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold">{selected.name}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs px-2 py-0.5 bg-gray-800 rounded text-gray-400">
                {selected.category}
              </span>
              <span className="text-xs text-gray-500">
                {selected.characters.length} characters
              </span>
            </div>
          </div>
          <button
            onClick={() => handleDeleteFranchise(selected.id)}
            className="text-gray-500 hover:text-red-400 transition-colors"
          >
            <Trash2 size={18} />
          </button>
        </div>

        {/* Franchise Details — Tags */}
        {selected.visual_aesthetic && (
          <div className="mb-4">
            <p className="text-xs text-gray-500 mb-2">Visual Aesthetic</p>
            <div className="flex flex-wrap gap-1.5">
              {selected.visual_aesthetic.split(",").map((tag, i) => (
                <span
                  key={i}
                  className="px-2 py-1 text-xs bg-blue-900/30 text-blue-300 border border-blue-800/50 rounded-md"
                >
                  {tag.trim()}
                </span>
              ))}
            </div>
          </div>
        )}
        {selected.iconic_elements && (
          <div className="mb-6">
            <p className="text-xs text-gray-500 mb-2">Iconic Elements</p>
            <div className="flex flex-wrap gap-1.5">
              {selected.iconic_elements.split(",").map((tag, i) => (
                <span
                  key={i}
                  className="px-2 py-1 text-xs bg-amber-900/30 text-amber-300 border border-amber-800/50 rounded-md"
                >
                  {tag.trim()}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Characters */}
        <h3 className="text-lg font-semibold mb-4">Characters</h3>

        <div className="space-y-4 mb-6">
          {selected.characters.map((char) => (
            <CharacterCard
              key={char.id}
              character={char}
              onDelete={() => handleDeleteCharacter(char.id)}
              onUpload={(file) => handleUploadImage(char.id, file)}
              onCopy={copyToClipboard}
              copied={copied}
            />
          ))}
        </div>

        {/* Add Character */}
        <div className="flex gap-2">
          <input
            value={newCharName}
            onChange={(e) => setNewCharName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddCharacter()}
            placeholder="Character name (e.g., Joel Miller)"
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={handleAddCharacter}
            disabled={addingChar || !newCharName.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
          >
            {addingChar ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
            {addingChar ? "Generating..." : "Add Character"}
          </button>
        </div>
      </div>
    );
  }

  // --- List View ---
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Franchise Library</h2>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors"
        >
          <Plus size={16} /> Add Franchise
        </button>
      </div>

      {/* Add Franchise Form */}
      {showAdd && (
        <div className="mb-6 p-4 bg-gray-900 rounded-lg border border-gray-800">
          <div className="flex gap-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddFranchise()}
              placeholder="Franchise name (e.g., The Last of Us)"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
              autoFocus
            />
            <select
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
            >
              <option value="gaming">Gaming</option>
              <option value="anime">Anime</option>
            </select>
            <button
              onClick={handleAddFranchise}
              disabled={adding || !newName.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
            >
              {adding ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
              {adding ? "Creating..." : "Create"}
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            The LLM will generate visual aesthetic and iconic elements automatically.
          </p>
        </div>
      )}

      {/* Franchise Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-gray-500">
          <Loader2 size={24} className="animate-spin" />
        </div>
      ) : franchises.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <Gamepad2 size={48} className="mx-auto mb-4 opacity-30" />
          <p>No franchises yet. Add one to get started.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {franchises.map((f) => (
            <button
              key={f.id}
              onClick={() => selectFranchise(f.id)}
              className="text-left p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 transition-colors"
            >
              <div className="flex items-center gap-2 mb-2">
                {f.category === "gaming" ? (
                  <Gamepad2 size={18} className="text-blue-400" />
                ) : (
                  <Tv size={18} className="text-pink-400" />
                )}
                <h3 className="font-semibold">{f.name}</h3>
              </div>
              {f.visual_aesthetic && (
                <p className="text-xs text-gray-500 line-clamp-2">{f.visual_aesthetic}</p>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Character Card Component ---

function CharacterCard({
  character,
  onDelete,
  onUpload,
  onCopy,
  copied,
}: {
  character: Character;
  onDelete: () => void;
  onUpload: (file: File) => void;
  onCopy: (text: string, id: string) => void;
  copied: string | null;
}) {
  const fileInput = useRef<HTMLInputElement>(null);

  // Use the full Flow prompt if available, otherwise fall back to appearance+outfit
  const promptText = character.flow_prompt || [
    character.appearance,
    character.outfit,
  ]
    .filter(Boolean)
    .join(". ");

  return (
    <div className="p-4 bg-gray-900 rounded-lg border border-gray-800">
      <div className="flex gap-4">
        {/* Image */}
        <div className="w-20 h-20 flex-shrink-0 rounded-lg overflow-hidden bg-gray-800 flex items-center justify-center">
          {character.image_path ? (
            <img
              src={`/images/${character.image_path}`}
              alt={character.name}
              className="w-full h-full object-cover"
            />
          ) : (
            <User size={24} className="text-gray-600" />
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <h4 className="font-semibold">{character.name}</h4>
            <button onClick={onDelete} className="text-gray-600 hover:text-red-400">
              <Trash2 size={14} />
            </button>
          </div>

          {character.appearance && (
            <p className="text-xs text-gray-400 mt-1 line-clamp-2">{character.appearance}</p>
          )}

          {character.personality && (
            <p className="text-xs text-gray-500 mt-1">{character.personality}</p>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2 mt-3">
        {/* Upload Image */}
        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
          className="hidden"
        />
        <button
          onClick={() => fileInput.current?.click()}
          className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-800 hover:bg-gray-700 rounded transition-colors"
        >
          {character.image_path ? (
            <ImageIcon size={12} className="text-green-400" />
          ) : (
            <Upload size={12} />
          )}
          {character.image_path ? "Replace Image" : "Upload Image"}
        </button>

        {/* Copy Prompt */}
        {promptText && (
          <button
            onClick={() => onCopy(promptText, character.id)}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-800 hover:bg-gray-700 rounded transition-colors"
          >
            {copied === character.id ? (
              <CheckCircle size={12} className="text-green-400" />
            ) : (
              <Copy size={12} />
            )}
            {copied === character.id ? "Copied!" : "Copy Prompt"}
          </button>
        )}

        {/* Flow URL */}
        {character.flow_url && (
          <a
            href={character.flow_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-800 hover:bg-gray-700 rounded transition-colors"
          >
            <ExternalLink size={12} /> Flow
          </a>
        )}
      </div>
    </div>
  );
}

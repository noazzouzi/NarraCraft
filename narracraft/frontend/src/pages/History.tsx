import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type ShortListItem } from "@/api/client";
import {
  Loader2,
  Trash2,
  Play,
  CheckCircle,
  Clock,
  PenLine,
  Film,
  Upload as UploadIcon,
} from "lucide-react";

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  draft: { label: "Draft", color: "text-gray-400", icon: PenLine },
  scripted: { label: "Scripted", color: "text-yellow-400", icon: PenLine },
  in_production: { label: "In Production", color: "text-blue-400", icon: Film },
  assembled: { label: "Assembled", color: "text-purple-400", icon: Film },
  published: { label: "Published", color: "text-green-400", icon: CheckCircle },
};

export default function History() {
  const [shorts, setShorts] = useState<ShortListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("");
  const navigate = useNavigate();

  useEffect(() => {
    loadShorts();
  }, [filter]);

  const loadShorts = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filter) params.status = filter;
      const list = await api.listShorts(params);
      setShorts(list);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this Short?")) return;
    await api.deleteShort(id);
    await loadShorts();
  };

  const handleResume = (short: ShortListItem) => {
    navigate(`/new/${short.id}`);
  };

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold mb-6">History</h2>

      {/* Filters */}
      <div className="flex gap-2 mb-6">
        {["", "draft", "scripted", "in_production", "assembled", "published"].map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
              filter === s
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-400 hover:text-white"
            }`}
          >
            {s === "" ? "All" : STATUS_CONFIG[s]?.label || s}
          </button>
        ))}
      </div>

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-gray-500">
          <Loader2 size={24} className="animate-spin" />
        </div>
      ) : shorts.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <Clock size={48} className="mx-auto mb-4 opacity-30" />
          <p>No Shorts yet. Create one from the New Short page.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {shorts.map((short) => {
            const cfg = STATUS_CONFIG[short.status] || STATUS_CONFIG.draft;
            const Icon = cfg.icon;
            return (
              <div
                key={short.id}
                onClick={() => handleResume(short)}
                className="flex items-center gap-4 p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 cursor-pointer transition-colors"
              >
                <Icon size={18} className={cfg.color} />
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">
                    {short.topic || "Untitled Short"}
                  </p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                    <span>{short.franchise_name}</span>
                    <span>{short.scene_count} scenes</span>
                    <span>Step {short.current_step}/5</span>
                  </div>
                </div>
                <span className={`text-xs ${cfg.color}`}>{cfg.label}</span>
                <span className="text-xs text-gray-600">
                  {short.created_at?.split("T")[0] || ""}
                </span>
                <button
                  onClick={(e) => handleDelete(short.id, e)}
                  className="text-gray-600 hover:text-red-400 transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

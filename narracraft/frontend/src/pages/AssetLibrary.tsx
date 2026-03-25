import { useState, useEffect, useCallback } from "react";
import { useTheme } from "@/components/ThemeProvider";
import { listAssets, approveAsset, rejectAsset } from "@/api/client";
import {
  ImageIcon,
  Check,
  X,
  Loader2,
  Filter,
  Users,
  MapPin,
  Puzzle,
} from "lucide-react";

interface Asset {
  id: string;
  franchise_id: string;
  asset_type: string;
  archetype_id: string | null;
  status: string;
  is_narrator: boolean;
  model_dir: string | null;
  metadata_json: string | null;
  created_at: string;
  approved_at: string | null;
}

type StatusFilter = "all" | "pending" | "approved" | "rejected";
type TypeFilter = "all" | "character" | "environment" | "prop";

export default function AssetLibrary() {
  const { theme } = useTheme();

  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [total, setTotal] = useState(0);
  const [actioning, setActioning] = useState<string | null>(null);

  const fetchAssets = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (statusFilter !== "all") params.status = statusFilter;
      if (typeFilter !== "all") params.type = typeFilter;
      const data = await listAssets(params);
      setAssets(data.assets as unknown as Asset[]);
      setTotal(data.total);
    } catch {
      setAssets([]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, typeFilter]);

  useEffect(() => {
    fetchAssets();
  }, [fetchAssets]);

  const handleApprove = async (id: string) => {
    setActioning(id);
    try {
      await approveAsset(id);
      setAssets((prev) =>
        prev.map((a) => (a.id === id ? { ...a, status: "approved" } : a)),
      );
    } finally {
      setActioning(null);
    }
  };

  const handleReject = async (id: string) => {
    setActioning(id);
    try {
      await rejectAsset(id);
      setAssets((prev) =>
        prev.map((a) => (a.id === id ? { ...a, status: "rejected" } : a)),
      );
    } finally {
      setActioning(null);
    }
  };

  const typeIcon = (type: string) => {
    switch (type) {
      case "character": return <Users size={14} />;
      case "environment": return <MapPin size={14} />;
      case "prop": return <Puzzle size={14} />;
      default: return <ImageIcon size={14} />;
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case "approved": return theme.success;
      case "rejected": return theme.danger;
      case "pending": return theme.accent;
      default: return theme.dim;
    }
  };

  const cardStyle = {
    background: theme.surface,
    border: `1px solid ${theme.border}`,
    borderRadius: theme.card.borderRadius,
    ...theme.card,
  };

  const parseMeta = (json: string | null): Record<string, unknown> => {
    if (!json) return {};
    try { return JSON.parse(json); } catch { return {}; }
  };

  return (
    <div className="flex-1 p-5 overflow-y-auto" style={{ fontFamily: theme.body }}>
      <h1
        className="m-0 mb-1"
        style={{ fontSize: 22, fontWeight: 700, fontFamily: theme.font, color: theme.text }}
      >
        Asset Library
      </h1>
      <p className="mb-5" style={{ fontSize: 13, color: theme.dim }}>
        Browse, approve, and manage persistent visual assets.
      </p>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-5">
        <div className="flex items-center gap-1.5">
          <Filter size={14} style={{ color: theme.dim }} />
          <span style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 10 }}>STATUS:</span>
          {(["all", "pending", "approved", "rejected"] as StatusFilter[]).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className="px-2.5 py-1 text-[11px] font-semibold tracking-wide cursor-pointer"
              style={{
                background: statusFilter === s ? `${theme.accent}20` : "transparent",
                border: `1px solid ${statusFilter === s ? theme.accent : theme.border}`,
                color: statusFilter === s ? theme.accent : theme.dim,
                fontFamily: theme.mono,
                borderRadius: theme.card.borderRadius,
              }}
            >
              {s.toUpperCase()}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1.5">
          <span style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 10 }}>TYPE:</span>
          {(["all", "character", "environment", "prop"] as TypeFilter[]).map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className="px-2.5 py-1 text-[11px] font-semibold tracking-wide cursor-pointer"
              style={{
                background: typeFilter === t ? `${theme.accent}20` : "transparent",
                border: `1px solid ${typeFilter === t ? theme.accent : theme.border}`,
                color: typeFilter === t ? theme.accent : theme.dim,
                fontFamily: theme.mono,
                borderRadius: theme.card.borderRadius,
              }}
            >
              {t.toUpperCase()}
            </button>
          ))}
        </div>

        <span style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 11, marginLeft: "auto" }}>
          {total} assets
        </span>
      </div>

      {/* Assets grid */}
      {loading ? (
        <div className="flex items-center justify-center gap-3 p-12" style={cardStyle}>
          <Loader2 size={20} className="animate-spin" style={{ color: theme.accent }} />
          <span style={{ color: theme.dim, fontFamily: theme.mono, fontSize: 12 }}>
            Loading assets...
          </span>
        </div>
      ) : assets.length === 0 ? (
        <div className="p-8 text-center" style={cardStyle}>
          <ImageIcon size={32} style={{ color: theme.muted }} className="mx-auto mb-3" />
          <p style={{ color: theme.dim, fontFamily: theme.mono, fontSize: 12 }}>
            No assets found. Onboard a franchise to generate character and environment assets.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-3">
          {assets.map((asset) => {
            const meta = parseMeta(asset.metadata_json);
            const name = (meta.name as string) || asset.archetype_id || asset.id.split("/").pop() || "Unnamed";
            const description = (meta.description as string) || (meta.visual_description as string) || "";
            const isActioning = actioning === asset.id;

            return (
              <div key={asset.id} className="flex flex-col" style={cardStyle}>
                {/* Asset preview area */}
                <div
                  className="flex items-center justify-center h-32"
                  style={{ background: `${theme.accent}08`, borderBottom: `1px solid ${theme.border}` }}
                >
                  {asset.model_dir ? (
                    <img
                      src={asset.model_dir}
                      alt={name}
                      className="w-full h-full object-cover"
                      style={{ borderRadius: `${theme.card.borderRadius} ${theme.card.borderRadius} 0 0` }}
                    />
                  ) : (
                    <div className="flex flex-col items-center gap-2" style={{ color: theme.muted }}>
                      {typeIcon(asset.asset_type)}
                      <span className="text-[10px]" style={{ fontFamily: theme.mono }}>
                        NOT GENERATED
                      </span>
                    </div>
                  )}
                </div>

                {/* Info */}
                <div className="p-3 flex-1">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-xs font-bold truncate" style={{ color: theme.text }}>
                      {name}
                    </span>
                    {asset.is_narrator && (
                      <span
                        className="text-[9px] px-1.5 py-0.5 font-bold tracking-wider"
                        style={{
                          background: `${theme.accent}20`,
                          color: theme.accent,
                          borderRadius: "2px",
                          fontFamily: theme.mono,
                        }}
                      >
                        NARRATOR
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className="flex items-center gap-1 text-[10px]"
                      style={{ color: theme.dim, fontFamily: theme.mono }}
                    >
                      {typeIcon(asset.asset_type)}
                      {asset.asset_type}
                    </span>
                    <span
                      className="text-[10px] px-1.5 py-0.5 font-bold tracking-wider"
                      style={{
                        background: `${statusColor(asset.status)}20`,
                        color: statusColor(asset.status),
                        borderRadius: "2px",
                        fontFamily: theme.mono,
                      }}
                    >
                      {asset.status.toUpperCase()}
                    </span>
                  </div>

                  {description && (
                    <p className="text-[11px] m-0 line-clamp-2" style={{ color: theme.dim }}>
                      {description.slice(0, 120)}
                    </p>
                  )}

                  <div className="text-[10px] mt-2" style={{ color: theme.muted, fontFamily: theme.mono }}>
                    {asset.franchise_id}
                  </div>
                </div>

                {/* Actions */}
                {asset.status === "pending" && (
                  <div
                    className="flex border-t"
                    style={{ borderColor: theme.border }}
                  >
                    <button
                      onClick={() => handleApprove(asset.id)}
                      disabled={isActioning}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2 text-[11px] font-bold tracking-wider cursor-pointer"
                      style={{
                        background: "transparent",
                        border: "none",
                        borderRight: `1px solid ${theme.border}`,
                        color: theme.success,
                        fontFamily: theme.mono,
                      }}
                    >
                      {isActioning ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                      APPROVE
                    </button>
                    <button
                      onClick={() => handleReject(asset.id)}
                      disabled={isActioning}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2 text-[11px] font-bold tracking-wider cursor-pointer"
                      style={{
                        background: "transparent",
                        border: "none",
                        color: theme.danger,
                        fontFamily: theme.mono,
                      }}
                    >
                      {isActioning ? <Loader2 size={12} className="animate-spin" /> : <X size={12} />}
                      REJECT
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

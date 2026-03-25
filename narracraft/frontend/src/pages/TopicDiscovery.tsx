import { useState, useEffect, useCallback } from "react";
import { useTheme } from "@/components/ThemeProvider";
import { listTopics, discoverTopics, queueTopic, getConfig } from "@/api/client";
import {
  Search,
  Loader2,
  ArrowUpDown,
  Globe,
  MessageSquare,
  Video,
  Sparkles,
  ChevronDown,
  Plus,
  ListTodo,
  LayoutGrid,
  List,
} from "lucide-react";

interface Topic {
  id: string;
  franchise_id: string;
  title: string;
  description: string | null;
  category: string | null;
  score: number;
  score_breakdown_json: string | null;
  sources_json: string | null;
  status: string;
  created_at: string;
}

interface FranchiseOption {
  id: string;
  name: string;
}

type ViewMode = "card" | "list";
type SortBy = "score" | "created_at" | "title";

export default function TopicDiscovery() {
  const { theme } = useTheme();

  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>("card");
  const [sortBy, setSortBy] = useState<SortBy>("score");
  const [filterCategory, setFilterCategory] = useState("all");
  const [filterFranchise, setFilterFranchise] = useState("all");

  const [franchises, setFranchises] = useState<FranchiseOption[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [discoverFranchise, setDiscoverFranchise] = useState("");
  const [discoverResult, setDiscoverResult] = useState<{ discovered: number; errors: string[] | null } | null>(null);
  const [showDiscoverPanel, setShowDiscoverPanel] = useState(false);
  const [discoverSources, setDiscoverSources] = useState<string[]>(["wiki", "reddit", "youtube", "ai"]);

  // Fetch franchises for dropdown
  useEffect(() => {
    getConfig().then((cfg) => {
      setFranchises(cfg.franchises.map((f) => ({ id: f.id, name: f.name })));
      if (cfg.franchises.length > 0 && !discoverFranchise) {
        setDiscoverFranchise(cfg.franchises[0].id);
      }
    }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchTopics = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { status: "discovered" };
      if (filterFranchise !== "all") params.franchise = filterFranchise;
      const data = await listTopics(params);
      let sorted = data.topics as unknown as Topic[];

      // Client-side category filter + sort
      if (filterCategory !== "all") {
        sorted = sorted.filter((t) => t.category === filterCategory);
      }
      if (sortBy === "score") sorted.sort((a, b) => b.score - a.score);
      else if (sortBy === "title") sorted.sort((a, b) => a.title.localeCompare(b.title));
      else sorted.sort((a, b) => b.created_at.localeCompare(a.created_at));

      setTopics(sorted);
      setTotal(data.total);
    } catch {
      setTopics([]);
    } finally {
      setLoading(false);
    }
  }, [filterFranchise, filterCategory, sortBy]);

  useEffect(() => {
    fetchTopics();
  }, [fetchTopics]);

  const handleDiscover = async () => {
    if (!discoverFranchise) return;
    setDiscovering(true);
    setDiscoverResult(null);
    try {
      const data = await discoverTopics({
        franchise_id: discoverFranchise,
        sources: discoverSources,
      });
      setDiscoverResult({ discovered: data.discovered, errors: data.errors });
      fetchTopics();
    } catch {
      setDiscoverResult({ discovered: 0, errors: ["Discovery failed — check backend"] });
    } finally {
      setDiscovering(false);
    }
  };

  const handleQueue = async (topicId: string) => {
    try {
      await queueTopic(topicId);
      setTopics((prev) => prev.filter((t) => t.id !== topicId));
    } catch { /* ignore */ }
  };

  const toggleSource = (src: string) => {
    setDiscoverSources((prev) =>
      prev.includes(src) ? prev.filter((s) => s !== src) : [...prev, src],
    );
  };

  const sourceIcon = (type: string) => {
    switch (type) {
      case "wiki": return <Globe size={12} />;
      case "reddit": return <MessageSquare size={12} />;
      case "youtube": return <Video size={12} />;
      case "ai": return <Sparkles size={12} />;
      default: return <Search size={12} />;
    }
  };

  const tierColor = (score: number) => {
    if (score >= 30) return "#FFD700";
    if (score >= 22) return theme.success;
    if (score >= 15) return theme.accent;
    if (score >= 8) return theme.dim;
    return theme.muted;
  };

  const tierLabel = (score: number) => {
    if (score >= 30) return "S";
    if (score >= 22) return "A";
    if (score >= 15) return "B";
    if (score >= 8) return "C";
    return "D";
  };

  const categoryLabel = (cat: string | null) => {
    const map: Record<string, string> = {
      characters: "Characters",
      dev_design: "Dev/Design",
      lore: "Lore",
      easter_egg: "Easter Egg",
      cut_content: "Cut Content",
      memes: "Memes",
    };
    return cat ? map[cat] || cat : "Unknown";
  };

  const parseSources = (json: string | null): { type: string; url?: string; title?: string }[] => {
    if (!json) return [];
    try { return JSON.parse(json); } catch { return []; }
  };

  const cardStyle = {
    background: theme.surface,
    border: `1px solid ${theme.border}`,
    borderRadius: theme.card.borderRadius,
    ...theme.card,
  };

  const categories = ["all", "characters", "dev_design", "lore", "easter_egg", "cut_content", "memes"];

  return (
    <div className="flex-1 p-5 overflow-y-auto" style={{ fontFamily: theme.body }}>
      <div className="flex items-start justify-between mb-5">
        <div>
          <h1 className="m-0 mb-1" style={{ fontSize: 22, fontWeight: 700, fontFamily: theme.font, color: theme.text }}>
            Discover Topics
          </h1>
          <p className="m-0" style={{ fontSize: 13, color: theme.dim }}>
            Find and score topics from wikis, Reddit, YouTube, and AI.
          </p>
        </div>
        <button
          onClick={() => setShowDiscoverPanel(!showDiscoverPanel)}
          className="flex items-center gap-2 px-4 py-2 text-xs font-bold tracking-wider cursor-pointer"
          style={{
            background: theme.accent,
            border: "none",
            color: theme.bg,
            fontFamily: theme.mono,
            borderRadius: theme.card.borderRadius,
          }}
        >
          <Plus size={14} />
          DISCOVER NEW
          <ChevronDown size={12} style={{ transform: showDiscoverPanel ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
        </button>
      </div>

      {/* Discover panel */}
      {showDiscoverPanel && (
        <div className="p-4 mb-5" style={cardStyle}>
          <div className="flex items-end gap-4">
            <div className="flex-1">
              <label className="block text-[10px] mb-1.5" style={{ color: theme.muted, fontFamily: theme.mono }}>
                FRANCHISE
              </label>
              <select
                value={discoverFranchise}
                onChange={(e) => setDiscoverFranchise(e.target.value)}
                className="w-full p-2 text-xs"
                style={{
                  background: theme.bg,
                  border: `1px solid ${theme.border}`,
                  borderRadius: theme.card.borderRadius,
                  color: theme.text,
                  fontFamily: theme.mono,
                }}
              >
                {franchises.length === 0 && (
                  <option value="">No franchises — onboard one first</option>
                )}
                {franchises.map((f) => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[10px] mb-1.5" style={{ color: theme.muted, fontFamily: theme.mono }}>
                SOURCES
              </label>
              <div className="flex gap-1.5">
                {(["wiki", "reddit", "youtube", "ai"] as const).map((src) => (
                  <button
                    key={src}
                    onClick={() => toggleSource(src)}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-semibold cursor-pointer"
                    style={{
                      background: discoverSources.includes(src) ? `${theme.accent}20` : "transparent",
                      border: `1px solid ${discoverSources.includes(src) ? theme.accent : theme.border}`,
                      color: discoverSources.includes(src) ? theme.accent : theme.dim,
                      fontFamily: theme.mono,
                      borderRadius: theme.card.borderRadius,
                    }}
                  >
                    {sourceIcon(src)}
                    {src.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            <button
              onClick={handleDiscover}
              disabled={discovering || !discoverFranchise || discoverSources.length === 0}
              className="flex items-center gap-2 px-5 py-2 text-xs font-bold tracking-wider cursor-pointer disabled:opacity-40"
              style={{
                background: `${theme.accent}15`,
                border: `1px solid ${theme.accent}`,
                color: theme.accent,
                fontFamily: theme.mono,
                borderRadius: theme.card.borderRadius,
              }}
            >
              {discovering ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              {discovering ? "DISCOVERING..." : "RUN DISCOVERY"}
            </button>
          </div>

          {discoverResult && (
            <div className="mt-3 text-xs" style={{ color: discoverResult.discovered > 0 ? theme.success : theme.danger, fontFamily: theme.mono }}>
              {discoverResult.discovered > 0
                ? `Discovered ${discoverResult.discovered} new topics.`
                : "No new topics discovered."}
              {discoverResult.errors && discoverResult.errors.length > 0 && (
                <span style={{ color: theme.danger }}> Errors: {discoverResult.errors.join(", ")}</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Filters & view controls */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-1.5">
          <span style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 10 }}>CATEGORY:</span>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setFilterCategory(cat)}
              className="px-2 py-1 text-[10px] font-semibold tracking-wide cursor-pointer"
              style={{
                background: filterCategory === cat ? `${theme.accent}20` : "transparent",
                border: `1px solid ${filterCategory === cat ? theme.accent : theme.border}`,
                color: filterCategory === cat ? theme.accent : theme.dim,
                fontFamily: theme.mono,
                borderRadius: theme.card.borderRadius,
              }}
            >
              {cat === "all" ? "ALL" : categoryLabel(cat).toUpperCase()}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1.5 ml-auto">
          <button
            onClick={() => setSortBy((s) => s === "score" ? "created_at" : s === "created_at" ? "title" : "score")}
            className="flex items-center gap-1 px-2 py-1 text-[10px] cursor-pointer"
            style={{
              background: "transparent",
              border: `1px solid ${theme.border}`,
              color: theme.dim,
              fontFamily: theme.mono,
              borderRadius: theme.card.borderRadius,
            }}
          >
            <ArrowUpDown size={10} />
            {sortBy === "score" ? "SCORE" : sortBy === "title" ? "TITLE" : "NEWEST"}
          </button>
          <button
            onClick={() => setViewMode("card")}
            className="p-1.5 cursor-pointer"
            style={{
              background: viewMode === "card" ? `${theme.accent}20` : "transparent",
              border: `1px solid ${viewMode === "card" ? theme.accent : theme.border}`,
              color: viewMode === "card" ? theme.accent : theme.dim,
              borderRadius: theme.card.borderRadius,
            }}
          >
            <LayoutGrid size={14} />
          </button>
          <button
            onClick={() => setViewMode("list")}
            className="p-1.5 cursor-pointer"
            style={{
              background: viewMode === "list" ? `${theme.accent}20` : "transparent",
              border: `1px solid ${viewMode === "list" ? theme.accent : theme.border}`,
              color: viewMode === "list" ? theme.accent : theme.dim,
              borderRadius: theme.card.borderRadius,
            }}
          >
            <List size={14} />
          </button>
        </div>
      </div>

      {/* Topics */}
      {loading ? (
        <div className="flex items-center justify-center gap-3 p-12" style={cardStyle}>
          <Loader2 size={20} className="animate-spin" style={{ color: theme.accent }} />
          <span style={{ color: theme.dim, fontFamily: theme.mono, fontSize: 12 }}>Loading topics...</span>
        </div>
      ) : topics.length === 0 ? (
        <div className="p-8 text-center" style={cardStyle}>
          <Search size={32} style={{ color: theme.muted }} className="mx-auto mb-3" />
          <p style={{ color: theme.dim, fontFamily: theme.mono, fontSize: 12 }}>
            No discovered topics yet. Run discovery on a franchise to find topics.
          </p>
        </div>
      ) : viewMode === "card" ? (
        <div className="grid grid-cols-2 gap-3">
          {topics.map((topic) => {
            const sources = parseSources(topic.sources_json);
            return (
              <div key={topic.id} className="flex flex-col" style={cardStyle}>
                <div className="p-4 flex-1">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <span
                      className="text-xs font-bold leading-snug"
                      style={{ color: theme.text, fontFamily: theme.font }}
                    >
                      {topic.title}
                    </span>
                    <span
                      className="shrink-0 w-7 h-7 flex items-center justify-center text-[11px] font-black"
                      style={{
                        background: `${tierColor(topic.score)}20`,
                        color: tierColor(topic.score),
                        borderRadius: "4px",
                        fontFamily: theme.mono,
                      }}
                    >
                      {tierLabel(topic.score)}
                    </span>
                  </div>

                  {topic.description && (
                    <p className="text-[11px] m-0 mb-2 line-clamp-2" style={{ color: theme.dim }}>
                      {topic.description}
                    </p>
                  )}

                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className="px-1.5 py-0.5 text-[10px] font-bold tracking-wider"
                      style={{
                        background: `${theme.accent}15`,
                        color: theme.accent,
                        borderRadius: "2px",
                        fontFamily: theme.mono,
                      }}
                    >
                      {categoryLabel(topic.category)}
                    </span>
                    <span className="text-[10px]" style={{ color: theme.muted, fontFamily: theme.mono }}>
                      Score: {topic.score.toFixed(1)}
                    </span>
                  </div>

                  {/* Source badges */}
                  <div className="flex items-center gap-1.5">
                    {sources.map((src, i) => (
                      <span
                        key={i}
                        className="flex items-center gap-0.5 text-[10px]"
                        style={{ color: theme.dim }}
                      >
                        {sourceIcon(src.type)}
                      </span>
                    ))}
                    {sources.length > 0 && (
                      <span className="text-[10px]" style={{ color: theme.muted, fontFamily: theme.mono }}>
                        {sources.length} source{sources.length !== 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div
                  className="flex border-t"
                  style={{ borderColor: theme.border }}
                >
                  <button
                    onClick={() => handleQueue(topic.id)}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 text-[11px] font-bold tracking-wider cursor-pointer"
                    style={{
                      background: "transparent",
                      border: "none",
                      color: theme.accent,
                      fontFamily: theme.mono,
                    }}
                  >
                    <ListTodo size={12} />
                    ADD TO QUEUE
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* List view */
        <div className="flex flex-col gap-1">
          {topics.map((topic) => {
            const sources = parseSources(topic.sources_json);
            return (
              <div
                key={topic.id}
                className="flex items-center gap-4 p-3"
                style={cardStyle}
              >
                {/* Tier badge */}
                <span
                  className="shrink-0 w-7 h-7 flex items-center justify-center text-[11px] font-black"
                  style={{
                    background: `${tierColor(topic.score)}20`,
                    color: tierColor(topic.score),
                    borderRadius: "4px",
                    fontFamily: theme.mono,
                  }}
                >
                  {tierLabel(topic.score)}
                </span>

                {/* Title & category */}
                <div className="flex-1 min-w-0">
                  <span className="text-xs font-bold truncate block" style={{ color: theme.text }}>
                    {topic.title}
                  </span>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[10px]" style={{ color: theme.dim, fontFamily: theme.mono }}>
                      {categoryLabel(topic.category)}
                    </span>
                    <span className="text-[10px]" style={{ color: theme.muted, fontFamily: theme.mono }}>
                      {topic.franchise_id}
                    </span>
                  </div>
                </div>

                {/* Sources */}
                <div className="flex items-center gap-1 shrink-0">
                  {sources.map((src, i) => (
                    <span key={i} style={{ color: theme.dim }}>{sourceIcon(src.type)}</span>
                  ))}
                </div>

                {/* Score */}
                <span className="text-xs shrink-0" style={{ color: theme.dim, fontFamily: theme.mono }}>
                  {topic.score.toFixed(1)}
                </span>

                {/* Queue button */}
                <button
                  onClick={() => handleQueue(topic.id)}
                  className="flex items-center gap-1 px-3 py-1.5 text-[10px] font-bold tracking-wider cursor-pointer shrink-0"
                  style={{
                    background: `${theme.accent}15`,
                    border: `1px solid ${theme.accent}`,
                    color: theme.accent,
                    fontFamily: theme.mono,
                    borderRadius: theme.card.borderRadius,
                  }}
                >
                  <ListTodo size={10} />
                  QUEUE
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Total count */}
      {!loading && topics.length > 0 && (
        <div className="mt-4 text-center">
          <span style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 10 }}>
            Showing {topics.length} of {total} topics
          </span>
        </div>
      )}
    </div>
  );
}

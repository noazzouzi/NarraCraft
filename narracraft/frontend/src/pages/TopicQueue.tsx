import { useState, useEffect, useCallback, useRef } from "react";
import { useTheme } from "@/components/ThemeProvider";
import { listTopics, queueTopic, skipTopic } from "@/api/client";
import {
  Loader2,
  GripVertical,
  ChevronRight,
  SkipForward,
  ListTodo,
  Play,
  CheckCircle2,
  Search,
} from "lucide-react";

interface Topic {
  id: string;
  franchise_id: string;
  title: string;
  description: string | null;
  category: string | null;
  score: number;
  status: string;
  sources_json: string | null;
  created_at: string;
}

type ColumnId = "discovered" | "queued" | "in_production" | "published";

interface Column {
  id: ColumnId;
  label: string;
  status: string;
  icon: typeof Search;
  color: string;
}

export default function TopicQueue() {
  const { theme } = useTheme();

  const [topics, setTopics] = useState<Record<ColumnId, Topic[]>>({
    discovered: [],
    queued: [],
    in_production: [],
    published: [],
  });
  const [loading, setLoading] = useState(true);
  const [dragging, setDragging] = useState<{ topicId: string; fromColumn: ColumnId } | null>(null);
  const [dragOver, setDragOver] = useState<ColumnId | null>(null);
  const dragCounter = useRef<Record<string, number>>({ discovered: 0, queued: 0, in_production: 0, published: 0 });

  const columns: Column[] = [
    { id: "discovered", label: "DISCOVERED", status: "discovered", icon: Search, color: theme.dim },
    { id: "queued", label: "QUEUED", status: "queued", icon: ListTodo, color: theme.accent },
    { id: "in_production", label: "IN PRODUCTION", status: "in_production", icon: Play, color: "#FF9800" },
    { id: "published", label: "PUBLISHED", status: "published", icon: CheckCircle2, color: theme.success },
  ];

  const fetchTopics = useCallback(async () => {
    setLoading(true);
    try {
      const [discovered, queued, inProd, published] = await Promise.all([
        listTopics({ status: "discovered", limit: "50" }),
        listTopics({ status: "queued", limit: "50" }),
        listTopics({ status: "in_production", limit: "50" }),
        listTopics({ status: "published", limit: "50" }),
      ]);
      setTopics({
        discovered: discovered.topics as unknown as Topic[],
        queued: queued.topics as unknown as Topic[],
        in_production: inProd.topics as unknown as Topic[],
        published: published.topics as unknown as Topic[],
      });
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTopics();
  }, [fetchTopics]);

  // Drag & drop handlers
  const handleDragStart = (topicId: string, fromColumn: ColumnId) => {
    setDragging({ topicId, fromColumn });
  };

  const handleDragEnter = (columnId: ColumnId) => {
    dragCounter.current[columnId]++;
    setDragOver(columnId);
  };

  const handleDragLeave = (columnId: ColumnId) => {
    dragCounter.current[columnId]--;
    if (dragCounter.current[columnId] <= 0) {
      dragCounter.current[columnId] = 0;
      if (dragOver === columnId) setDragOver(null);
    }
  };

  const handleDrop = async (toColumn: ColumnId) => {
    setDragOver(null);
    Object.keys(dragCounter.current).forEach((k) => { dragCounter.current[k] = 0; });

    if (!dragging) return;
    const { topicId, fromColumn } = dragging;
    setDragging(null);

    if (fromColumn === toColumn) return;

    // Only allow forward movement or skip
    const columnOrder: ColumnId[] = ["discovered", "queued", "in_production", "published"];
    const fromIdx = columnOrder.indexOf(fromColumn);
    const toIdx = columnOrder.indexOf(toColumn);

    // Allow discovered -> queued (queue action)
    // Other transitions will be handled by the pipeline
    if (fromColumn === "discovered" && toColumn === "queued") {
      // Optimistic update
      const topic = topics[fromColumn].find((t) => t.id === topicId);
      if (!topic) return;
      setTopics((prev) => ({
        ...prev,
        [fromColumn]: prev[fromColumn].filter((t) => t.id !== topicId),
        [toColumn]: [...prev[toColumn], { ...topic, status: "queued" }],
      }));
      try {
        await queueTopic(topicId);
      } catch {
        // Revert on failure
        fetchTopics();
      }
    } else if (toIdx < fromIdx) {
      // Don't allow backward movement
    }
  };

  // Quick action buttons
  const handleQuickQueue = async (topicId: string) => {
    const topic = topics.discovered.find((t) => t.id === topicId);
    if (!topic) return;
    setTopics((prev) => ({
      ...prev,
      discovered: prev.discovered.filter((t) => t.id !== topicId),
      queued: [...prev.queued, { ...topic, status: "queued" }],
    }));
    try {
      await queueTopic(topicId);
    } catch {
      fetchTopics();
    }
  };

  const handleQuickSkip = async (topicId: string) => {
    setTopics((prev) => ({
      ...prev,
      discovered: prev.discovered.filter((t) => t.id !== topicId),
    }));
    try {
      await skipTopic(topicId);
    } catch {
      fetchTopics();
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
      characters: "Chars",
      dev_design: "Dev",
      lore: "Lore",
      easter_egg: "Egg",
      cut_content: "Cut",
      memes: "Meme",
    };
    return cat ? map[cat] || cat : "";
  };

  const cardStyle = {
    background: theme.surface,
    border: `1px solid ${theme.border}`,
    borderRadius: theme.card.borderRadius,
    ...theme.card,
  };

  if (loading) {
    return (
      <div className="flex-1 p-5 flex items-center justify-center" style={{ fontFamily: theme.body }}>
        <div className="flex items-center gap-3">
          <Loader2 size={20} className="animate-spin" style={{ color: theme.accent }} />
          <span style={{ color: theme.dim, fontFamily: theme.mono, fontSize: 12 }}>Loading queue...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 p-5 overflow-x-auto" style={{ fontFamily: theme.body }}>
      <h1 className="m-0 mb-1" style={{ fontSize: 22, fontWeight: 700, fontFamily: theme.font, color: theme.text }}>
        Topic Queue
      </h1>
      <p className="mb-5" style={{ fontSize: 13, color: theme.dim }}>
        Drag topics between columns to manage their lifecycle.
      </p>

      <div className="grid grid-cols-4 gap-3" style={{ minHeight: "calc(100vh - 160px)" }}>
        {columns.map((col) => {
          const colTopics = topics[col.id];
          const Icon = col.icon;
          const isOver = dragOver === col.id;

          return (
            <div
              key={col.id}
              className="flex flex-col"
              onDragOver={(e) => e.preventDefault()}
              onDragEnter={() => handleDragEnter(col.id)}
              onDragLeave={() => handleDragLeave(col.id)}
              onDrop={() => handleDrop(col.id)}
            >
              {/* Column header */}
              <div
                className="flex items-center justify-between mb-3 pb-2"
                style={{ borderBottom: `2px solid ${col.color}40` }}
              >
                <div className="flex items-center gap-2">
                  <Icon size={14} style={{ color: col.color }} />
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      letterSpacing: "1.5px",
                      color: col.color,
                      fontFamily: theme.mono,
                    }}
                  >
                    {col.label}
                  </span>
                </div>
                <span
                  className="px-1.5 py-0.5 text-[10px] font-bold"
                  style={{
                    background: `${col.color}15`,
                    color: col.color,
                    borderRadius: "3px",
                    fontFamily: theme.mono,
                  }}
                >
                  {colTopics.length}
                </span>
              </div>

              {/* Drop zone */}
              <div
                className="flex-1 flex flex-col gap-2 p-2 transition-colors"
                style={{
                  background: isOver ? `${col.color}10` : "transparent",
                  border: `1px dashed ${isOver ? col.color : theme.border}`,
                  borderRadius: theme.card.borderRadius,
                  minHeight: 200,
                }}
              >
                {colTopics.length === 0 ? (
                  <div className="flex-1 flex items-center justify-center">
                    <p style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 10 }}>
                      {col.id === "discovered" ? "Run discovery to find topics" : "Drop topics here"}
                    </p>
                  </div>
                ) : (
                  colTopics.map((topic) => (
                    <div
                      key={topic.id}
                      draggable
                      onDragStart={() => handleDragStart(topic.id, col.id)}
                      onDragEnd={() => { setDragging(null); setDragOver(null); }}
                      className="cursor-grab active:cursor-grabbing"
                      style={{
                        ...cardStyle,
                        opacity: dragging?.topicId === topic.id ? 0.4 : 1,
                      }}
                    >
                      <div className="p-3">
                        <div className="flex items-start gap-2">
                          <GripVertical size={12} style={{ color: theme.muted, marginTop: 2 }} className="shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5 mb-1">
                              <span
                                className="w-5 h-5 flex items-center justify-center text-[9px] font-black shrink-0"
                                style={{
                                  background: `${tierColor(topic.score)}20`,
                                  color: tierColor(topic.score),
                                  borderRadius: "3px",
                                  fontFamily: theme.mono,
                                }}
                              >
                                {tierLabel(topic.score)}
                              </span>
                              <span
                                className="text-[11px] font-bold leading-snug line-clamp-2"
                                style={{ color: theme.text }}
                              >
                                {topic.title}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 mt-1">
                              {topic.category && (
                                <span
                                  className="text-[9px] px-1 py-0.5"
                                  style={{
                                    background: `${theme.accent}10`,
                                    color: theme.dim,
                                    borderRadius: "2px",
                                    fontFamily: theme.mono,
                                  }}
                                >
                                  {categoryLabel(topic.category)}
                                </span>
                              )}
                              <span className="text-[9px]" style={{ color: theme.muted, fontFamily: theme.mono }}>
                                {topic.franchise_id}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Quick actions for discovered column */}
                        {col.id === "discovered" && (
                          <div className="flex gap-1.5 mt-2 ml-5">
                            <button
                              onClick={(e) => { e.stopPropagation(); handleQuickQueue(topic.id); }}
                              className="flex items-center gap-1 px-2 py-1 text-[9px] font-bold tracking-wider cursor-pointer"
                              style={{
                                background: `${theme.accent}15`,
                                border: `1px solid ${theme.accent}40`,
                                color: theme.accent,
                                fontFamily: theme.mono,
                                borderRadius: theme.card.borderRadius,
                              }}
                            >
                              <ChevronRight size={10} />
                              QUEUE
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleQuickSkip(topic.id); }}
                              className="flex items-center gap-1 px-2 py-1 text-[9px] font-bold tracking-wider cursor-pointer"
                              style={{
                                background: "transparent",
                                border: `1px solid ${theme.border}`,
                                color: theme.dim,
                                fontFamily: theme.mono,
                                borderRadius: theme.card.borderRadius,
                              }}
                            >
                              <SkipForward size={10} />
                              SKIP
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

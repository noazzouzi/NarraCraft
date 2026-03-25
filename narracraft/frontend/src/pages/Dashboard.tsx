import { useEffect, useState, useCallback } from "react";
import { useTheme } from "@/components/ThemeProvider";
import {
  getDashboardAnalytics,
  getInsights,
  getAllFranchiseAnalytics,
  listTopics,
  pipelineStatus,
  type DashboardAnalytics,
  type Insight,
  type FranchiseAnalytics,
} from "@/api/client";

interface QueueItem {
  franchise_id: string;
  title: string;
  score: number;
  narrator_archetype?: string;
}

interface LogItem {
  t: string;
  l: string;
  d: string;
}

export default function Dashboard() {
  const { theme } = useTheme();
  const h = theme;
  const isPx = h.font.includes("Press Start");
  const fs = (n: number) => (isPx ? Math.max(n - 4, 6) : n);

  const [dashboard, setDashboard] = useState<DashboardAnalytics | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [franchises, setFranchises] = useState<FranchiseAnalytics[]>([]);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [logs, setLogs] = useState<LogItem[]>([]);

  const load = useCallback(async () => {
    const [dash, ins, fr, q, pipe] = await Promise.allSettled([
      getDashboardAnalytics(),
      getInsights(),
      getAllFranchiseAnalytics(),
      listTopics({ status: "queued", limit: "5" }),
      pipelineStatus(),
    ]);

    if (dash.status === "fulfilled") setDashboard(dash.value);
    if (ins.status === "fulfilled") setInsights(ins.value.insights || []);
    if (fr.status === "fulfilled") setFranchises(fr.value.franchises || []);

    if (q.status === "fulfilled") {
      setQueue(
        (q.value.topics || []).map((t: Record<string, unknown>) => ({
          franchise_id: String(t.franchise_id || ""),
          title: String(t.title || ""),
          score: Number(t.score || 0),
          narrator_archetype: t.narrator_archetype ? String(t.narrator_archetype) : undefined,
        })),
      );
    }

    if (pipe.status === "fulfilled") {
      const runs = (pipe.value.runs || []).slice(0, 6);
      setLogs(
        runs.map((r: Record<string, unknown>) => ({
          t: r.started_at ? new Date(String(r.started_at)).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "",
          l: String(r.status || "").toUpperCase(),
          d: String(r.topic_id || ""),
        })),
      );
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, [load]);

  // Use real data or fallbacks
  const stats = dashboard
    ? [
        { l: "PUBLISHED", v: String(dashboard.total_videos), s: `${dashboard.videos_this_week} this week` },
        {
          l: "VIEWS",
          v: dashboard.total_views >= 1000 ? `${(dashboard.total_views / 1000).toFixed(1)}K` : String(dashboard.total_views),
          s: dashboard.views_change_pct ? `${dashboard.views_change_pct > 0 ? "+" : ""}${dashboard.views_change_pct}%` : "—",
        },
        { l: "SUBS", v: `+${dashboard.total_subscribers_gained}`, s: "gained" },
        { l: "QUEUE", v: String(dashboard.queued_topics), s: "topics ready" },
      ]
    : [
        { l: "PUBLISHED", v: "—", s: "loading" },
        { l: "VIEWS", v: "—", s: "loading" },
        { l: "SUBS", v: "—", s: "loading" },
        { l: "QUEUE", v: "—", s: "loading" },
      ];

  // Franchise performance with real data
  const maxViews = Math.max(...franchises.map((f) => f.total_views), 1);

  return (
    <div className="flex-1 p-5" style={{ fontFamily: h.body }}>
      {/* Header */}
      <div
        className="flex justify-between items-end mb-5 pb-3"
        style={{ borderBottom: `1px solid ${h.border}` }}
      >
        <div>
          <div
            style={{
              fontSize: fs(9),
              fontWeight: 700,
              letterSpacing: "2.5px",
              color: h.muted,
              fontFamily: h.mono,
              marginBottom: 4,
            }}
          >
            NARRACRAFT
          </div>
          <h1
            className="m-0"
            style={{
              fontSize: fs(22),
              fontWeight: 700,
              fontFamily: h.font,
              letterSpacing: "-0.3px",
              color: h.text,
            }}
          >
            Mission Control
          </h1>
        </div>
        <button
          style={{
            padding: "9px 20px",
            border: `1px solid ${h.accent}`,
            background: `${h.accent}15`,
            color: h.accent,
            cursor: "pointer",
            fontSize: fs(11),
            fontWeight: 700,
            letterSpacing: "1.5px",
            fontFamily: h.mono,
            boxShadow: `0 0 14px ${h.accent}20`,
            borderRadius: h.card.borderRadius,
          }}
          onClick={() => (window.location.hash = "#/pipeline")}
        >
          {"\u25B6"} {h.f.deploy}
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-2.5 mb-4">
        {stats.map((x, i) => (
          <div
            key={i}
            className="p-3.5"
            style={{
              background: h.surface,
              border: `1px solid ${h.border}`,
              borderRadius: h.card.borderRadius,
              ...(h.card.borderTop ? { borderTop: h.card.borderTop } : {}),
              ...(h.card.borderLeft ? { borderLeft: h.card.borderLeft } : {}),
              ...(h.card.borderRight ? { borderRight: h.card.borderRight } : {}),
              ...(h.card.borderBottom ? { borderBottom: h.card.borderBottom } : {}),
              ...(h.card.boxShadow ? { boxShadow: h.card.boxShadow } : {}),
            }}
          >
            <div
              style={{
                fontSize: fs(8),
                fontWeight: 700,
                letterSpacing: "1.5px",
                color: h.muted,
                fontFamily: h.mono,
                marginBottom: 5,
              }}
            >
              {x.l}
            </div>
            <div
              style={{ fontSize: fs(24), fontWeight: 800, fontFamily: h.font, lineHeight: 1, color: h.text }}
            >
              {x.v}
            </div>
            <div style={{ fontSize: fs(9), color: h.accent, marginTop: 4, fontFamily: h.mono }}>
              {x.s}
            </div>
          </div>
        ))}
      </div>

      {/* Log + Queue row */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        {/* Activity Log */}
        <div
          className="p-4"
          style={{
            background: h.surface,
            border: `1px solid ${h.border}`,
            borderRadius: h.card.borderRadius,
            ...(h.card.boxShadow ? { boxShadow: h.card.boxShadow } : {}),
          }}
        >
          <div
            style={{
              fontSize: fs(10),
              fontWeight: 700,
              letterSpacing: "1.5px",
              color: h.dim,
              fontFamily: h.mono,
              marginBottom: 10,
            }}
          >
            {h.f.log.toUpperCase()}
          </div>
          {logs.length > 0 ? (
            logs.map((x, i) => (
              <div
                key={i}
                className="flex items-center gap-2 py-1"
                style={{
                  borderBottom: i < logs.length - 1 ? `1px solid ${h.border}` : "none",
                }}
              >
                <span style={{ fontSize: fs(9), color: h.muted, fontFamily: h.mono, width: 32 }}>
                  {x.t}
                </span>
                <span
                  style={{
                    fontSize: fs(7),
                    fontWeight: 700,
                    letterSpacing: "0.8px",
                    padding: "1px 5px",
                    color: h.accent,
                    background: `${h.accent}12`,
                    fontFamily: h.mono,
                  }}
                >
                  {x.l}
                </span>
                <span
                  className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap"
                  style={{ fontSize: fs(10), color: h.dim }}
                >
                  {x.d}
                </span>
              </div>
            ))
          ) : (
            <p style={{ fontSize: fs(10), color: h.muted, fontFamily: h.mono }}>No pipeline runs yet.</p>
          )}
        </div>

        {/* Queue Preview */}
        <div
          className="p-4"
          style={{
            background: h.surface,
            border: `1px solid ${h.border}`,
            borderRadius: h.card.borderRadius,
            ...(h.card.boxShadow ? { boxShadow: h.card.boxShadow } : {}),
          }}
        >
          <div
            style={{
              fontSize: fs(10),
              fontWeight: 700,
              letterSpacing: "1.5px",
              color: h.dim,
              fontFamily: h.mono,
              marginBottom: 10,
            }}
          >
            {h.f.queue.toUpperCase()}
          </div>
          {queue.length > 0 ? (
            queue.map((x, i) => (
              <div
                key={i}
                className="flex items-center gap-2 py-1.5 px-1"
                style={{
                  borderBottom: i < queue.length - 1 ? `1px solid ${h.border}` : "none",
                }}
              >
                <span
                  style={{ fontSize: fs(10), fontWeight: 900, color: h.accent, fontFamily: h.mono, width: 24 }}
                >
                  {x.franchise_id.substring(0, 3).toUpperCase()}
                </span>
                <div className="flex-1 min-w-0">
                  <div
                    className="overflow-hidden text-ellipsis whitespace-nowrap"
                    style={{ fontSize: fs(11), fontWeight: 600, color: h.text }}
                  >
                    {x.title}
                  </div>
                  <div style={{ fontSize: fs(8), color: h.muted, fontFamily: h.mono }}>
                    {x.narrator_archetype || "auto"} · {x.score.toFixed(1)}
                  </div>
                </div>
                <div
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: h.success,
                    boxShadow: `0 0 5px ${h.success}60`,
                  }}
                />
              </div>
            ))
          ) : (
            <p style={{ fontSize: fs(10), color: h.muted, fontFamily: h.mono }}>
              No queued topics. Discover and queue topics to get started.
            </p>
          )}
        </div>
      </div>

      {/* Franchise Performance */}
      <div
        className="p-4 mb-4"
        style={{
          background: h.surface,
          border: `1px solid ${h.border}`,
          borderRadius: h.card.borderRadius,
          ...(h.card.boxShadow ? { boxShadow: h.card.boxShadow } : {}),
        }}
      >
        <div
          style={{
            fontSize: fs(10),
            fontWeight: 700,
            letterSpacing: "1.5px",
            color: h.dim,
            fontFamily: h.mono,
            marginBottom: 10,
          }}
        >
          {h.f.perf.toUpperCase()}
        </div>
        {franchises.length > 0 ? (
          franchises.map((x, i) => (
            <div key={i} className="flex items-center gap-2.5 py-1.5">
              <span
                style={{ fontSize: fs(10), fontWeight: 800, color: h.accent, fontFamily: h.mono, width: 28 }}
              >
                {x.name.substring(0, 3).toUpperCase()}
              </span>
              <span style={{ fontSize: fs(11), width: 100, fontWeight: 600, color: h.text }}>{x.name}</span>
              <div className="flex-1 h-1 overflow-hidden" style={{ background: h.border, borderRadius: 2 }}>
                <div
                  style={{
                    height: "100%",
                    width: `${(x.total_views / maxViews) * 100}%`,
                    background: `linear-gradient(90deg, ${h.accent}80, ${h.accent}30)`,
                    transition: "width 0.6s",
                  }}
                />
              </div>
              <span style={{ fontSize: fs(13), fontWeight: 800, width: 46, textAlign: "right", color: h.text }}>
                {x.total_views >= 1000 ? `${(x.total_views / 1000).toFixed(0)}K` : x.total_views}
              </span>
              <span
                style={{
                  fontSize: fs(8),
                  color: h.success,
                  width: 32,
                  fontFamily: h.mono,
                  textAlign: "right",
                }}
              >
                {x.video_count}v
              </span>
            </div>
          ))
        ) : (
          <p style={{ fontSize: fs(10), color: h.muted, fontFamily: h.mono }}>
            Franchise performance will appear after publishing videos.
          </p>
        )}
      </div>

      {/* Insights */}
      <div
        className="p-4"
        style={{
          background: h.surface,
          border: `1px solid ${h.border}`,
          borderRadius: h.card.borderRadius,
          ...(h.card.boxShadow ? { boxShadow: h.card.boxShadow } : {}),
        }}
      >
        <div
          style={{
            fontSize: fs(10),
            fontWeight: 700,
            letterSpacing: "1.5px",
            color: h.dim,
            fontFamily: h.mono,
            marginBottom: 10,
          }}
        >
          {h.f.intel.toUpperCase()}
        </div>
        <div className="grid grid-cols-2 gap-2">
          {insights.length > 0 ? (
            insights.slice(0, 4).map((x, i) => (
              <div
                key={i}
                className="p-2.5 px-3"
                style={{
                  background: `${h.accent}05`,
                  borderLeft: `2px solid ${h.accent}25`,
                }}
              >
                <div
                  style={{
                    fontSize: fs(7),
                    fontWeight: 700,
                    letterSpacing: "1.5px",
                    color: h.accent,
                    fontFamily: h.mono,
                    marginBottom: 3,
                  }}
                >
                  {x.tag}
                </div>
                <div style={{ fontSize: fs(10), color: h.dim, lineHeight: 1.55 }}>{x.text}</div>
              </div>
            ))
          ) : (
            <div className="col-span-2">
              <p style={{ fontSize: fs(10), color: h.muted, fontFamily: h.mono }}>
                Insights will generate after collecting analytics data from published videos.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

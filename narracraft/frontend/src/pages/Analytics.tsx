import { useEffect, useState, useCallback } from "react";
import { useTheme } from "@/components/ThemeProvider";
import {
  getDashboardAnalytics,
  getInsights,
  getAllFranchiseAnalytics,
  getVideoAnalyticsList,
  getDerivedScores,
  triggerAnalyticsCollection,
  triggerFeedbackLoop,
  refreshInsights,
  type DashboardAnalytics,
  type Insight,
  type FranchiseAnalytics,
  type VideoAnalytics,
  type ScoredVideo,
} from "@/api/client";

// ---------- tiny bar-chart component (no deps) ----------
function BarChart({
  data,
  labelKey,
  valueKey,
  accent,
  dim,
  mono,
  fs,
}: {
  data: Record<string, unknown>[];
  labelKey: string;
  valueKey: string;
  accent: string;
  dim: string;
  mono: string;
  fs: (n: number) => number;
}) {
  const max = Math.max(...data.map((d) => Number(d[valueKey]) || 0), 1);
  return (
    <div className="flex flex-col gap-1.5">
      {data.map((d, i) => {
        const val = Number(d[valueKey]) || 0;
        const pct = (val / max) * 100;
        return (
          <div key={i} className="flex items-center gap-2">
            <span
              className="shrink-0 overflow-hidden text-ellipsis whitespace-nowrap"
              style={{ width: 80, fontSize: fs(10), color: dim, fontFamily: mono }}
            >
              {String(d[labelKey] ?? "")}
            </span>
            <div className="flex-1 h-2 overflow-hidden" style={{ background: `${accent}15`, borderRadius: 2 }}>
              <div
                style={{
                  height: "100%",
                  width: `${pct}%`,
                  background: `linear-gradient(90deg, ${accent}90, ${accent}40)`,
                  transition: "width 0.5s",
                  borderRadius: 2,
                }}
              />
            </div>
            <span style={{ fontSize: fs(10), fontWeight: 700, color: dim, fontFamily: mono, width: 52, textAlign: "right" }}>
              {val >= 1000 ? `${(val / 1000).toFixed(1)}K` : val.toLocaleString()}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ---------- Tag badge ----------
function Tag({ label, accent, mono, fs }: { label: string; accent: string; mono: string; fs: (n: number) => number }) {
  return (
    <span
      style={{
        fontSize: fs(7),
        fontWeight: 700,
        letterSpacing: "1px",
        padding: "1px 6px",
        color: accent,
        background: `${accent}12`,
        fontFamily: mono,
        borderRadius: 2,
      }}
    >
      {label}
    </span>
  );
}

export default function Analytics() {
  const { theme } = useTheme();
  const h = theme;
  const isPx = h.font.includes("Press Start");
  const fs = (n: number) => (isPx ? Math.max(n - 4, 6) : n);

  // State
  const [dashboard, setDashboard] = useState<DashboardAnalytics | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [franchises, setFranchises] = useState<FranchiseAnalytics[]>([]);
  const [videos, setVideos] = useState<VideoAnalytics[]>([]);
  const [scores, setScores] = useState<ScoredVideo[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [tab, setTab] = useState<"overview" | "franchises" | "videos" | "scores">("overview");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [dash, ins, fr, vid, sc] = await Promise.allSettled([
        getDashboardAnalytics(),
        getInsights(),
        getAllFranchiseAnalytics(),
        getVideoAnalyticsList(),
        getDerivedScores(),
      ]);
      if (dash.status === "fulfilled") setDashboard(dash.value);
      if (ins.status === "fulfilled") setInsights(ins.value.insights);
      if (fr.status === "fulfilled") setFranchises(fr.value.franchises);
      if (vid.status === "fulfilled") setVideos(vid.value.videos);
      if (sc.status === "fulfilled") setScores(sc.value.videos);
    } catch {
      /* noop */
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCollect = async () => {
    setActionLoading("collect");
    try {
      await triggerAnalyticsCollection();
      await load();
    } finally {
      setActionLoading(null);
    }
  };

  const handleFeedback = async () => {
    setActionLoading("feedback");
    try {
      await triggerFeedbackLoop();
      await load();
    } finally {
      setActionLoading(null);
    }
  };

  const handleRefreshInsights = async () => {
    setActionLoading("insights");
    try {
      const r = await refreshInsights();
      setInsights(r.insights);
    } finally {
      setActionLoading(null);
    }
  };

  // Shared card style
  const card = {
    background: h.surface,
    border: `1px solid ${h.border}`,
    borderRadius: h.card.borderRadius,
    ...(h.card.boxShadow ? { boxShadow: h.card.boxShadow } : {}),
  };

  const sectionTitle = (text: string) => (
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
      {text}
    </div>
  );

  const btnStyle = (active?: boolean) => ({
    padding: "6px 14px",
    border: `1px solid ${active ? h.accent : h.border}`,
    background: active ? `${h.accent}15` : "transparent",
    color: active ? h.accent : h.dim,
    cursor: "pointer" as const,
    fontSize: fs(9),
    fontWeight: 700,
    letterSpacing: "1px",
    fontFamily: h.mono,
    borderRadius: h.card.borderRadius,
  });

  return (
    <div className="flex-1 p-5" style={{ fontFamily: h.body }}>
      {/* Header */}
      <div className="flex justify-between items-end mb-5 pb-3" style={{ borderBottom: `1px solid ${h.border}` }}>
        <div>
          <h1 className="m-0" style={{ fontSize: fs(22), fontWeight: 700, fontFamily: h.font, color: h.text }}>
            Analytics
          </h1>
          <p className="m-0 mt-1" style={{ fontSize: fs(11), color: h.dim }}>
            Performance charts, franchise comparison, narrator analysis, and auto-insights.
          </p>
        </div>
        <div className="flex gap-2">
          <button style={btnStyle()} onClick={handleCollect} disabled={!!actionLoading}>
            {actionLoading === "collect" ? "..." : "COLLECT"}
          </button>
          <button style={btnStyle()} onClick={handleFeedback} disabled={!!actionLoading}>
            {actionLoading === "feedback" ? "..." : "FEEDBACK"}
          </button>
          <button style={btnStyle()} onClick={handleRefreshInsights} disabled={!!actionLoading}>
            {actionLoading === "insights" ? "..." : "INSIGHTS"}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4">
        {(["overview", "franchises", "videos", "scores"] as const).map((t) => (
          <button key={t} style={btnStyle(tab === t)} onClick={() => setTab(t)}>
            {t.toUpperCase()}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="p-8 text-center" style={card}>
          <p style={{ color: h.muted, fontFamily: h.mono, fontSize: fs(11) }}>Loading analytics...</p>
        </div>
      ) : tab === "overview" ? (
        <OverviewTab
          dashboard={dashboard}
          insights={insights}
          franchises={franchises}
          h={h}
          fs={fs}
          card={card}
          sectionTitle={sectionTitle}
        />
      ) : tab === "franchises" ? (
        <FranchisesTab franchises={franchises} h={h} fs={fs} card={card} sectionTitle={sectionTitle} />
      ) : tab === "videos" ? (
        <VideosTab videos={videos} h={h} fs={fs} card={card} sectionTitle={sectionTitle} />
      ) : (
        <ScoresTab scores={scores} h={h} fs={fs} card={card} sectionTitle={sectionTitle} />
      )}
    </div>
  );
}

// ---------- Overview Tab ----------
function OverviewTab({
  dashboard,
  insights,
  franchises,
  h,
  fs,
  card,
  sectionTitle,
}: {
  dashboard: DashboardAnalytics | null;
  insights: Insight[];
  franchises: FranchiseAnalytics[];
  h: ReturnType<typeof useTheme>["theme"];
  fs: (n: number) => number;
  card: React.CSSProperties;
  sectionTitle: (t: string) => React.ReactNode;
}) {
  // Stat cards
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
    : [];

  return (
    <>
      {/* Stats row */}
      {stats.length > 0 && (
        <div className="grid grid-cols-4 gap-2.5 mb-4">
          {stats.map((x, i) => (
            <div key={i} className="p-3.5" style={card}>
              <div style={{ fontSize: fs(8), fontWeight: 700, letterSpacing: "1.5px", color: h.muted, fontFamily: h.mono, marginBottom: 5 }}>
                {x.l}
              </div>
              <div style={{ fontSize: fs(24), fontWeight: 800, fontFamily: h.font, lineHeight: 1, color: h.text }}>{x.v}</div>
              <div style={{ fontSize: fs(9), color: h.accent, marginTop: 4, fontFamily: h.mono }}>{x.s}</div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 mb-4">
        {/* Franchise Performance */}
        <div className="p-4" style={card}>
          {sectionTitle("FRANCHISE PERFORMANCE")}
          {franchises.length > 0 ? (
            <BarChart data={franchises} labelKey="name" valueKey="total_views" accent={h.accent} dim={h.dim} mono={h.mono} fs={fs} />
          ) : (
            <p style={{ color: h.muted, fontFamily: h.mono, fontSize: fs(10) }}>No published videos yet.</p>
          )}
        </div>

        {/* Insights */}
        <div className="p-4" style={card}>
          {sectionTitle(h.f.intel.toUpperCase())}
          {insights.length > 0 ? (
            <div className="flex flex-col gap-2">
              {insights.slice(0, 6).map((ins, i) => (
                <div
                  key={i}
                  className="p-2.5 px-3"
                  style={{ background: `${h.accent}05`, borderLeft: `2px solid ${h.accent}25` }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Tag label={ins.tag} accent={h.accent} mono={h.mono} fs={fs} />
                    {ins.priority === "high" && (
                      <span style={{ fontSize: fs(7), color: h.danger, fontFamily: h.mono }}>HIGH</span>
                    )}
                  </div>
                  <div style={{ fontSize: fs(10), color: h.dim, lineHeight: 1.55 }}>{ins.text}</div>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: h.muted, fontFamily: h.mono, fontSize: fs(10) }}>
              Insights generate after publishing videos and collecting analytics.
            </p>
          )}
        </div>
      </div>

      {/* Retention by Franchise */}
      {franchises.length > 0 && (
        <div className="p-4" style={card}>
          {sectionTitle("RETENTION BY FRANCHISE")}
          <div className="flex flex-col gap-1.5">
            {franchises.map((f, i) => (
              <div key={i} className="flex items-center gap-2.5 py-1">
                <span style={{ fontSize: fs(10), fontWeight: 800, color: h.accent, fontFamily: h.mono, width: 80 }}>
                  {f.name}
                </span>
                <div className="flex-1 h-2 overflow-hidden" style={{ background: `${h.border}`, borderRadius: 2 }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${Math.min(f.avg_retention, 100)}%`,
                      background:
                        f.avg_retention >= 60
                          ? h.success
                          : f.avg_retention >= 40
                            ? h.accent
                            : h.danger,
                      transition: "width 0.5s",
                      borderRadius: 2,
                    }}
                  />
                </div>
                <span style={{ fontSize: fs(10), fontWeight: 700, color: h.dim, fontFamily: h.mono, width: 40, textAlign: "right" }}>
                  {f.avg_retention.toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

// ---------- Franchises Tab ----------
function FranchisesTab({
  franchises,
  h,
  fs,
  card,
  sectionTitle,
}: {
  franchises: FranchiseAnalytics[];
  h: ReturnType<typeof useTheme>["theme"];
  fs: (n: number) => number;
  card: React.CSSProperties;
  sectionTitle: (t: string) => React.ReactNode;
}) {
  if (franchises.length === 0) {
    return (
      <div className="p-8 text-center" style={card}>
        <p style={{ color: h.muted, fontFamily: h.mono, fontSize: fs(11) }}>
          No franchise analytics data yet. Publish videos to see performance data.
        </p>
      </div>
    );
  }

  const maxViews = Math.max(...franchises.map((f) => f.total_views), 1);

  return (
    <div className="flex flex-col gap-3">
      {franchises.map((f, i) => (
        <div key={i} className="p-4" style={card}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <span style={{ fontSize: fs(14), fontWeight: 800, fontFamily: h.font, color: h.text }}>{f.name}</span>
              <span style={{ fontSize: fs(8), color: h.muted, fontFamily: h.mono }}>
                {f.category} · {f.video_count} videos
              </span>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div style={{ fontSize: fs(8), color: h.muted, fontFamily: h.mono, letterSpacing: "1px" }}>WEIGHT</div>
                <div style={{ fontSize: fs(14), fontWeight: 700, color: h.accent, fontFamily: h.mono }}>{f.weight.toFixed(2)}x</div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-3 mb-3">
            {[
              { l: "Total Views", v: f.total_views >= 1000 ? `${(f.total_views / 1000).toFixed(1)}K` : f.total_views },
              { l: "Avg Views", v: f.avg_views >= 1000 ? `${(f.avg_views / 1000).toFixed(1)}K` : Math.round(f.avg_views) },
              { l: "Retention", v: `${f.avg_retention.toFixed(1)}%` },
              { l: "Subs Gained", v: `+${f.subs_gained}` },
            ].map((m, j) => (
              <div key={j}>
                <div style={{ fontSize: fs(8), color: h.muted, fontFamily: h.mono, letterSpacing: "1px", marginBottom: 2 }}>{m.l}</div>
                <div style={{ fontSize: fs(16), fontWeight: 700, fontFamily: h.font, color: h.text }}>{m.v}</div>
              </div>
            ))}
          </div>

          {/* View share bar */}
          <div className="h-1.5 overflow-hidden" style={{ background: h.border, borderRadius: 2 }}>
            <div
              style={{
                height: "100%",
                width: `${(f.total_views / maxViews) * 100}%`,
                background: `linear-gradient(90deg, ${h.accent}90, ${h.accent}30)`,
                transition: "width 0.5s",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------- Videos Tab ----------
function VideosTab({
  videos,
  h,
  fs,
  card,
  sectionTitle,
}: {
  videos: VideoAnalytics[];
  h: ReturnType<typeof useTheme>["theme"];
  fs: (n: number) => number;
  card: React.CSSProperties;
  sectionTitle: (t: string) => React.ReactNode;
}) {
  if (videos.length === 0) {
    return (
      <div className="p-8 text-center" style={card}>
        <p style={{ color: h.muted, fontFamily: h.mono, fontSize: fs(11) }}>
          No published videos yet. Run the pipeline to start generating content.
        </p>
      </div>
    );
  }

  return (
    <div className="p-4" style={card}>
      {sectionTitle("VIDEO PERFORMANCE")}
      <div className="overflow-x-auto">
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${h.border}` }}>
              {["Title", "Franchise", "Narrator", "Views", "Likes", "Retention", "Published"].map((col) => (
                <th
                  key={col}
                  style={{
                    textAlign: "left",
                    padding: "6px 8px",
                    fontSize: fs(8),
                    fontWeight: 700,
                    letterSpacing: "1px",
                    color: h.muted,
                    fontFamily: h.mono,
                  }}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {videos.map((v, i) => (
              <tr key={i} style={{ borderBottom: `1px solid ${h.border}` }}>
                <td style={{ padding: "8px", fontSize: fs(11), color: h.text, maxWidth: 200 }}>
                  <div className="overflow-hidden text-ellipsis whitespace-nowrap">{v.title}</div>
                </td>
                <td style={{ padding: "8px", fontSize: fs(10), color: h.dim, fontFamily: h.mono }}>{v.franchise_id}</td>
                <td style={{ padding: "8px", fontSize: fs(10), color: h.dim }}>{v.narrator_archetype || "—"}</td>
                <td style={{ padding: "8px", fontSize: fs(11), fontWeight: 700, color: h.text, fontFamily: h.mono }}>
                  {(v.views ?? 0) >= 1000 ? `${((v.views ?? 0) / 1000).toFixed(1)}K` : v.views ?? 0}
                </td>
                <td style={{ padding: "8px", fontSize: fs(10), color: h.dim, fontFamily: h.mono }}>{v.likes ?? 0}</td>
                <td style={{ padding: "8px" }}>
                  <span
                    style={{
                      fontSize: fs(10),
                      fontWeight: 700,
                      fontFamily: h.mono,
                      color: (v.avg_view_duration_pct ?? 0) >= 60 ? h.success : (v.avg_view_duration_pct ?? 0) >= 40 ? h.accent : h.danger,
                    }}
                  >
                    {v.avg_view_duration_pct != null ? `${v.avg_view_duration_pct.toFixed(1)}%` : "—"}
                  </span>
                </td>
                <td style={{ padding: "8px", fontSize: fs(9), color: h.muted, fontFamily: h.mono }}>
                  {v.published_at ? new Date(v.published_at).toLocaleDateString() : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------- Scores Tab ----------
function ScoresTab({
  scores,
  h,
  fs,
  card,
  sectionTitle,
}: {
  scores: ScoredVideo[];
  h: ReturnType<typeof useTheme>["theme"];
  fs: (n: number) => number;
  card: React.CSSProperties;
  sectionTitle: (t: string) => React.ReactNode;
}) {
  const [sortBy, setSortBy] = useState<"engagement_score" | "growth_score" | "virality_score" | "retention_score">("engagement_score");

  const sorted = [...scores].sort((a, b) => (b[sortBy] ?? 0) - (a[sortBy] ?? 0));

  if (scores.length === 0) {
    return (
      <div className="p-8 text-center" style={card}>
        <p style={{ color: h.muted, fontFamily: h.mono, fontSize: fs(11) }}>
          Derived scores require at least 7-day analytics snapshots.
        </p>
      </div>
    );
  }

  const scoreCols = [
    { key: "engagement_score" as const, label: "ENGAGE" },
    { key: "growth_score" as const, label: "GROWTH" },
    { key: "virality_score" as const, label: "VIRAL" },
    { key: "retention_score" as const, label: "RETAIN" },
  ];

  return (
    <div className="p-4" style={card}>
      <div className="flex items-center justify-between mb-3">
        {sectionTitle("DERIVED SCORES")}
        <div className="flex gap-1">
          {scoreCols.map((c) => (
            <button
              key={c.key}
              onClick={() => setSortBy(c.key)}
              style={{
                padding: "3px 8px",
                fontSize: fs(7),
                fontWeight: 700,
                letterSpacing: "1px",
                fontFamily: h.mono,
                border: `1px solid ${sortBy === c.key ? h.accent : h.border}`,
                background: sortBy === c.key ? `${h.accent}15` : "transparent",
                color: sortBy === c.key ? h.accent : h.muted,
                cursor: "pointer",
                borderRadius: h.card.borderRadius,
              }}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        {sorted.map((v, i) => (
          <div
            key={v.id}
            className="flex items-center gap-3 p-2.5 px-3"
            style={{
              background: i === 0 ? `${h.accent}08` : "transparent",
              borderBottom: `1px solid ${h.border}`,
            }}
          >
            <span style={{ fontSize: fs(12), fontWeight: 800, color: h.muted, fontFamily: h.mono, width: 20 }}>
              {i + 1}
            </span>
            <div className="flex-1 min-w-0">
              <div className="overflow-hidden text-ellipsis whitespace-nowrap" style={{ fontSize: fs(11), fontWeight: 600, color: h.text }}>
                {v.title}
              </div>
              <div style={{ fontSize: fs(8), color: h.muted, fontFamily: h.mono }}>
                {v.franchise_id} · {v.narrator_archetype || "—"} · {v.views.toLocaleString()} views
              </div>
            </div>
            {scoreCols.map((c) => (
              <div key={c.key} className="text-center" style={{ width: 56 }}>
                <div style={{ fontSize: fs(7), color: h.muted, fontFamily: h.mono, letterSpacing: "0.5px" }}>{c.label}</div>
                <div
                  style={{
                    fontSize: fs(11),
                    fontWeight: 700,
                    fontFamily: h.mono,
                    color: c.key === sortBy ? h.accent : h.dim,
                  }}
                >
                  {v[c.key] < 1 ? v[c.key].toFixed(3) : v[c.key].toFixed(1)}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Typed API client for all NarraCraft backend endpoints.
 */

const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// --- Onboarding ---
export interface SearchResult {
  source: string;
  title: string;
  url?: string;
  summary?: string;
  image_url?: string;
  wiki_slug?: string;
  igdb_id?: number;
  mal_id?: number;
  anilist_id?: number;
  genres?: string[];
  score?: number;
  [key: string]: unknown;
}
export const searchFranchise = (q: string, category?: string) => {
  const params = new URLSearchParams({ q });
  if (category) params.set("category", category);
  return request<{ query: string; results: SearchResult[]; total: number }>(
    `/onboarding/search?${params}`,
  );
};

export interface CharacterResult {
  source: string;
  name: string;
  description?: string;
  image_urls?: string[];
  role?: string;
  [key: string]: unknown;
}
export const discoverCharacters = (params: {
  franchise_id: string;
  wiki_slug?: string;
  mal_id?: number;
  anilist_id?: number;
  igdb_id?: number;
}) => {
  const qs = new URLSearchParams();
  qs.set("franchise_id", params.franchise_id);
  if (params.wiki_slug) qs.set("wiki_slug", params.wiki_slug);
  if (params.mal_id) qs.set("mal_id", String(params.mal_id));
  if (params.anilist_id) qs.set("anilist_id", String(params.anilist_id));
  if (params.igdb_id) qs.set("igdb_id", String(params.igdb_id));
  return request<{ franchise_id: string; characters: CharacterResult[]; total: number }>(
    `/onboarding/characters?${qs}`,
  );
};

export const discoverLocations = (franchise_id: string, wiki_slug?: string) => {
  const qs = new URLSearchParams({ franchise_id });
  if (wiki_slug) qs.set("wiki_slug", wiki_slug);
  return request<{ franchise_id: string; locations: { name: string; description: string; image_urls: string[]; page_url: string }[]; total: number }>(
    `/onboarding/locations?${qs}`,
  );
};

export const searchImages = (q: string, limit = 20) =>
  request<{ query: string; images: { url: string; thumbnail_url: string; title: string; source_url: string }[] }>(
    `/onboarding/images?q=${encodeURIComponent(q)}&limit=${limit}`,
  );

export const generateBible = (data: { character_name: string; wiki_summary?: string; infobox?: Record<string, string> }) =>
  request<{ archetype_id: string; visual_description: string; character_bible: Record<string, string>; source_character_name: string }>(
    "/onboarding/generate-bible",
    { method: "POST", body: JSON.stringify(data) },
  );

export const saveFranchise = (data: {
  id: string;
  name: string;
  franchise_group: string;
  category: string;
  characters?: Record<string, unknown>[];
  environments?: Record<string, unknown>[];
  topic_seeds?: string[];
}) =>
  request<{ status: string; franchise_id: string }>("/onboarding/save", {
    method: "POST",
    body: JSON.stringify(data),
  });

// --- Topic Discovery ---
export const discoverTopics = (data: {
  franchise_id: string;
  sources?: string[];
}) =>
  request<{
    franchise_id: string;
    raw_count: number;
    deduped_count: number;
    discovered: number;
    errors: string[] | null;
    top_topics: { title: string; score: number; tier: string; sources: number; confidence: string; category: string }[];
  }>("/topics/discover", { method: "POST", body: JSON.stringify(data) });

// --- Health ---
export const health = () => request<{ status: string; version: string }>("/health");

// --- Config ---
export interface ConfigSummary {
  channel_name: string;
  voice_provider: string;
  franchises: {
    id: string;
    name: string;
    category: string;
    active: boolean;
    character_count: number;
    topic_seed_count: number;
  }[];
  pipeline: { videos_per_day: number; videos_per_week: number };
}
export const getConfig = () => request<ConfigSummary>("/config");

// --- Settings ---
export interface SettingsResponse {
  settings: Record<string, string>;
}
export const getSettings = () => request<SettingsResponse>("/settings");
export const updateSettings = (updates: Record<string, string>) =>
  request<SettingsResponse>("/settings", {
    method: "PUT",
    body: JSON.stringify(updates),
  });

// --- Topics ---
export interface TopicListResponse {
  topics: Record<string, unknown>[];
  total: number;
}
export const listTopics = (params?: Record<string, string>) => {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return request<TopicListResponse>(`/topics${qs}`);
};
export const queueTopic = (id: string) =>
  request(`/topics/${id}/queue`, { method: "PUT" });
export const skipTopic = (id: string) =>
  request(`/topics/${id}/skip`, { method: "PUT" });

// --- Assets ---
export interface AssetListResponse {
  assets: Record<string, unknown>[];
  total: number;
}
export const listAssets = (params?: Record<string, string>) => {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return request<AssetListResponse>(`/assets${qs}`);
};
export const approveAsset = (id: string) =>
  request(`/assets/${id}/approve`, { method: "POST" });
export const rejectAsset = (id: string) =>
  request(`/assets/${id}/reject`, { method: "POST" });

// --- Pipeline ---
export interface StepLog {
  step: string;
  status: string;
  duration: number;
  message?: string;
  error?: string;
}
export interface PipelineStatusResponse {
  is_running: boolean;
  current: {
    run_id: number;
    topic_id: string;
    franchise_id: string;
    status: string;
    current_step: string;
    steps_log: StepLog[];
  };
  steps: { id: string; label: string }[];
  runs: Record<string, unknown>[];
}
export const runPipeline = () =>
  request<{ status: string; message: string }>("/pipeline/run", { method: "POST" });
export const stopPipeline = () =>
  request<{ status: string; message: string }>("/pipeline/stop", { method: "POST" });
export const pipelineStatus = () =>
  request<PipelineStatusResponse>("/pipeline/status");

// --- Analytics ---
export interface DashboardAnalytics {
  total_videos: number;
  total_views: number;
  videos_this_week: number;
  queued_topics: number;
  total_subscribers_gained: number;
  views_change_pct: number;
}
export const getDashboardAnalytics = () =>
  request<DashboardAnalytics>("/analytics/dashboard");

export interface Insight {
  tag: string;
  type: string;
  priority: string;
  text: string;
  franchise_id?: string;
  metric?: number;
}
export const getInsights = () =>
  request<{ insights: Insight[]; message?: string }>("/analytics/insights");
export const refreshInsights = () =>
  request<{ insights: Insight[]; count: number }>("/analytics/insights/refresh", { method: "POST" });

export interface FranchiseAnalytics {
  franchise_id: string;
  name: string;
  category: string;
  video_count: number;
  total_views: number;
  avg_views: number;
  avg_retention: number;
  subs_gained: number;
  weight: number;
}
export const getAllFranchiseAnalytics = () =>
  request<{ franchises: FranchiseAnalytics[] }>("/analytics/franchises");

export interface FranchiseDetail {
  franchise_id: string;
  total_videos: number;
  total_views: number;
  avg_views: number;
  avg_retention: number;
  total_subscribers_gained: number;
  videos: VideoAnalytics[];
}
export const getFranchiseAnalytics = (id: string) =>
  request<FranchiseDetail>(`/analytics/franchise/${id}`);

export interface VideoAnalytics {
  video_id?: number;
  id?: number;
  title: string;
  franchise_id: string;
  narrator_archetype?: string;
  closer_style?: string;
  published_at?: string;
  youtube_video_id?: string;
  snapshot_type?: string;
  views?: number;
  likes?: number;
  comments?: number;
  shares?: number;
  avg_view_duration_pct?: number;
  click_through_rate?: number;
  subscribers_gained?: number;
}
export const getVideoAnalyticsList = () =>
  request<{ videos: VideoAnalytics[]; total: number }>("/analytics/videos");
export const getVideoAnalyticsDetail = (id: number) =>
  request<{ video: Record<string, unknown>; snapshots: Record<string, unknown>[] }>(`/analytics/videos/${id}`);

export interface ScoredVideo {
  id: number;
  title: string;
  franchise_id: string;
  narrator_archetype?: string;
  views: number;
  likes: number;
  comments: number;
  engagement_score: number;
  growth_score: number;
  virality_score: number;
  retention_score: number;
}
export const getDerivedScores = () =>
  request<{ videos: ScoredVideo[] }>("/analytics/scores");

export const triggerAnalyticsCollection = () =>
  request<{ status: string; collected: number; errors?: string[] }>("/analytics/collect", { method: "POST" });
export const triggerFeedbackLoop = () =>
  request<{ status: string; results: Record<string, unknown> }>("/analytics/feedback", { method: "POST" });
export const getFeedbackResults = () =>
  request<{ results: Record<string, unknown> }>("/analytics/feedback");

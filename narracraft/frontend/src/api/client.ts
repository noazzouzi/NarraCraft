// --- Types ---

export interface Franchise {
  id: string;
  name: string;
  category: string;
  visual_aesthetic: string | null;
  iconic_elements: string | null;
  created_at: string | null;
}

export interface FranchiseWithCharacters extends Franchise {
  characters: Character[];
}

export interface Character {
  id: string;
  franchise_id: string;
  name: string;
  appearance: string | null;
  outfit: string | null;
  personality: string | null;
  speech_style: string | null;
  flow_prompt: string | null;
  image_path: string | null;
  flow_url: string | null;
  created_at: string | null;
}

export interface ShortListItem {
  id: number;
  franchise_id: string;
  franchise_name: string | null;
  topic: string | null;
  status: string;
  current_step: number;
  scene_count: number;
  created_at: string | null;
  published_at: string | null;
}

export interface Short {
  id: number;
  franchise_id: string;
  franchise_name: string | null;
  topic: string | null;
  script_json: string | null;
  status: string;
  current_step: number;
  upload_metadata_json: string | null;
  created_at: string | null;
  published_at: string | null;
  scenes: Scene[];
}

export interface Scene {
  id: number;
  short_id: number;
  scene_number: number;
  character_id: string | null;
  character_name: string | null;
  dialogue: string | null;
  expression: string | null;
  environment: string | null;
  veo3_prompt: string | null;
  flow_url: string | null;
  status: string;
}

export interface TopicSuggestion {
  title: string;
  hook: string;
  characters: string[];
  category: string;
}

export interface LLMStatus {
  provider: string | null;
  model?: string;
  configured: boolean;
  free_tier?: boolean;
  rpd_limit?: number;
  message?: string;
  available_providers?: string[];
}

// --- API Helper ---

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

// --- Franchises ---

export const api = {
  // Franchises
  listFranchises: () => request<Franchise[]>("/api/franchises/"),

  createFranchise: (name: string, category: string) =>
    request<Franchise>("/api/franchises/", {
      method: "POST",
      body: JSON.stringify({ name, category }),
    }),

  getFranchise: (id: string) =>
    request<FranchiseWithCharacters>(`/api/franchises/${id}`),

  updateFranchise: (id: string, data: Partial<Franchise>) =>
    request<Franchise>(`/api/franchises/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteFranchise: (id: string) =>
    request<{ deleted: string }>(`/api/franchises/${id}`, { method: "DELETE" }),

  // Characters
  addCharacter: (franchiseId: string, name: string) =>
    request<Character>(`/api/franchises/${franchiseId}/characters`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  updateCharacter: (id: string, data: Partial<Character>) =>
    request<Character>(`/api/characters/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteCharacter: (id: string) =>
    request<{ deleted: string }>(`/api/characters/${id}`, { method: "DELETE" }),

  uploadCharacterImage: async (id: string, file: File): Promise<Character> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`/api/characters/${id}/image`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error("Upload failed");
    return res.json();
  },

  // Shorts
  listShorts: (params?: { franchise_id?: string; status?: string }) => {
    const query = new URLSearchParams();
    if (params?.franchise_id) query.set("franchise_id", params.franchise_id);
    if (params?.status) query.set("status", params.status);
    const qs = query.toString();
    return request<ShortListItem[]>(`/api/shorts/${qs ? `?${qs}` : ""}`);
  },

  createShort: (franchise_id: string) =>
    request<Short>("/api/shorts/", {
      method: "POST",
      body: JSON.stringify({ franchise_id }),
    }),

  getShort: (id: number) => request<Short>(`/api/shorts/${id}`),

  updateShort: (id: number, data: Partial<Short>) =>
    request<Short>(`/api/shorts/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteShort: (id: number) =>
    request<{ deleted: number }>(`/api/shorts/${id}`, { method: "DELETE" }),

  // Wizard
  generateTopics: (shortId: number) =>
    request<{ topics: TopicSuggestion[] }>(`/api/shorts/${shortId}/generate-topics`, {
      method: "POST",
    }),

  generateScript: (shortId: number, topic: string, hook: string, characterNames: string[]) =>
    request<Short>(`/api/shorts/${shortId}/generate-script`, {
      method: "POST",
      body: JSON.stringify({ topic, hook, character_names: characterNames }),
    }),

  generatePrompts: (shortId: number) =>
    request<Short>(`/api/shorts/${shortId}/generate-prompts`, {
      method: "POST",
    }),

  // Scenes
  updateScene: (id: number, data: { status?: string; flow_url?: string }) =>
    request<Scene>(`/api/scenes/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  // Settings
  getSettings: () => request<Record<string, string>>("/api/settings"),

  updateSettings: (settings: Record<string, string>) =>
    request<{ status: string }>("/api/settings", {
      method: "PUT",
      body: JSON.stringify({ settings }),
    }),

  // LLM
  llmStatus: () => request<LLMStatus>("/api/llm/status"),
};

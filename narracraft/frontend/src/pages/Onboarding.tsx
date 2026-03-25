import { useState, useCallback } from "react";
import { useTheme } from "@/components/ThemeProvider";
import {
  searchFranchise,
  discoverCharacters,
  discoverLocations,
  saveFranchise,
  type SearchResult,
  type CharacterResult,
} from "@/api/client";
import {
  Search,
  ChevronRight,
  ChevronLeft,
  Check,
  Loader2,
  Users,
  MapPin,
  Globe,
  Gamepad2,
  BookOpen,
  X,
} from "lucide-react";

type Step = "search" | "results" | "characters" | "review";

interface SelectedFranchise {
  title: string;
  source: string;
  wiki_slug?: string;
  igdb_id?: number;
  mal_id?: number;
  anilist_id?: number;
  summary?: string;
  image_url?: string;
  category: string;
  genres?: string[];
}

interface SelectedCharacter {
  name: string;
  description: string;
  image_url?: string;
  source: string;
  role?: string;
  selected: boolean;
}

interface DiscoveredLocation {
  name: string;
  description: string;
  image_urls: string[];
  page_url: string;
}

export default function Onboarding() {
  const { theme } = useTheme();

  const [step, setStep] = useState<Step>("search");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>("all");
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);

  const [selectedFranchise, setSelectedFranchise] = useState<SelectedFranchise | null>(null);
  const [loadingChars, setLoadingChars] = useState(false);
  const [characters, setCharacters] = useState<SelectedCharacter[]>([]);
  const [locations, setLocations] = useState<DiscoveredLocation[]>([]);

  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState<string | null>(null);
  const [franchiseId, setFranchiseId] = useState("");

  // Step 1: Search
  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    setSearching(true);
    setSaveResult(null);
    try {
      const cat = category === "all" ? undefined : category;
      const data = await searchFranchise(query, cat);
      setSearchResults(data.results);
      if (data.results.length > 0) setStep("results");
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }, [query, category]);

  // Step 2: Select a franchise result
  const handleSelectFranchise = useCallback((result: SearchResult) => {
    const isAnime = result.source === "jikan" || result.source === "anilist";
    setSelectedFranchise({
      title: result.title,
      source: result.source,
      wiki_slug: result.wiki_slug,
      igdb_id: result.igdb_id,
      mal_id: result.mal_id,
      anilist_id: result.anilist_id,
      summary: result.summary,
      image_url: result.image_url,
      category: isAnime ? "anime_manga" : "gaming",
      genres: result.genres,
    });
    // Auto-generate franchise ID
    const id = result.title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "")
      .slice(0, 40);
    setFranchiseId(id);
  }, []);

  // Step 3: Discover characters
  const handleDiscoverCharacters = useCallback(async () => {
    if (!selectedFranchise) return;
    setLoadingChars(true);
    setStep("characters");
    try {
      const [charData, locData] = await Promise.all([
        discoverCharacters({
          franchise_id: franchiseId,
          wiki_slug: selectedFranchise.wiki_slug,
          mal_id: selectedFranchise.mal_id,
          anilist_id: selectedFranchise.anilist_id,
          igdb_id: selectedFranchise.igdb_id,
        }),
        discoverLocations(franchiseId, selectedFranchise.wiki_slug),
      ]);

      // Deduplicate characters by name
      const seen = new Set<string>();
      const chars: SelectedCharacter[] = [];
      for (const c of charData.characters) {
        const key = c.name.toLowerCase();
        if (seen.has(key)) continue;
        seen.add(key);
        chars.push({
          name: c.name,
          description: c.description || "",
          image_url: c.image_urls?.[0],
          source: c.source,
          role: c.role,
          selected: true,
        });
      }
      setCharacters(chars);
      setLocations(locData.locations || []);
    } catch {
      setCharacters([]);
      setLocations([]);
    } finally {
      setLoadingChars(false);
    }
  }, [selectedFranchise, franchiseId]);

  // Step 4: Save franchise
  const handleSave = useCallback(async () => {
    if (!selectedFranchise) return;
    setSaving(true);
    try {
      const selectedChars = characters.filter((c) => c.selected);
      await saveFranchise({
        id: franchiseId,
        name: selectedFranchise.title,
        franchise_group: franchiseId,
        category: selectedFranchise.category,
        characters: selectedChars.map((c) => ({
          name: c.name,
          archetype_id: c.name.toLowerCase().replace(/[^a-z0-9]+/g, "_").slice(0, 30),
          description: c.description,
          source: c.source,
          role: c.role,
        })),
        environments: locations.map((l) => ({
          env_id: l.name.toLowerCase().replace(/[^a-z0-9]+/g, "_").slice(0, 30),
          name: l.name,
          description: l.description,
        })),
      });
      setSaveResult("success");
    } catch {
      setSaveResult("error");
    } finally {
      setSaving(false);
    }
  }, [selectedFranchise, characters, locations, franchiseId]);

  const toggleCharacter = (index: number) => {
    setCharacters((prev) =>
      prev.map((c, i) => (i === index ? { ...c, selected: !c.selected } : c)),
    );
  };

  const sourceIcon = (source: string) => {
    switch (source) {
      case "fandom_wiki": return <Globe size={12} />;
      case "igdb": return <Gamepad2 size={12} />;
      case "jikan":
      case "anilist": return <BookOpen size={12} />;
      default: return <Search size={12} />;
    }
  };

  const sourceBadgeColor = (source: string) => {
    switch (source) {
      case "fandom_wiki": return "#4CAF50";
      case "igdb": return "#9C27B0";
      case "jikan": return "#2196F3";
      case "anilist": return "#E91E63";
      default: return theme.dim;
    }
  };

  // Shared card style
  const cardStyle = {
    background: theme.surface,
    border: `1px solid ${theme.border}`,
    borderRadius: theme.card.borderRadius,
    ...theme.card,
  };

  return (
    <div className="flex-1 p-5 overflow-y-auto" style={{ fontFamily: theme.body }}>
      {/* Header */}
      <h1
        className="m-0 mb-1"
        style={{ fontSize: 22, fontWeight: 700, fontFamily: theme.font, color: theme.text }}
      >
        Franchise Onboarding
      </h1>
      <p className="mb-5" style={{ fontSize: 13, color: theme.dim }}>
        Search, discover, and onboard new franchises into the system.
      </p>

      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-5">
        {(["search", "results", "characters", "review"] as Step[]).map((s, i) => {
          const labels = ["Search", "Select", "Characters", "Save"];
          const isActive = s === step;
          const isDone =
            (s === "search" && step !== "search") ||
            (s === "results" && (step === "characters" || step === "review")) ||
            (s === "characters" && step === "review");
          return (
            <div key={s} className="flex items-center gap-2">
              {i > 0 && (
                <ChevronRight size={14} style={{ color: theme.muted }} />
              )}
              <div
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold tracking-wide"
                style={{
                  background: isActive ? `${theme.accent}20` : isDone ? `${theme.success}15` : "transparent",
                  border: `1px solid ${isActive ? theme.accent : isDone ? theme.success : theme.border}`,
                  borderRadius: theme.card.borderRadius,
                  color: isActive ? theme.accent : isDone ? theme.success : theme.dim,
                  fontFamily: theme.mono,
                  cursor: isDone ? "pointer" : "default",
                }}
                onClick={() => isDone && setStep(s)}
              >
                {isDone && <Check size={12} />}
                {labels[i]}
              </div>
            </div>
          );
        })}
      </div>

      {/* === STEP 1: Search === */}
      {step === "search" && (
        <div>
          <div className="flex items-center gap-3 p-4 mb-4" style={cardStyle}>
            <div className="flex items-center gap-2 shrink-0">
              {(["all", "gaming", "anime_manga"] as const).map((cat) => (
                <button
                  key={cat}
                  onClick={() => setCategory(cat)}
                  className="px-3 py-1.5 text-[11px] font-semibold tracking-wide cursor-pointer"
                  style={{
                    background: category === cat ? `${theme.accent}20` : "transparent",
                    border: `1px solid ${category === cat ? theme.accent : theme.border}`,
                    color: category === cat ? theme.accent : theme.dim,
                    fontFamily: theme.mono,
                    borderRadius: theme.card.borderRadius,
                  }}
                >
                  {cat === "all" ? "ALL" : cat === "gaming" ? "GAMES" : "ANIME"}
                </button>
              ))}
            </div>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Search for a game or anime..."
              className="flex-1 bg-transparent border-none outline-none text-sm"
              style={{ color: theme.text, fontFamily: theme.body }}
            />
            <button
              onClick={handleSearch}
              disabled={searching || !query.trim()}
              className="flex items-center gap-2 px-4 py-2 text-xs font-bold tracking-wider cursor-pointer disabled:opacity-40"
              style={{
                background: `${theme.accent}15`,
                border: `1px solid ${theme.accent}`,
                color: theme.accent,
                fontFamily: theme.mono,
                borderRadius: theme.card.borderRadius,
              }}
            >
              {searching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              SEARCH
            </button>
          </div>

          {searchResults.length === 0 && !searching && (
            <div className="p-8 text-center" style={cardStyle}>
              <p style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 11 }}>
                Search across Fandom Wiki, IGDB, MyAnimeList, and AniList.
              </p>
            </div>
          )}
        </div>
      )}

      {/* === STEP 2: Results === */}
      {step === "results" && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => setStep("search")}
              className="flex items-center gap-1 text-xs cursor-pointer bg-transparent border-none"
              style={{ color: theme.dim, fontFamily: theme.mono }}
            >
              <ChevronLeft size={14} /> Back to search
            </button>
            <span style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 11 }}>
              {searchResults.length} results for "{query}"
            </span>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {searchResults.map((result, i) => {
              const isSelected = selectedFranchise?.title === result.title && selectedFranchise?.source === result.source;
              return (
                <div
                  key={`${result.source}-${i}`}
                  className="flex gap-4 p-4 cursor-pointer transition-all"
                  style={{
                    ...cardStyle,
                    border: `1px solid ${isSelected ? theme.accent : theme.border}`,
                    background: isSelected ? `${theme.accent}08` : theme.surface,
                  }}
                  onClick={() => handleSelectFranchise(result)}
                >
                  {/* Thumbnail */}
                  {result.image_url && (
                    <img
                      src={result.image_url}
                      alt={result.title}
                      className="w-16 h-20 object-cover shrink-0"
                      style={{ borderRadius: theme.card.borderRadius }}
                    />
                  )}

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className="font-bold text-sm"
                        style={{ color: theme.text, fontFamily: theme.font }}
                      >
                        {result.title}
                      </span>
                      <span
                        className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold tracking-wider"
                        style={{
                          background: `${sourceBadgeColor(result.source)}20`,
                          color: sourceBadgeColor(result.source),
                          borderRadius: "2px",
                          fontFamily: theme.mono,
                        }}
                      >
                        {sourceIcon(result.source)}
                        {result.source.toUpperCase().replace("_", " ")}
                      </span>
                    </div>

                    {result.summary && (
                      <p
                        className="text-xs m-0 mb-2 line-clamp-2"
                        style={{ color: theme.dim }}
                      >
                        {result.summary}
                      </p>
                    )}

                    {result.genres && result.genres.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {result.genres.slice(0, 5).map((g) => (
                          <span
                            key={g}
                            className="px-1.5 py-0.5 text-[10px]"
                            style={{
                              background: `${theme.dim}15`,
                              color: theme.dim,
                              borderRadius: "2px",
                              fontFamily: theme.mono,
                            }}
                          >
                            {typeof g === "string" ? g : String(g)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {isSelected && (
                    <Check size={20} style={{ color: theme.accent }} className="shrink-0 self-center" />
                  )}
                </div>
              );
            })}
          </div>

          {/* Continue button */}
          {selectedFranchise && (
            <div className="flex justify-end mt-4">
              <button
                onClick={handleDiscoverCharacters}
                className="flex items-center gap-2 px-5 py-2.5 text-xs font-bold tracking-wider cursor-pointer"
                style={{
                  background: theme.accent,
                  border: "none",
                  color: theme.bg,
                  fontFamily: theme.mono,
                  borderRadius: theme.card.borderRadius,
                }}
              >
                DISCOVER CHARACTERS <ChevronRight size={14} />
              </button>
            </div>
          )}
        </div>
      )}

      {/* === STEP 3: Characters === */}
      {step === "characters" && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => setStep("results")}
              className="flex items-center gap-1 text-xs cursor-pointer bg-transparent border-none"
              style={{ color: theme.dim, fontFamily: theme.mono }}
            >
              <ChevronLeft size={14} /> Back to results
            </button>
            <span style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 11 }}>
              {selectedFranchise?.title}
            </span>
          </div>

          {loadingChars ? (
            <div className="flex items-center justify-center gap-3 p-12" style={cardStyle}>
              <Loader2 size={20} className="animate-spin" style={{ color: theme.accent }} />
              <span style={{ color: theme.dim, fontFamily: theme.mono, fontSize: 12 }}>
                Discovering characters and locations...
              </span>
            </div>
          ) : (
            <>
              {/* Characters */}
              <div className="mb-6">
                <div className="flex items-center gap-2 mb-3">
                  <Users size={16} style={{ color: theme.accent }} />
                  <h2 className="m-0 text-sm font-bold" style={{ color: theme.text, fontFamily: theme.font }}>
                    Characters
                  </h2>
                  <span
                    className="text-[10px] px-2 py-0.5"
                    style={{ color: theme.dim, fontFamily: theme.mono, background: `${theme.dim}15`, borderRadius: "2px" }}
                  >
                    {characters.filter((c) => c.selected).length}/{characters.length} selected
                  </span>
                </div>

                {characters.length === 0 ? (
                  <div className="p-6 text-center" style={cardStyle}>
                    <p style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 11 }}>
                      No characters discovered. You can add them manually later.
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    {characters.map((char, i) => (
                      <div
                        key={`${char.name}-${i}`}
                        className="flex items-start gap-3 p-3 cursor-pointer transition-all"
                        style={{
                          ...cardStyle,
                          border: `1px solid ${char.selected ? theme.accent : theme.border}`,
                          opacity: char.selected ? 1 : 0.5,
                        }}
                        onClick={() => toggleCharacter(i)}
                      >
                        {char.image_url ? (
                          <img
                            src={char.image_url}
                            alt={char.name}
                            className="w-10 h-10 object-cover rounded shrink-0"
                          />
                        ) : (
                          <div
                            className="w-10 h-10 flex items-center justify-center shrink-0 rounded text-xs font-bold"
                            style={{ background: `${theme.accent}15`, color: theme.accent }}
                          >
                            {char.name[0]}
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold truncate" style={{ color: theme.text }}>
                              {char.name}
                            </span>
                            {char.role && (
                              <span className="text-[10px]" style={{ color: theme.dim, fontFamily: theme.mono }}>
                                {char.role}
                              </span>
                            )}
                          </div>
                          {char.description && (
                            <p className="text-[11px] m-0 mt-0.5 line-clamp-2" style={{ color: theme.dim }}>
                              {char.description.slice(0, 120)}
                            </p>
                          )}
                        </div>
                        <div className="shrink-0 self-center">
                          {char.selected ? (
                            <Check size={16} style={{ color: theme.accent }} />
                          ) : (
                            <X size={16} style={{ color: theme.muted }} />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Locations */}
              {locations.length > 0 && (
                <div className="mb-6">
                  <div className="flex items-center gap-2 mb-3">
                    <MapPin size={16} style={{ color: theme.accent }} />
                    <h2 className="m-0 text-sm font-bold" style={{ color: theme.text, fontFamily: theme.font }}>
                      Locations
                    </h2>
                    <span
                      className="text-[10px] px-2 py-0.5"
                      style={{ color: theme.dim, fontFamily: theme.mono, background: `${theme.dim}15`, borderRadius: "2px" }}
                    >
                      {locations.length} found
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    {locations.slice(0, 12).map((loc, i) => (
                      <div key={i} className="p-3" style={cardStyle}>
                        <span className="text-xs font-bold" style={{ color: theme.text }}>
                          {loc.name}
                        </span>
                        {loc.description && (
                          <p className="text-[11px] m-0 mt-1 line-clamp-2" style={{ color: theme.dim }}>
                            {loc.description.slice(0, 100)}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Continue to review */}
              <div className="flex justify-end">
                <button
                  onClick={() => setStep("review")}
                  className="flex items-center gap-2 px-5 py-2.5 text-xs font-bold tracking-wider cursor-pointer"
                  style={{
                    background: theme.accent,
                    border: "none",
                    color: theme.bg,
                    fontFamily: theme.mono,
                    borderRadius: theme.card.borderRadius,
                  }}
                >
                  REVIEW & SAVE <ChevronRight size={14} />
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* === STEP 4: Review & Save === */}
      {step === "review" && selectedFranchise && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => setStep("characters")}
              className="flex items-center gap-1 text-xs cursor-pointer bg-transparent border-none"
              style={{ color: theme.dim, fontFamily: theme.mono }}
            >
              <ChevronLeft size={14} /> Back to characters
            </button>
          </div>

          {/* Summary card */}
          <div className="p-5 mb-4" style={cardStyle}>
            <h2 className="m-0 mb-3 text-base font-bold" style={{ color: theme.text, fontFamily: theme.font }}>
              {selectedFranchise.title}
            </h2>

            <div className="grid grid-cols-2 gap-4 text-xs" style={{ color: theme.dim }}>
              <div>
                <span style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 10 }}>FRANCHISE ID</span>
                <div className="mt-1">
                  <input
                    type="text"
                    value={franchiseId}
                    onChange={(e) => setFranchiseId(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_"))}
                    className="w-full bg-transparent text-xs p-1.5"
                    style={{
                      color: theme.text,
                      border: `1px solid ${theme.border}`,
                      borderRadius: theme.card.borderRadius,
                      fontFamily: theme.mono,
                    }}
                  />
                </div>
              </div>
              <div>
                <span style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 10 }}>CATEGORY</span>
                <div className="mt-1" style={{ color: theme.text }}>{selectedFranchise.category}</div>
              </div>
              <div>
                <span style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 10 }}>CHARACTERS</span>
                <div className="mt-1" style={{ color: theme.text }}>
                  {characters.filter((c) => c.selected).length} selected
                </div>
              </div>
              <div>
                <span style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 10 }}>LOCATIONS</span>
                <div className="mt-1" style={{ color: theme.text }}>{locations.length} discovered</div>
              </div>
              <div>
                <span style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 10 }}>SOURCE</span>
                <div className="mt-1" style={{ color: theme.text }}>{selectedFranchise.source}</div>
              </div>
              {selectedFranchise.genres && selectedFranchise.genres.length > 0 && (
                <div>
                  <span style={{ color: theme.muted, fontFamily: theme.mono, fontSize: 10 }}>GENRES</span>
                  <div className="mt-1" style={{ color: theme.text }}>
                    {selectedFranchise.genres.slice(0, 4).join(", ")}
                  </div>
                </div>
              )}
            </div>

            {selectedFranchise.summary && (
              <p className="text-xs mt-3 m-0" style={{ color: theme.dim }}>
                {selectedFranchise.summary}
              </p>
            )}
          </div>

          {/* Selected characters list */}
          {characters.filter((c) => c.selected).length > 0 && (
            <div className="p-4 mb-4" style={cardStyle}>
              <div className="flex items-center gap-2 mb-3">
                <Users size={14} style={{ color: theme.accent }} />
                <span className="text-xs font-bold" style={{ color: theme.text, fontFamily: theme.font }}>
                  Selected Characters
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {characters.filter((c) => c.selected).map((c, i) => (
                  <span
                    key={i}
                    className="px-2 py-1 text-[11px]"
                    style={{
                      background: `${theme.accent}15`,
                      border: `1px solid ${theme.accent}40`,
                      borderRadius: theme.card.borderRadius,
                      color: theme.text,
                      fontFamily: theme.mono,
                    }}
                  >
                    {c.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Save button */}
          <div className="flex items-center gap-3 justify-end">
            {saveResult === "success" && (
              <span className="flex items-center gap-1 text-xs" style={{ color: theme.success, fontFamily: theme.mono }}>
                <Check size={14} /> Franchise saved successfully!
              </span>
            )}
            {saveResult === "error" && (
              <span className="text-xs" style={{ color: theme.danger, fontFamily: theme.mono }}>
                Error saving franchise. Check backend logs.
              </span>
            )}
            <button
              onClick={handleSave}
              disabled={saving || !franchiseId.trim()}
              className="flex items-center gap-2 px-6 py-2.5 text-xs font-bold tracking-wider cursor-pointer disabled:opacity-40"
              style={{
                background: theme.accent,
                border: "none",
                color: theme.bg,
                fontFamily: theme.mono,
                borderRadius: theme.card.borderRadius,
              }}
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
              SAVE FRANCHISE
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

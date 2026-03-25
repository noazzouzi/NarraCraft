/**
 * NarraCraft Theme Definitions
 * Ported from dashboard-mockup.jsx — 10 themes, each with colors,
 * fonts, card styles, and in-context terminology ("flavor").
 */

export interface ThemeFlavor {
  deploy: string;
  abort: string;
  log: string;
  queue: string;
  perf: string;
  intel: string;
}

export interface ThemeCardStyle {
  borderRadius: string;
  borderTop?: string;
  borderLeft?: string;
  borderRight?: string;
  borderBottom?: string;
  boxShadow?: string;
}

export interface Theme {
  id: string;
  name: string;
  emoji: string;
  desc: string;
  isLight: boolean;

  // Colors
  bg: string;
  surface: string;
  border: string;
  text: string;
  dim: string;
  muted: string;
  accent: string;
  success: string;
  danger: string;

  // Preview colors (for theme picker strip)
  preview: [string, string, string];

  // Fonts
  font: string;   // Display / headings
  body: string;   // Body text
  mono: string;   // Monospace

  // Card styling
  card: ThemeCardStyle;

  // In-context terminology
  f: ThemeFlavor;
}

export const themes: Record<string, Theme> = {
  gothic: {
    id: "gothic",
    name: "Gothic Cathedral",
    emoji: "\u2694\uFE0F",
    desc: "Dark Souls \u00B7 Bloodborne \u00B7 Elden Ring",
    isLight: false,
    preview: ["#0C0A08", "#C9A84C", "#141210"],
    bg: "#0C0A08", surface: "#141210", border: "#2A2420",
    text: "#D4C8B8", dim: "#6B5F50", muted: "#3D352C",
    accent: "#C9A84C", success: "#7B9E4A", danger: "#8B3A3A",
    font: "'Cinzel', serif", body: "'Crimson Text', serif", mono: "'IBM Plex Mono', monospace",
    card: { borderRadius: "2px", borderTop: "2px solid rgba(139, 115, 85, 0.25)" },
    f: { deploy: "KINDLE", abort: "EXTINGUISH", log: "Chronicle", queue: "Upcoming Rites", perf: "Domain Conquest", intel: "Whispers from the Abyss" },
  },
  survival: {
    id: "survival",
    name: "Survival Horror",
    emoji: "\u2623\uFE0F",
    desc: "Resident Evil \u00B7 Silent Hill",
    isLight: false,
    preview: ["#0A0C0A", "#4CAF50", "#0F120F"],
    bg: "#0A0C0A", surface: "#0F120F", border: "#1E2A1E",
    text: "#B8C4A8", dim: "#5A6B4A", muted: "#2E3A28",
    accent: "#4CAF50", success: "#4CAF50", danger: "#D32F2F",
    font: "'Courier Prime', monospace", body: "'Source Sans 3', sans-serif", mono: "'Courier Prime', monospace",
    card: { borderRadius: "0px", borderLeft: "3px solid rgba(76, 175, 80, 0.19)" },
    f: { deploy: "EXECUTE", abort: "ABORT", log: "System Log", queue: "Pending Ops", perf: "Sector Status", intel: "Field Reports" },
  },
  ink: {
    id: "ink",
    name: "Manga Ink",
    emoji: "\u2712\uFE0F",
    desc: "One Piece \u00B7 JJK \u00B7 Naruto",
    isLight: true,
    preview: ["#F5F0E8", "#E63946", "#FFFFFF"],
    bg: "#F5F0E8", surface: "#FFFFFF", border: "#E0D8C8",
    text: "#1A1A1A", dim: "#6B6560", muted: "#A8A098",
    accent: "#E63946", success: "#2D6A4F", danger: "#E63946",
    font: "'Noto Serif JP', serif", body: "'Noto Sans JP', sans-serif", mono: "'DM Mono', monospace",
    card: { borderRadius: "0px", borderBottom: "3px solid #1A1A1A", boxShadow: "3px 3px 0 rgba(26, 26, 26, 0.06)" },
    f: { deploy: "PUBLISH", abort: "CANCEL", log: "Story So Far", queue: "Next Chapters", perf: "Bounty Board", intel: "Editor's Notes" },
  },
  arcade: {
    id: "arcade",
    name: "Neon Arcade",
    emoji: "\uD83D\uDC7E",
    desc: "Retro gaming \u00B7 Pixel art",
    isLight: false,
    preview: ["#0A0012", "#FF00FF", "#120020"],
    bg: "#0A0012", surface: "#120020", border: "#2A1040",
    text: "#E0D0FF", dim: "#8060A0", muted: "#402060",
    accent: "#FF00FF", success: "#00FF88", danger: "#FF2244",
    font: "'Press Start 2P', monospace", body: "'Chakra Petch', sans-serif", mono: "'Press Start 2P', monospace",
    card: { borderRadius: "0px", boxShadow: "0 0 10px rgba(255, 0, 255, 0.03), inset 0 0 10px rgba(255, 0, 255, 0.015)" },
    f: { deploy: "START", abort: "GAME OVER", log: "High Scores", queue: "Next Stage", perf: "Leaderboard", intel: "Pro Tips" },
  },
  ancient: {
    id: "ancient",
    name: "Ancient Scroll",
    emoji: "\uD83D\uDCDC",
    desc: "Zelda \u00B7 Elden Ring \u00B7 Fantasy RPG",
    isLight: false,
    preview: ["#1A1610", "#B8963A", "#211C14"],
    bg: "#1A1610", surface: "#211C14", border: "#342A1E",
    text: "#D4C4A0", dim: "#7A6C50", muted: "#443C2E",
    accent: "#B8963A", success: "#6B8E23", danger: "#8B0000",
    font: "'MedievalSharp', cursive", body: "'Lora', serif", mono: "'Fira Code', monospace",
    card: { borderRadius: "2px" },
    f: { deploy: "EMBARK", abort: "RETREAT", log: "Traveler's Log", queue: "Quests Ahead", perf: "Conquered Lands", intel: "Oracle's Wisdom" },
  },
  shinobi: {
    id: "shinobi",
    name: "Shinobi Dusk",
    emoji: "\uD83C\uDF19",
    desc: "Naruto \u00B7 Demon Slayer \u00B7 Ninja",
    isLight: false,
    preview: ["#0C0814", "#FF6B35", "#12101C"],
    bg: "#0C0814", surface: "#12101C", border: "#221E30",
    text: "#C8C0D8", dim: "#6A6080", muted: "#3A3450",
    accent: "#FF6B35", success: "#66BB6A", danger: "#EF5350",
    font: "'Zen Dots', sans-serif", body: "'Nunito', sans-serif", mono: "'Fira Code', monospace",
    card: { borderRadius: "4px", borderRight: "3px solid rgba(255, 107, 53, 0.19)" },
    f: { deploy: "STRIKE", abort: "WITHDRAW", log: "Mission Scroll", queue: "Targets", perf: "Clan Rankings", intel: "Sensei's Advice" },
  },
  ocean: {
    id: "ocean",
    name: "Grand Line",
    emoji: "\uD83C\uDFF4\u200D\u2620\uFE0F",
    desc: "One Piece \u00B7 Sea adventure \u00B7 Pirate",
    isLight: false,
    preview: ["#0A1018", "#2196F3", "#0F1520"],
    bg: "#0A1018", surface: "#0F1520", border: "#1A2530",
    text: "#B8CCE0", dim: "#5A7090", muted: "#2A3A50",
    accent: "#2196F3", success: "#26A69A", danger: "#EF5350",
    font: "'Righteous', sans-serif", body: "'Nunito Sans', sans-serif", mono: "'DM Mono', monospace",
    card: { borderRadius: "6px", borderBottom: "2px solid rgba(33, 150, 243, 0.19)" },
    f: { deploy: "SET SAIL", abort: "DROP ANCHOR", log: "Captain's Log", queue: "Treasure Map", perf: "Crew Bounties", intel: "Lookout Report" },
  },
  void: {
    id: "void",
    name: "Cosmic Void",
    emoji: "\uD83C\uDF0C",
    desc: "Final Fantasy \u00B7 Kingdom Hearts \u00B7 Space",
    isLight: false,
    preview: ["#06060F", "#7C4DFF", "#0E0E1A"],
    bg: "#06060F", surface: "#0E0E1A", border: "#1A1A30",
    text: "#C8C4E0", dim: "#6860A0", muted: "#383458",
    accent: "#7C4DFF", success: "#69F0AE", danger: "#FF5252",
    font: "'Orbitron', sans-serif", body: "'Quicksand', sans-serif", mono: "'Space Mono', monospace",
    card: { borderRadius: "8px", boxShadow: "0 0 15px rgba(124, 77, 255, 0.03)" },
    f: { deploy: "LAUNCH", abort: "RECALL", log: "Star Chart", queue: "Next Warp", perf: "Galaxy Map", intel: "Astral Echoes" },
  },
  ember: {
    id: "ember",
    name: "Volcanic Ember",
    emoji: "\uD83C\uDF0B",
    desc: "Monster Hunter \u00B7 Dragon's Dogma \u00B7 Fire",
    isLight: false,
    preview: ["#100808", "#FF5722", "#181010"],
    bg: "#100808", surface: "#181010", border: "#2A1A1A",
    text: "#D8C0B0", dim: "#8A6858", muted: "#4A3430",
    accent: "#FF5722", success: "#8BC34A", danger: "#FF5722",
    font: "'Bungee Shade', sans-serif", body: "'Merriweather Sans', sans-serif", mono: "'IBM Plex Mono', monospace",
    card: { borderRadius: "2px", borderBottom: "2px solid rgba(255, 87, 34, 0.15)" },
    f: { deploy: "IGNITE", abort: "QUENCH", log: "Forge Record", queue: "Hunt Board", perf: "Kill Count", intel: "Sage's Warning" },
  },
  clean: {
    id: "clean",
    name: "Studio Minimal",
    emoji: "\u25FB\uFE0F",
    desc: "Clean \u00B7 Professional \u00B7 Neutral",
    isLight: true,
    preview: ["#F8F9FA", "#1A1A2E", "#FFFFFF"],
    bg: "#F8F9FA", surface: "#FFFFFF", border: "#E8E8EE",
    text: "#1A1A2E", dim: "#6B6B80", muted: "#AAAABB",
    accent: "#1A1A2E", success: "#2E7D32", danger: "#C62828",
    font: "'Sora', sans-serif", body: "'Sora', sans-serif", mono: "'JetBrains Mono', monospace",
    card: { borderRadius: "8px", boxShadow: "0 1px 3px rgba(0, 0, 0, 0.03)" },
    f: { deploy: "RUN", abort: "STOP", log: "Activity", queue: "Queue", perf: "Performance", intel: "Suggestions" },
  },
};

export const themeIds = Object.keys(themes) as (keyof typeof themes)[];

/** Google Fonts URL that loads all fonts used by all themes. */
export const GOOGLE_FONTS_URL =
  "https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700;800;900&family=Crimson+Text:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500;700&family=Courier+Prime:wght@400;700&family=Source+Sans+3:wght@400;500;600;700&family=Noto+Serif+JP:wght@400;600;700&family=Noto+Sans+JP:wght@400;500;600;700&family=DM+Mono:wght@400;500&family=Press+Start+2P&family=Chakra+Petch:wght@400;500;600;700&family=MedievalSharp&family=Lora:wght@400;500;600;700&family=Fira+Code:wght@400;500;600;700&family=Zen+Dots&family=Nunito:wght@400;600;700;800&family=Righteous&family=Nunito+Sans:wght@400;500;600;700&family=Orbitron:wght@400;500;600;700;800;900&family=Quicksand:wght@400;500;600;700&family=Space+Mono:wght@400;700&family=Bungee+Shade&family=Merriweather+Sans:wght@400;500;600;700&family=Sora:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap";

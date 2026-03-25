import { useState } from "react";

const T = {
  gothic: {
    name: "Gothic Cathedral", emoji: "⚔️",
    desc: "Dark Souls · Bloodborne · Elden Ring",
    preview: ["#0C0A08","#C9A84C","#141210"],
    bg: "#0C0A08", surface: "#141210", border: "#2A2420",
    text: "#D4C8B8", dim: "#6B5F50", muted: "#3D352C",
    accent: "#C9A84C", success: "#7B9E4A", danger: "#8B3A3A",
    font: "'Cinzel', serif", body: "'Crimson Text', serif", mono: "'IBM Plex Mono', monospace",
    card: { borderRadius: "2px", borderTop: "2px solid #8B735540" },
    f: { deploy:"KINDLE", abort:"EXTINGUISH", log:"Chronicle", queue:"Upcoming Rites", perf:"Domain Conquest", intel:"Whispers from the Abyss" },
  },
  survival: {
    name: "Survival Horror", emoji: "☣️",
    desc: "Resident Evil · Silent Hill",
    preview: ["#0A0C0A","#4CAF50","#0F120F"],
    bg: "#0A0C0A", surface: "#0F120F", border: "#1E2A1E",
    text: "#B8C4A8", dim: "#5A6B4A", muted: "#2E3A28",
    accent: "#4CAF50", success: "#4CAF50", danger: "#D32F2F",
    font: "'Courier Prime', monospace", body: "'Source Sans 3', sans-serif", mono: "'Courier Prime', monospace",
    card: { borderRadius: "0px", borderLeft: "3px solid #4CAF5030" },
    f: { deploy:"EXECUTE", abort:"ABORT", log:"System Log", queue:"Pending Ops", perf:"Sector Status", intel:"Field Reports" },
  },
  ink: {
    name: "Manga Ink", emoji: "✒️",
    desc: "One Piece · JJK · Naruto",
    preview: ["#F5F0E8","#E63946","#FFFFFF"],
    bg: "#F5F0E8", surface: "#FFFFFF", border: "#E0D8C8",
    text: "#1A1A1A", dim: "#6B6560", muted: "#A8A098",
    accent: "#E63946", success: "#2D6A4F", danger: "#E63946",
    font: "'Noto Serif JP', serif", body: "'Noto Sans JP', sans-serif", mono: "'DM Mono', monospace",
    card: { borderRadius: "0px", borderBottom: "3px solid #1A1A1A", boxShadow: "3px 3px 0 #1A1A1A10" },
    f: { deploy:"PUBLISH", abort:"CANCEL", log:"Story So Far", queue:"Next Chapters", perf:"Bounty Board", intel:"Editor's Notes" },
  },
  arcade: {
    name: "Neon Arcade", emoji: "👾",
    desc: "Retro gaming · Pixel art",
    preview: ["#0A0012","#FF00FF","#120020"],
    bg: "#0A0012", surface: "#120020", border: "#2A1040",
    text: "#E0D0FF", dim: "#8060A0", muted: "#402060",
    accent: "#FF00FF", success: "#00FF88", danger: "#FF2244",
    font: "'Press Start 2P', monospace", body: "'Chakra Petch', sans-serif", mono: "'Press Start 2P', monospace",
    card: { borderRadius: "0px", boxShadow: "0 0 10px #FF00FF08, inset 0 0 10px #FF00FF04" },
    f: { deploy:"START", abort:"GAME OVER", log:"High Scores", queue:"Next Stage", perf:"Leaderboard", intel:"Pro Tips" },
  },
  ancient: {
    name: "Ancient Scroll", emoji: "📜",
    desc: "Zelda · Elden Ring · Fantasy RPG",
    preview: ["#1A1610","#B8963A","#211C14"],
    bg: "#1A1610", surface: "#211C14", border: "#342A1E",
    text: "#D4C4A0", dim: "#7A6C50", muted: "#443C2E",
    accent: "#B8963A", success: "#6B8E23", danger: "#8B0000",
    font: "'MedievalSharp', cursive", body: "'Lora', serif", mono: "'Fira Code', monospace",
    card: { borderRadius: "2px" },
    f: { deploy:"EMBARK", abort:"RETREAT", log:"Traveler's Log", queue:"Quests Ahead", perf:"Conquered Lands", intel:"Oracle's Wisdom" },
  },
  shinobi: {
    name: "Shinobi Dusk", emoji: "🌙",
    desc: "Naruto · Demon Slayer · Ninja",
    preview: ["#0C0814","#FF6B35","#12101C"],
    bg: "#0C0814", surface: "#12101C", border: "#221E30",
    text: "#C8C0D8", dim: "#6A6080", muted: "#3A3450",
    accent: "#FF6B35", success: "#66BB6A", danger: "#EF5350",
    font: "'Zen Dots', sans-serif", body: "'Nunito', sans-serif", mono: "'Fira Code', monospace",
    card: { borderRadius: "4px", borderRight: "3px solid #FF6B3530" },
    f: { deploy:"STRIKE", abort:"WITHDRAW", log:"Mission Scroll", queue:"Targets", perf:"Clan Rankings", intel:"Sensei's Advice" },
  },
  ocean: {
    name: "Grand Line", emoji: "🏴‍☠️",
    desc: "One Piece · Sea adventure · Pirate",
    preview: ["#0A1018","#2196F3","#0F1520"],
    bg: "#0A1018", surface: "#0F1520", border: "#1A2530",
    text: "#B8CCE0", dim: "#5A7090", muted: "#2A3A50",
    accent: "#2196F3", success: "#26A69A", danger: "#EF5350",
    font: "'Righteous', sans-serif", body: "'Nunito Sans', sans-serif", mono: "'DM Mono', monospace",
    card: { borderRadius: "6px", borderBottom: "2px solid #2196F330" },
    f: { deploy:"SET SAIL", abort:"DROP ANCHOR", log:"Captain's Log", queue:"Treasure Map", perf:"Crew Bounties", intel:"Lookout Report" },
  },
  void: {
    name: "Cosmic Void", emoji: "🌌",
    desc: "Final Fantasy · Kingdom Hearts · Space",
    preview: ["#06060F","#7C4DFF","#0E0E1A"],
    bg: "#06060F", surface: "#0E0E1A", border: "#1A1A30",
    text: "#C8C4E0", dim: "#6860A0", muted: "#383458",
    accent: "#7C4DFF", success: "#69F0AE", danger: "#FF5252",
    font: "'Orbitron', sans-serif", body: "'Quicksand', sans-serif", mono: "'Space Mono', monospace",
    card: { borderRadius: "8px", boxShadow: "0 0 15px #7C4DFF08" },
    f: { deploy:"LAUNCH", abort:"RECALL", log:"Star Chart", queue:"Next Warp", perf:"Galaxy Map", intel:"Astral Echoes" },
  },
  ember: {
    name: "Volcanic Ember", emoji: "🌋",
    desc: "Monster Hunter · Dragon's Dogma · Fire",
    preview: ["#100808","#FF5722","#181010"],
    bg: "#100808", surface: "#181010", border: "#2A1A1A",
    text: "#D8C0B0", dim: "#8A6858", muted: "#4A3430",
    accent: "#FF5722", success: "#8BC34A", danger: "#FF5722",
    font: "'Bungee Shade', sans-serif", body: "'Merriweather Sans', sans-serif", mono: "'IBM Plex Mono', monospace",
    card: { borderRadius: "2px", borderBottom: "2px solid #FF572225" },
    f: { deploy:"IGNITE", abort:"QUENCH", log:"Forge Record", queue:"Hunt Board", perf:"Kill Count", intel:"Sage's Warning" },
  },
  clean: {
    name: "Studio Minimal", emoji: "◻️",
    desc: "Clean · Professional · Neutral",
    preview: ["#F8F9FA","#1A1A2E","#FFFFFF"],
    bg: "#F8F9FA", surface: "#FFFFFF", border: "#E8E8EE",
    text: "#1A1A2E", dim: "#6B6B80", muted: "#AAAABB",
    accent: "#1A1A2E", success: "#2E7D32", danger: "#C62828",
    font: "'Sora', sans-serif", body: "'Sora', sans-serif", mono: "'JetBrains Mono', monospace",
    card: { borderRadius: "8px", boxShadow: "0 1px 3px #00000008" },
    f: { deploy:"RUN", abort:"STOP", log:"Activity", queue:"Queue", perf:"Performance", intel:"Suggestions" },
  },
};

const Q = [
  { f:"RE", topic:"Wesker's sunglasses were a rendering trick", s:12.1, n:"Jill" },
  { f:"DS", topic:"Miyazaki couldn't read the English source books", s:13.5, n:"Firekeeper" },
  { f:"OP", topic:"Oda planned the ending from chapter 1", s:13.8, n:"Nami" },
  { f:"AoT", topic:"The world map is inverted real Earth", s:11.2, n:"Eren" },
];
const L = [
  { t:"14:32", l:"PUBLISHED", d:"RE — Did You Know THIS About Chris?" },
  { t:"14:30", l:"GATE PASS", d:"9/9 checks cleared" },
  { t:"14:22", l:"ASSEMBLED", d:"CapCut · 1080×1920 · 48.3s" },
  { t:"13:58", l:"ANIMATED", d:"6 clips · Kling 3.0" },
  { t:"13:45", l:"VOICED", d:"Jill · Chatterbox · 47.2s" },
  { t:"12:10", l:"IMAGED", d:"6 scenes · Flow" },
];
const S = [
  { c:"RE", n:"Resident Evil", v:"128K", t:18, p:92 },
  { c:"OP", n:"One Piece", v:"97K", t:12, p:70 },
  { c:"AoT", n:"Attack on Titan", v:"84K", t:22, p:60 },
  { c:"DS", n:"Dark Souls", v:"62K", t:5, p:45 },
];
const I = [
  { tag:"HOOKS", txt:"Question hooks retain 12% better than bold claims" },
  { tag:"TREND", txt:"AoT trending +22% — consider 2 per week" },
  { tag:"TIME", txt:"18:00 UTC posts get 23% better first-day views" },
  { tag:"VOICE", txt:"Jill outperforms Wesker by 31% in retention" },
];

function Dash({ t: h }) {
  const px = h.font.includes("Press Start");
  const fs = (n) => px ? Math.max(n - 4, 6) : n;
  return (
    <div style={{ background: h.bg, color: h.text, padding: "20px 24px", fontFamily: h.body, minHeight: "70vh" }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-end", marginBottom:"20px", paddingBottom:"12px", borderBottom:`1px solid ${h.border}` }}>
        <div>
          <div style={{ fontSize:fs(9)+"px", fontWeight:700, letterSpacing:"2.5px", color:h.muted, fontFamily:h.mono, marginBottom:"4px" }}>NARRACRAFT</div>
          <h1 style={{ fontSize:fs(22)+"px", fontWeight:700, margin:0, fontFamily:h.font, letterSpacing:"-0.3px" }}>Mission Control</h1>
        </div>
        <button style={{ padding:"9px 20px", border:`1px solid ${h.accent}`, background:`${h.accent}15`, color:h.accent, cursor:"pointer", fontSize:fs(11)+"px", fontWeight:700, letterSpacing:"1.5px", fontFamily:h.mono, boxShadow:`0 0 14px ${h.accent}20` }}>▶ {h.f.deploy}</button>
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:"10px", marginBottom:"18px" }}>
        {[{l:"PUBLISHED",v:"4/5",s:"this week"},{l:"VIEWS",v:"428K",s:"+23%"},{l:"SUBS",v:"+187",s:"1,240 total"},{l:"QUEUE",v:"5",s:"3 ready"}].map((x,i)=>(
          <div key={i} style={{ background:h.surface, padding:"13px 15px", border:`1px solid ${h.border}`, ...h.card }}>
            <div style={{ fontSize:fs(8)+"px", fontWeight:700, letterSpacing:"1.5px", color:h.muted, fontFamily:h.mono, marginBottom:"5px" }}>{x.l}</div>
            <div style={{ fontSize:fs(24)+"px", fontWeight:800, fontFamily:h.font, lineHeight:1 }}>{x.v}</div>
            <div style={{ fontSize:fs(9)+"px", color:h.accent, marginTop:"4px", fontFamily:h.mono }}>{x.s}</div>
          </div>
        ))}
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"12px", marginBottom:"18px" }}>
        <div style={{ background:h.surface, border:`1px solid ${h.border}`, padding:"15px", ...h.card }}>
          <div style={{ fontSize:fs(10)+"px", fontWeight:700, letterSpacing:"1.5px", color:h.dim, fontFamily:h.mono, marginBottom:"10px" }}>{h.f.log.toUpperCase()}</div>
          {L.map((x,i)=>(
            <div key={i} style={{ display:"flex", gap:"8px", padding:"4px 0", borderBottom:i<L.length-1?`1px solid ${h.border}`:"none", alignItems:"center" }}>
              <span style={{ fontSize:fs(9)+"px", color:h.muted, fontFamily:h.mono, width:"32px" }}>{x.t}</span>
              <span style={{ fontSize:fs(7)+"px", fontWeight:700, letterSpacing:"0.8px", padding:"1px 5px", color:h.accent, background:`${h.accent}12`, fontFamily:h.mono }}>{x.l}</span>
              <span style={{ fontSize:fs(10)+"px", color:h.dim, flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{x.d}</span>
            </div>
          ))}
        </div>
        <div style={{ background:h.surface, border:`1px solid ${h.border}`, padding:"15px", ...h.card }}>
          <div style={{ fontSize:fs(10)+"px", fontWeight:700, letterSpacing:"1.5px", color:h.dim, fontFamily:h.mono, marginBottom:"10px" }}>{h.f.queue.toUpperCase()}</div>
          {Q.map((x,i)=>(
            <div key={i} style={{ display:"flex", alignItems:"center", gap:"8px", padding:"7px 4px", borderBottom:i<Q.length-1?`1px solid ${h.border}`:"none" }}>
              <span style={{ fontSize:fs(10)+"px", fontWeight:900, color:h.accent, fontFamily:h.mono, width:"24px" }}>{x.f}</span>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontSize:fs(11)+"px", fontWeight:600, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{x.topic}</div>
                <div style={{ fontSize:fs(8)+"px", color:h.muted, fontFamily:h.mono }}>{x.n} · {x.s}</div>
              </div>
              <div style={{ width:"6px", height:"6px", borderRadius:"50%", background:h.success, boxShadow:`0 0 5px ${h.success}60` }}/>
            </div>
          ))}
        </div>
      </div>

      <div style={{ background:h.surface, border:`1px solid ${h.border}`, padding:"15px", marginBottom:"18px", ...h.card }}>
        <div style={{ fontSize:fs(10)+"px", fontWeight:700, letterSpacing:"1.5px", color:h.dim, fontFamily:h.mono, marginBottom:"10px" }}>{h.f.perf.toUpperCase()}</div>
        {S.map((x,i)=>(
          <div key={i} style={{ display:"flex", alignItems:"center", gap:"10px", padding:"5px 2px" }}>
            <span style={{ fontSize:fs(10)+"px", fontWeight:800, color:h.accent, fontFamily:h.mono, width:"28px" }}>{x.c}</span>
            <span style={{ fontSize:fs(11)+"px", width:"100px", fontWeight:600 }}>{x.n}</span>
            <div style={{ flex:1, height:"4px", background:h.border, overflow:"hidden" }}>
              <div style={{ height:"100%", width:`${x.p}%`, background:`linear-gradient(90deg, ${h.accent}80, ${h.accent}30)`, transition:"width 0.6s" }}/>
            </div>
            <span style={{ fontSize:fs(13)+"px", fontWeight:800, width:"46px", textAlign:"right" }}>{x.v}</span>
            <span style={{ fontSize:fs(8)+"px", color:h.success, width:"32px", fontFamily:h.mono, textAlign:"right" }}>+{x.t}%</span>
          </div>
        ))}
      </div>

      <div style={{ background:h.surface, border:`1px solid ${h.border}`, padding:"15px", ...h.card }}>
        <div style={{ fontSize:fs(10)+"px", fontWeight:700, letterSpacing:"1.5px", color:h.dim, fontFamily:h.mono, marginBottom:"10px" }}>{h.f.intel.toUpperCase()}</div>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"8px" }}>
          {I.map((x,i)=>(
            <div key={i} style={{ padding:"10px 12px", background:`${h.accent}05`, borderLeft:`2px solid ${h.accent}25` }}>
              <div style={{ fontSize:fs(7)+"px", fontWeight:700, letterSpacing:"1.5px", color:h.accent, fontFamily:h.mono, marginBottom:"3px" }}>{x.tag}</div>
              <div style={{ fontSize:fs(10)+"px", color:h.dim, lineHeight:1.55 }}>{x.txt}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ThemeCard({ theme: h, isActive, onClick }) {
  const [hov, setHov] = useState(false);
  return (
    <div onClick={onClick} onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{
        cursor: "pointer", padding: "14px",
        background: isActive ? `${h.accent}12` : hov ? "#ffffff08" : "#0E0E1A",
        border: isActive ? `2px solid ${h.accent}` : "2px solid #1A1A30",
        borderRadius: "10px", transition: "all 0.2s",
        transform: isActive ? "scale(1.02)" : hov ? "scale(1.01)" : "scale(1)",
        boxShadow: isActive ? `0 4px 20px ${h.accent}20` : "none",
      }}>
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px" }}>
        <span style={{ fontSize: "20px" }}>{h.emoji}</span>
        <div>
          <div style={{ fontSize: "13px", fontWeight: 700, color: isActive ? h.accent : "#C8C8D8" }}>{h.name}</div>
          <div style={{ fontSize: "10px", color: "#555570" }}>{h.desc}</div>
        </div>
      </div>
      {/* Color preview strip */}
      <div style={{ display: "flex", gap: "4px", height: "18px", borderRadius: "3px", overflow: "hidden" }}>
        <div style={{ flex: 3, background: h.preview[0] }} />
        <div style={{ flex: 1, background: h.accent }} />
        <div style={{ flex: 2, background: h.preview[2] }} />
        <div style={{ flex: 0.5, background: h.success }} />
      </div>
    </div>
  );
}

export default function App() {
  const [active, setActive] = useState("gothic");
  const [selectorOpen, setSelectorOpen] = useState(true);
  const keys = Object.keys(T);

  return (
    <div style={{ minHeight: "100vh", background: "#08080E", fontFamily: "-apple-system, sans-serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700;800;900&family=Crimson+Text:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500;700&family=Courier+Prime:wght@400;700&family=Source+Sans+3:wght@400;500;600;700&family=Noto+Serif+JP:wght@400;600;700&family=Noto+Sans+JP:wght@400;500;600;700&family=DM+Mono:wght@400;500&family=Press+Start+2P&family=Chakra+Petch:wght@400;500;600;700&family=MedievalSharp&family=Lora:wght@400;500;600;700&family=Fira+Code:wght@400;500;600;700&family=Zen+Dots&family=Nunito:wght@400;600;700;800&family=Righteous&family=Nunito+Sans:wght@400;500;600;700&family=Orbitron:wght@400;500;600;700;800;900&family=Quicksand:wght@400;500;600;700&family=Space+Mono:wght@400;700&family=Bungee+Shade&family=Merriweather+Sans:wght@400;500;600;700&family=Sora:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet" />
      
      {/* Top bar */}
      <div style={{
        position: "sticky", top: 0, zIndex: 100,
        background: "#08080EF0", backdropFilter: "blur(12px)",
        borderBottom: "1px solid #1A1A2E", padding: "10px 24px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{
            fontSize: "10px", fontWeight: 700, letterSpacing: "2px",
            color: "#555", fontFamily: "monospace",
          }}>NARRACRAFT — THEME PREVIEW</div>
        </div>
        <button onClick={() => setSelectorOpen(o => !o)} style={{
          padding: "6px 14px", background: selectorOpen ? T[active].accent : "#1A1A30",
          color: selectorOpen ? "#000" : "#888",
          border: "none", borderRadius: "6px", cursor: "pointer",
          fontSize: "11px", fontWeight: 700,
          fontFamily: "-apple-system, sans-serif",
        }}>
          {selectorOpen ? "Hide Themes" : `🎨 ${T[active].name} — Change Theme`}
        </button>
      </div>

      {/* Theme selector grid */}
      {selectorOpen && (
        <div style={{
          padding: "16px 24px 8px",
          background: "#0A0A14",
          borderBottom: "1px solid #1A1A2E",
        }}>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: "8px",
          }}>
            {keys.map(k => (
              <ThemeCard key={k} theme={T[k]} isActive={active === k} onClick={() => setActive(k)} />
            ))}
          </div>
        </div>
      )}

      {/* Dashboard with active theme */}
      <Dash t={T[active]} />
    </div>
  );
}

import { useState } from "react";

const PRE_PRODUCTION = [
  {
    id: "asset_library",
    label: "0. ASSET LIBRARY",
    subtitle: "Generate & Approve All Visual Assets",
    tool: "Google Flow (Nano Banana 2)",
    integration: "Playwright + Manual Approval",
    icon: "🎭",
    color: "#FF6B9D",
    inputs: [
      "Franchise registry (characters, environments, props)",
      "Source reference images (official art — private, never published)",
      "Character bibles (text descriptions)",
      "Franchise visual style settings",
    ],
    outputs: [
      "Approved character model sheets (portrait + full body + expressions)",
      "Approved environment images (wide shot + detail + angle variants)",
      "Approved prop images (iconic items)",
      "All persisted in assets/library/{franchise_id}/",
    ],
    logic: [
      "ONE-TIME per franchise — run before any videos are made",
      "All assets are PERMANENT — generate once, approve once, reuse forever",
      "",
      "CHARACTERS (per archetype):",
      "→ Upload source ref images to Flow as visual anchor",
      "→ Generate portrait (locks the face for all future videos)",
      "→ Generate full body (locks outfit + proportions)",
      "→ Generate expression sheet: neutral, angry, smiling, surprised",
      "→ Save to assets/library/{franchise}/{archetype}/",
      "",
      "ENVIRONMENTS (per location):",
      "→ Upload source ref of the game location to Flow",
      "→ Generate wide establishing shot (photorealistic, no characters)",
      "→ Generate close-up / detail variants",
      "→ Generate different angles or lighting variations",
      "→ Save to assets/library/{franchise}/environments/{env_id}/",
      "",
      "PROPS (per iconic item):",
      "→ Generate clean image of item on neutral background",
      "→ Save to assets/library/{franchise}/props/{prop_id}/",
      "",
      "APPROVAL:",
      "→ Review every generated asset manually",
      "→ Set reference_status: 'approved' in franchise registry",
      "→ NEVER regenerate approved assets — consistency depends on it",
      "→ Pipeline halts if any required asset is missing or unapproved",
    ],
    decision: {
      pass: "All assets locked → ready for video production",
      fail: "Regenerate → refine prompts or source refs",
    },
  },
];

const PRODUCTION = [
  {
    id: "research",
    label: "1. RESEARCH",
    subtitle: "Topic Discovery",
    tool: "Franchise Registry + Web Search",
    integration: "Local DB + Browser",
    icon: "🔍",
    color: "#E8B931",
    inputs: ["Franchise Registry (YAML)", "Topic history DB", "Web search results"],
    outputs: ["Selected franchise", "Selected topic seed", "Research notes"],
    logic: [
      "Pick franchise based on rotation rules (min 5 gap, max 2/week)",
      "Select unused topic seed OR discover new topic via web search",
      "Check topic_history.db — skip if already covered",
      "Output: franchise_id + topic + character_archetypes needed",
    ],
    decision: null,
  },
  {
    id: "script",
    label: "2. SCRIPT",
    subtitle: "In-Character Narrator Script",
    tool: "Gemini (Web UI)",
    integration: "Playwright Browser Automation",
    icon: "✍️",
    color: "#4A9BD9",
    inputs: [
      "Topic + franchise context",
      "Narrator archetype + personality profile",
      "Character bibles for all characters in topic",
      "System prompt template",
    ],
    outputs: [
      "In-character dialogue (narrator speaks AS the character)",
      "Scene breakdown with shot types per segment",
      "Per-scene: shot_type, narrator_expression, action_characters, environment",
      "Title + description + tags",
    ],
    logic: [
      "Load narrator personality (tone, speech style, how they refer to others)",
      "Build prompt: system prompt + narrator persona + topic + character bibles",
      "Instruct LLM: write dialogue AS the narrator character, not neutral",
      "Example output: 'Did you know? My partner was not supposed to be this buffed.'",
      "Each scene specifies shot_type:",
      "→ narrator_with_characters (narrator foreground + others behind)",
      "→ narrator_alone (close-up, speaking to camera)",
      "→ characters_only (narrator not visible, voice-over action)",
      "Rule: first scene MUST be narrator_with_characters",
      "Rule: vary shot types — never 3+ of same type in a row",
      "Validate word count (100–155 words) and structure",
      "Store script + embedding in scripts.db",
    ],
    decision: null,
  },
  {
    id: "compliance",
    label: "3. COMPLIANCE",
    subtitle: "Pre-Production Check",
    tool: "Gemini (Web UI) + Local Similarity",
    integration: "Playwright + Python",
    icon: "🛡️",
    color: "#E85D3A",
    inputs: [
      "Generated script",
      "Last 100 scripts (embeddings)",
      "Advertiser-friendly rules",
    ],
    outputs: [
      "PASS → continue to production",
      "FAIL → quarantine + regenerate",
    ],
    logic: [
      "Similarity check: cosine similarity vs last 100 scripts (threshold: 0.70)",
      "Unique words ratio check (min 40%)",
      "Send script to Gemini: 'Is this advertiser-friendly?'",
      "Check for copyrighted character names or direct references",
      "Validate duration estimate (words ÷ 2.8 wps)",
    ],
    decision: { pass: "Continue → Scene Images", fail: "Quarantine → Regenerate" },
  },
  {
    id: "voice_and_images",
    label: "4. VOICE + IMAGES",
    subtitle: "Parallel: Voiceover + Scene Images",
    tool: "Chatterbox (local) + Google Flow (browser)",
    integration: "Local Python + Playwright (parallel)",
    icon: "🎙️🎨",
    color: "#9B59B6",
    inputs: [
      "Full script text + scene breakdown",
      "Voice reference audio (10–30s WAV)",
      "Narrator model sheets (front-facing assets)",
      "Action character models (from asset library)",
      "Approved environments + props",
    ],
    outputs: [
      "Full voiceover audio (WAV)",
      "Audio segments split per scene with timestamps",
      "Narrator scene images (front-facing for lip sync)",
      "Action scene images (characters doing things)",
      "Mixed scene images (narrator + characters together)",
    ],
    logic: [
      "These two run in PARALLEL (voice is local, images need browser):",
      "",
      "VOICE (local GPU — no browser needed):",
      "→ Generate full voiceover from complete script",
      "→ Use narrator's voice reference for cloning",
      "→ Extract word-level timestamps",
      "→ Split audio into segments per scene",
      "→ Validate total duration (45–55s)",
      "",
      "IMAGES (Playwright → Google Flow):",
      "→ For narrator_with_characters scenes:",
      "   Upload narrator front-facing asset + character models + environment",
      "→ For narrator_alone scenes:",
      "   Upload narrator front-facing asset + environment",
      "→ For characters_only scenes:",
      "   Upload action character models + environment",
      "→ Generate 4 variants per scene, pick best",
      "→ Use lasso edit for face/detail fixes",
      "",
      "Wait for BOTH to complete before step 5",
    ],
    decision: null,
  },
  {
    id: "video_clips",
    label: "5. ANIMATE",
    subtitle: "Lip Sync + Action Clips",
    tool: "Kling AI (Web UI)",
    integration: "Playwright Browser Automation",
    icon: "🎬",
    color: "#2ECC71",
    inputs: [
      "Scene images (from step 4)",
      "Audio segments per scene (from step 4)",
      "Character model sheets (for Kling Elements)",
      "Shot type per scene (from script breakdown)",
    ],
    outputs: [
      "Narrator clips WITH lip sync (mouth matches audio)",
      "Action clips with motion only (no lip sync)",
      "5–6 clips total, 3–5s each",
    ],
    logic: [
      "REQUIRES both voice + images completed first",
      "",
      "For each scene, generate clip based on shot_type:",
      "",
      "→ narrator_with_characters or narrator_alone:",
      "   Upload scene image + audio segment to Kling",
      "   Use Kling LIP SYNC mode (image + audio → speaking video)",
      "   Character's mouth animated to match the voiceover",
      "",
      "→ characters_only:",
      "   Upload scene image only (no audio)",
      "   Use Kling MOTION mode (subtle animation, no lip sync)",
      "   Narrator voice plays over this in final assembly",
      "",
      "Upload character models via Elements for identity lock",
      "Budget: max 6 clips × 10 credits = 60 of 66 daily",
    ],
    decision: null,
  },
  {
    id: "assembly",
    label: "6. ASSEMBLE",
    subtitle: "Video Assembly in CapCut",
    tool: "VectCutAPI → CapCut",
    integration: "HTTP API + Local Render",
    icon: "🔧",
    color: "#1ABC9C",
    inputs: [
      "Narrator clips (lip synced) + Action clips (motion only)",
      "Full voiceover audio (for characters_only scenes)",
      "Word timestamps (for subtitle generation)",
      "Background music track",
      "SFX library",
      "Caption style config",
    ],
    outputs: ["CapCut draft project", "Final rendered MP4 (1080×1920)"],
    logic: [
      "Create VectCutAPI draft (1080×1920, 30fps)",
      "Add video clips to timeline (scene order)",
      "Add voiceover audio track synced to start",
      "Generate SRT from timestamps → add styled subtitles",
      "Add background music (volume 0.08) with fades",
      "Add randomized transitions between clips",
      "Add keyframe animations (zoom, pan) to clips",
      "Add SFX triggers (whoosh on hook, ding on reveal)",
      "Save draft → copy to CapCut drafts folder",
      "Render in CapCut desktop",
    ],
    decision: null,
  },
  {
    id: "quality",
    label: "7. QUALITY GATE",
    subtitle: "Final Pre-Publish Check",
    tool: "Automated Checklist",
    integration: "Python",
    icon: "✅",
    color: "#E74C3C",
    inputs: ["Final rendered video", "Script", "Metadata", "Upload history"],
    outputs: ["APPROVED → publish", "REJECTED → quarantine"],
    logic: [
      "□ Script is original (similarity passed)",
      "□ Voiceover present and > 10 seconds",
      "□ Visuals varied (template check)",
      "□ No copyrighted material",
      "□ Advertiser-friendly (filter passed)",
      "□ Duration < 60 seconds",
      "□ Title + description + tags complete",
      "□ Structure differs from last 5 uploads",
      "□ Upload pattern not bot-like",
    ],
    decision: { pass: "Approved → Publish", fail: "Rejected → Quarantine" },
  },
  {
    id: "publish",
    label: "8. PUBLISH",
    subtitle: "Multi-Platform Distribution",
    tool: "YouTube API + Playwright (TikTok, IG, FB)",
    integration: "API + Browser Automation",
    icon: "📤",
    color: "#FF0000",
    inputs: [
      "Final MP4",
      "Platform-specific metadata (titles, captions, hashtags)",
      "Long-form outline (saved for future production)",
      "Schedule config",
    ],
    outputs: [
      "Published YouTube Short + pinned comment with CTA",
      "Published TikTok video",
      "Published Instagram Reel (if enabled)",
      "Published Facebook Reel (if enabled)",
      "Long-form outline saved to queue",
      "Upload log entries per platform",
    ],
    logic: [
      "Check schedule: respect cooldown (6h between uploads)",
      "Add time jitter (±30 min) to seem natural",
      "",
      "YOUTUBE (primary):",
      "→ Upload via YouTube Data API",
      "→ Set visibility, category, language, made_for_kids=false",
      "→ Add pinned comment with long-form CTA",
      "",
      "TIKTOK (browser automation):",
      "→ Upload same MP4 via Playwright → TikTok web upload",
      "→ Set TikTok-specific caption + hashtags (#fyp etc.)",
      "",
      "INSTAGRAM / FACEBOOK (if enabled):",
      "→ Upload via Playwright → respective web UIs",
      "",
      "LONG-FORM FUNNEL:",
      "→ Save long-form outline to data/long_form_outlines/",
      "→ This is the real revenue driver (10-50x Shorts RPM)",
      "→ User produces long-form videos separately",
      "",
      "Log: timestamp, video_id per platform, franchise, topic",
      "Update topic_history.db (mark as used)",
    ],
    decision: null,
  },
];

const STORES = [
  { icon: "📋", name: "config-schema.yaml", desc: "Pipeline & tool config" },
  { icon: "🎮", name: "franchise-registry.yaml", desc: "Franchises, characters, topics" },
  { icon: "👤", name: "assets/library/", desc: "All visual assets" },
  { icon: "🖼️", name: "assets/source_refs/", desc: "Official art (private)" },
  { icon: "🗄️", name: "scripts.db", desc: "Script history + embeddings" },
  { icon: "📦", name: "assets.db", desc: "Used asset tracking" },
  { icon: "📜", name: "topic_history.db", desc: "Topic deduplication" },
  { icon: "🎵", name: "assets/music/", desc: "Royalty-free audio" },
  { icon: "📁", name: "browser_data/", desc: "Playwright sessions" },
  { icon: "📝", name: "long_form_outlines/", desc: "Deep dive outlines" },
];

function DetailSection({ title, color, items }) {
  return (
    <div style={{ marginBottom: "14px" }}>
      <div
        style={{
          fontSize: "9px",
          fontWeight: 800,
          letterSpacing: "1.5px",
          color,
          marginBottom: "6px",
          fontFamily: "monospace",
        }}
      >
        {title}
      </div>
      {items.map((item, i) => (
        <div
          key={i}
          style={{
            fontSize: "12px",
            color: item === ""
              ? "transparent"
              : item.startsWith("→")
              ? "#888"
              : item.startsWith("□")
              ? "#bbb"
              : "#ccc",
            paddingLeft: item.startsWith("→") ? "14px" : "0",
            lineHeight: item === "" ? 0.8 : 1.7,
            fontFamily:
              item.startsWith("→") || item.startsWith("□") || item.startsWith("Step")
                ? "monospace"
                : "inherit",
            fontWeight: item.startsWith("Step") ? 700 : 400,
          }}
        >
          {item || "\u00A0"}
        </div>
      ))}
    </div>
  );
}

function ModuleBlock({ mod, isOpen, onToggle, isLast, phaseColor }) {
  const hasDecision = mod.decision !== null;
  const borderColor = isOpen ? mod.color : "#252540";

  return (
    <div>
      <div
        onClick={onToggle}
        style={{
          background: isOpen ? `${mod.color}10` : "#161625",
          border: `2px solid ${borderColor}`,
          borderRadius: isOpen ? "10px 10px 0 0" : hasDecision ? "14px" : "10px",
          padding: "14px 16px",
          cursor: "pointer",
          transition: "border-color 0.2s, background 0.2s",
          position: "relative",
          WebkitTapHighlightColor: "transparent",
        }}
      >
        {hasDecision && (
          <div
            style={{
              position: "absolute",
              top: "-7px",
              right: "12px",
              fontSize: "8px",
              fontWeight: 800,
              padding: "2px 7px",
              borderRadius: "4px",
              background: mod.color,
              color: "#000",
              letterSpacing: "1px",
              fontFamily: "monospace",
            }}
          >
            GATE
          </div>
        )}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              flex: 1,
              minWidth: 0,
            }}
          >
            <span style={{ fontSize: "20px", flexShrink: 0 }}>{mod.icon}</span>
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  fontSize: "10px",
                  fontWeight: 800,
                  letterSpacing: "1.2px",
                  color: mod.color,
                  fontFamily: "monospace",
                }}
              >
                {mod.label}
              </div>
              <div
                style={{
                  fontSize: "14px",
                  fontWeight: 600,
                  color: "#ddd",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {mod.subtitle}
              </div>
            </div>
          </div>
          <span
            style={{
              fontSize: "16px",
              color: "#555",
              transition: "transform 0.2s",
              transform: isOpen ? "rotate(180deg)" : "rotate(0)",
              flexShrink: 0,
              marginLeft: "8px",
            }}
          >
            ▾
          </span>
        </div>
        <div
          style={{
            display: "flex",
            gap: "5px",
            marginTop: "8px",
            flexWrap: "wrap",
          }}
        >
          <span
            style={{
              fontSize: "9px",
              padding: "2px 7px",
              borderRadius: "5px",
              background: `${mod.color}18`,
              color: mod.color,
              fontFamily: "monospace",
              fontWeight: 700,
            }}
          >
            {mod.tool}
          </span>
          <span
            style={{
              fontSize: "9px",
              padding: "2px 7px",
              borderRadius: "5px",
              background: "#ffffff08",
              color: "#666",
              fontFamily: "monospace",
            }}
          >
            {mod.integration}
          </span>
        </div>
      </div>

      {isOpen && (
        <div
          style={{
            background: "#111122",
            border: `1px solid ${mod.color}30`,
            borderTop: "none",
            borderRadius: "0 0 10px 10px",
            padding: "16px",
            marginTop: "-2px",
          }}
        >
          <DetailSection title="INPUTS" color="#4A9BD9" items={mod.inputs} />
          <DetailSection title="OUTPUTS" color="#2ECC71" items={mod.outputs} />
          <DetailSection title="LOGIC / STEPS" color={mod.color} items={mod.logic} />
          {mod.decision && (
            <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
              <div
                style={{
                  flex: 1,
                  padding: "10px",
                  borderRadius: "8px",
                  background: "#2ECC7112",
                  border: "1px solid #2ECC7130",
                  textAlign: "center",
                }}
              >
                <div style={{ fontSize: "14px" }}>✅</div>
                <div
                  style={{
                    fontSize: "10px",
                    color: "#2ECC71",
                    fontWeight: 700,
                    fontFamily: "monospace",
                    marginTop: "4px",
                  }}
                >
                  {mod.decision.pass}
                </div>
              </div>
              <div
                style={{
                  flex: 1,
                  padding: "10px",
                  borderRadius: "8px",
                  background: "#E74C3C12",
                  border: "1px solid #E74C3C30",
                  textAlign: "center",
                }}
              >
                <div style={{ fontSize: "14px" }}>❌</div>
                <div
                  style={{
                    fontSize: "10px",
                    color: "#E74C3C",
                    fontWeight: 700,
                    fontFamily: "monospace",
                    marginTop: "4px",
                  }}
                >
                  {mod.decision.fail}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {!isLast && (
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            height: "22px",
            position: "relative",
          }}
        >
          <div
            style={{
              width: "2px",
              height: "100%",
              background: hasDecision
                ? "linear-gradient(to bottom, #2ECC71, #2ECC7140)"
                : `linear-gradient(to bottom, ${mod.color}50, ${mod.color}15)`,
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: 0,
              width: 0,
              height: 0,
              borderLeft: "5px solid transparent",
              borderRight: "5px solid transparent",
              borderTop: `6px solid ${hasDecision ? "#2ECC71" : mod.color}60`,
            }}
          />
        </div>
      )}
    </div>
  );
}

function PhaseHeader({ title, subtitle, color, icon }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "12px 16px",
        marginBottom: "8px",
        marginTop: "20px",
        background: `${color}08`,
        borderLeft: `3px solid ${color}`,
        borderRadius: "0 8px 8px 0",
      }}
    >
      <span style={{ fontSize: "18px" }}>{icon}</span>
      <div>
        <div
          style={{
            fontSize: "12px",
            fontWeight: 800,
            color: color,
            letterSpacing: "1.5px",
            fontFamily: "monospace",
          }}
        >
          {title}
        </div>
        <div style={{ fontSize: "11px", color: "#777" }}>{subtitle}</div>
      </div>
    </div>
  );
}

export default function PipelineDiagram() {
  const [openId, setOpenId] = useState(null);
  const toggle = (id) => setOpenId(openId === id ? null : id);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0c0c18",
        color: "#e0e0e0",
        padding: "20px 12px",
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      }}
    >
      <div style={{ maxWidth: "540px", margin: "0 auto" }}>
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "16px" }}>
          <div
            style={{
              fontSize: "9px",
              fontWeight: 800,
              letterSpacing: "3px",
              color: "#555",
              marginBottom: "6px",
              fontFamily: "monospace",
            }}
          >
            YOUTUBE SHORTS AUTOMATION
          </div>
          <h1 style={{ fontSize: "22px", fontWeight: 700, color: "#fff", margin: "0 0 6px" }}>
            Pipeline Workflow
          </h1>
          <p style={{ fontSize: "11px", color: "#555", margin: 0, fontFamily: "monospace" }}>
            2 phases · 9 modules · free tools · tap to expand
          </p>
        </div>

        {/* PHASE 1: PRE-PRODUCTION */}
        <PhaseHeader
          title="PHASE 1 — PRE-PRODUCTION"
          subtitle="One-time setup per character (before any videos)"
          color="#FF6B9D"
          icon="🎭"
        />
        {PRE_PRODUCTION.map((mod, i) => (
          <ModuleBlock
            key={mod.id}
            mod={mod}
            isOpen={openId === mod.id}
            onToggle={() => toggle(mod.id)}
            isLast={true}
          />
        ))}

        {/* Phase separator */}
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            height: "40px",
            position: "relative",
          }}
        >
          <div
            style={{
              width: "2px",
              height: "100%",
              background: "linear-gradient(to bottom, #FF6B9D40, #E8B93140)",
            }}
          />
          <div
            style={{
              position: "absolute",
              background: "#0c0c18",
              padding: "2px 10px",
              fontSize: "9px",
              fontWeight: 800,
              color: "#555",
              fontFamily: "monospace",
              letterSpacing: "1px",
            }}
          >
            models ready
          </div>
        </div>

        {/* PHASE 2: PER-VIDEO PRODUCTION */}
        <PhaseHeader
          title="PHASE 2 — PER-VIDEO PRODUCTION"
          subtitle="Automated pipeline (runs for each Short)"
          color="#E8B931"
          icon="🔄"
        />
        {PRODUCTION.map((mod, i) => (
          <ModuleBlock
            key={mod.id}
            mod={mod}
            isOpen={openId === mod.id}
            onToggle={() => toggle(mod.id)}
            isLast={i === PRODUCTION.length - 1}
          />
        ))}

        {/* Data stores */}
        <div
          style={{
            marginTop: "28px",
            padding: "14px",
            background: "#111122",
            borderRadius: "10px",
            border: "1px solid #252540",
          }}
        >
          <div
            style={{
              fontSize: "9px",
              fontWeight: 800,
              letterSpacing: "2px",
              color: "#555",
              marginBottom: "10px",
              fontFamily: "monospace",
            }}
          >
            DATA STORES & SHARED RESOURCES
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(145px, 1fr))",
              gap: "6px",
            }}
          >
            {STORES.map((s) => (
              <div
                key={s.name}
                style={{
                  padding: "8px 10px",
                  borderRadius: "7px",
                  background: "#161625",
                  border: "1px solid #252540",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <span style={{ fontSize: "14px", flexShrink: 0 }}>{s.icon}</span>
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: "9px",
                      fontWeight: 700,
                      color: "#bbb",
                      fontFamily: "monospace",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {s.name}
                  </div>
                  <div style={{ fontSize: "9px", color: "#555" }}>{s.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

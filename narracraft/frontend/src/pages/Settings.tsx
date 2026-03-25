import { useState } from "react";
import { useTheme } from "@/components/ThemeProvider";
import { themes, themeIds, type Theme } from "@/themes/themes";

function ThemeCard({
  theme: h,
  isActive,
  onClick,
}: {
  theme: Theme;
  isActive: boolean;
  onClick: () => void;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="cursor-pointer transition-all"
      style={{
        padding: 14,
        background: isActive ? `${h.accent}12` : hovered ? "#ffffff08" : h.surface,
        border: isActive ? `2px solid ${h.accent}` : `2px solid ${h.border}`,
        borderRadius: 10,
        transform: isActive ? "scale(1.02)" : hovered ? "scale(1.01)" : "scale(1)",
        boxShadow: isActive ? `0 4px 20px ${h.accent}20` : "none",
      }}
    >
      <div className="flex items-center gap-2.5 mb-2.5">
        <span className="text-xl">{h.emoji}</span>
        <div>
          <div
            className="text-[13px] font-bold"
            style={{ color: isActive ? h.accent : h.text }}
          >
            {h.name}
          </div>
          <div className="text-[10px]" style={{ color: h.dim }}>
            {h.desc}
          </div>
        </div>
      </div>
      {/* Color preview strip */}
      <div className="flex gap-1 h-[18px] rounded overflow-hidden">
        <div className="flex-[3]" style={{ background: h.preview[0] }} />
        <div className="flex-[1]" style={{ background: h.accent }} />
        <div className="flex-[2]" style={{ background: h.preview[2] }} />
        <div className="flex-[0.5]" style={{ background: h.success }} />
      </div>
    </div>
  );
}

export default function Settings() {
  const { theme, themeId, setThemeId } = useTheme();

  return (
    <div className="flex-1 p-5" style={{ fontFamily: theme.body }}>
      <h1
        className="m-0 mb-6"
        style={{
          fontSize: 22,
          fontWeight: 700,
          fontFamily: theme.font,
          color: theme.text,
        }}
      >
        Settings
      </h1>

      {/* Theme Picker */}
      <section className="mb-8">
        <h2
          className="mb-4"
          style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "2px",
            color: theme.dim,
            fontFamily: theme.mono,
          }}
        >
          THEME
        </h2>
        <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
          {themeIds.map((id) => (
            <ThemeCard
              key={id}
              theme={themes[id]}
              isActive={themeId === id}
              onClick={() => setThemeId(id)}
            />
          ))}
        </div>
      </section>

      {/* Voice Provider */}
      <section className="mb-8">
        <h2
          className="mb-4"
          style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "2px",
            color: theme.dim,
            fontFamily: theme.mono,
          }}
        >
          VOICE PROVIDER
        </h2>
        <div className="flex gap-3">
          {[
            { id: "chatterbox", name: "Chatterbox", desc: "Local \u00B7 Free \u00B7 Needs GPU" },
            { id: "elevenlabs", name: "ElevenLabs", desc: "Browser automation \u00B7 Best quality" },
          ].map((p) => (
            <div
              key={p.id}
              className="p-4 cursor-pointer transition-all"
              style={{
                background: theme.surface,
                border: `1px solid ${theme.border}`,
                borderRadius: theme.card.borderRadius,
                opacity: 0.6,
              }}
            >
              <div
                className="text-sm font-bold mb-1"
                style={{ color: theme.text }}
              >
                {p.name}
              </div>
              <div className="text-xs" style={{ color: theme.dim }}>
                {p.desc}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Browser Accounts placeholder */}
      <section className="mb-8">
        <h2
          className="mb-4"
          style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "2px",
            color: theme.dim,
            fontFamily: theme.mono,
          }}
        >
          BROWSER ACCOUNTS
        </h2>
        <div
          className="p-4"
          style={{
            background: theme.surface,
            border: `1px solid ${theme.border}`,
            borderRadius: theme.card.borderRadius,
          }}
        >
          <p className="text-sm" style={{ color: theme.dim }}>
            Browser account configuration will be available in Phase 3.
          </p>
        </div>
      </section>
    </div>
  );
}

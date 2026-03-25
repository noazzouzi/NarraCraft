/**
 * Command Palette (Cmd+K / Ctrl+K)
 *
 * Quick-access overlay for searching franchises, topics, and triggering actions.
 * Theme-aware, keyboard-navigable.
 */

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "@/components/ThemeProvider";
import {
  LayoutDashboard,
  Gamepad2,
  ImageIcon,
  Search,
  ListTodo,
  Play,
  BarChart3,
  Settings,
  Zap,
  RefreshCw,
  type LucideIcon,
} from "lucide-react";

interface PaletteItem {
  id: string;
  label: string;
  section: string;
  icon: LucideIcon;
  action: () => void;
  keywords?: string;
}

export function CommandPalette() {
  const { theme } = useTheme();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Build item list
  const items: PaletteItem[] = useMemo(
    () => [
      // Navigation
      { id: "nav-dashboard", label: "Dashboard", section: "Navigation", icon: LayoutDashboard, action: () => navigate("/"), keywords: "home mission control" },
      { id: "nav-franchises", label: "Franchises", section: "Navigation", icon: Gamepad2, action: () => navigate("/franchises"), keywords: "onboarding setup" },
      { id: "nav-assets", label: "Asset Library", section: "Navigation", icon: ImageIcon, action: () => navigate("/assets"), keywords: "characters images visuals" },
      { id: "nav-discover", label: "Topic Discovery", section: "Navigation", icon: Search, action: () => navigate("/discover"), keywords: "topics find search" },
      { id: "nav-queue", label: "Topic Queue", section: "Navigation", icon: ListTodo, action: () => navigate("/queue"), keywords: "kanban board" },
      { id: "nav-pipeline", label: "Pipeline", section: "Navigation", icon: Play, action: () => navigate("/pipeline"), keywords: "run generate video" },
      { id: "nav-analytics", label: "Analytics", section: "Navigation", icon: BarChart3, action: () => navigate("/analytics"), keywords: "stats performance charts" },
      { id: "nav-settings", label: "Settings", section: "Navigation", icon: Settings, action: () => navigate("/settings"), keywords: "config theme voice" },

      // Actions
      {
        id: "act-run-pipeline",
        label: "Run Pipeline",
        section: "Actions",
        icon: Zap,
        action: () => {
          navigate("/pipeline");
          fetch("/api/pipeline/run", { method: "POST" }).catch(() => {});
        },
        keywords: "start generate video create",
      },
      {
        id: "act-collect-analytics",
        label: "Collect Analytics",
        section: "Actions",
        icon: RefreshCw,
        action: () => {
          fetch("/api/analytics/collect", { method: "POST" }).catch(() => {});
        },
        keywords: "refresh metrics youtube",
      },
      {
        id: "act-feedback-loop",
        label: "Run Feedback Loop",
        section: "Actions",
        icon: RefreshCw,
        action: () => {
          fetch("/api/analytics/feedback", { method: "POST" }).catch(() => {});
        },
        keywords: "recalculate scoring weights",
      },
    ],
    [navigate],
  );

  // Filter items
  const filtered = useMemo(() => {
    if (!query.trim()) return items;
    const q = query.toLowerCase();
    return items.filter(
      (item) =>
        item.label.toLowerCase().includes(q) ||
        item.section.toLowerCase().includes(q) ||
        (item.keywords && item.keywords.includes(q)),
    );
  }, [items, query]);

  // Group by section
  const grouped = useMemo(() => {
    const groups: Record<string, PaletteItem[]> = {};
    for (const item of filtered) {
      if (!groups[item.section]) groups[item.section] = [];
      groups[item.section].push(item);
    }
    return groups;
  }, [filtered]);

  // Keyboard shortcut to open
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Clamp selected index
  useEffect(() => {
    if (selectedIndex >= filtered.length) {
      setSelectedIndex(Math.max(0, filtered.length - 1));
    }
  }, [filtered.length, selectedIndex]);

  const execute = useCallback(
    (item: PaletteItem) => {
      setOpen(false);
      item.action();
    },
    [],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (filtered[selectedIndex]) {
          execute(filtered[selectedIndex]);
        }
      }
    },
    [filtered, selectedIndex, execute],
  );

  // Scroll selected into view
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-index="${selectedIndex}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  if (!open) return null;

  const h = theme;
  const isPx = h.font.includes("Press Start");
  const fs = (n: number) => (isPx ? Math.max(n - 4, 6) : n);

  let flatIndex = -1;

  return (
    <>
      {/* Backdrop */}
      <div
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.5)",
          zIndex: 9998,
          backdropFilter: "blur(2px)",
        }}
        onClick={() => setOpen(false)}
      />

      {/* Palette */}
      <div
        style={{
          position: "fixed",
          top: "20%",
          left: "50%",
          transform: "translateX(-50%)",
          width: 520,
          maxHeight: "60vh",
          display: "flex",
          flexDirection: "column",
          background: h.surface,
          border: `1px solid ${h.border}`,
          borderRadius: h.card.borderRadius,
          boxShadow: `0 20px 60px rgba(0,0,0,0.5)`,
          zIndex: 9999,
          overflow: "hidden",
        }}
      >
        {/* Input */}
        <div style={{ padding: "12px 16px", borderBottom: `1px solid ${h.border}` }}>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search..."
            style={{
              width: "100%",
              background: "transparent",
              border: "none",
              outline: "none",
              color: h.text,
              fontSize: fs(14),
              fontFamily: h.body,
            }}
          />
        </div>

        {/* Results */}
        <div ref={listRef} style={{ overflowY: "auto", padding: "8px 0" }}>
          {filtered.length === 0 ? (
            <div style={{ padding: "16px", textAlign: "center", color: h.muted, fontFamily: h.mono, fontSize: fs(11) }}>
              No results found
            </div>
          ) : (
            Object.entries(grouped).map(([section, sectionItems]) => (
              <div key={section}>
                <div
                  style={{
                    padding: "6px 16px",
                    fontSize: fs(9),
                    fontWeight: 700,
                    letterSpacing: "1.5px",
                    color: h.muted,
                    fontFamily: h.mono,
                  }}
                >
                  {section.toUpperCase()}
                </div>
                {sectionItems.map((item) => {
                  flatIndex++;
                  const idx = flatIndex;
                  const isSelected = idx === selectedIndex;
                  const Icon = item.icon;

                  return (
                    <div
                      key={item.id}
                      data-index={idx}
                      onClick={() => execute(item)}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        padding: "8px 16px",
                        cursor: "pointer",
                        background: isSelected ? `${h.accent}15` : "transparent",
                        color: isSelected ? h.accent : h.dim,
                        fontFamily: h.body,
                        fontSize: fs(13),
                        transition: "background 0.1s",
                      }}
                    >
                      <Icon size={16} style={{ opacity: 0.7, flexShrink: 0 }} />
                      <span style={{ fontWeight: isSelected ? 600 : 400 }}>{item.label}</span>
                    </div>
                  );
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "8px 16px",
            borderTop: `1px solid ${h.border}`,
            display: "flex",
            gap: 12,
            fontSize: fs(9),
            color: h.muted,
            fontFamily: h.mono,
          }}
        >
          <span><kbd style={{ padding: "1px 4px", background: `${h.accent}10`, borderRadius: 2 }}>↑↓</kbd> navigate</span>
          <span><kbd style={{ padding: "1px 4px", background: `${h.accent}10`, borderRadius: 2 }}>↵</kbd> select</span>
          <span><kbd style={{ padding: "1px 4px", background: `${h.accent}10`, borderRadius: 2 }}>esc</kbd> close</span>
        </div>
      </div>
    </>
  );
}

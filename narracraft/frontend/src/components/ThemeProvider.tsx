import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { themes, GOOGLE_FONTS_URL, type Theme } from "@/themes/themes";

interface ThemeContextValue {
  theme: Theme;
  themeId: string;
  setThemeId: (id: string) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

/** Apply a theme's CSS custom properties to :root. */
function applyTheme(theme: Theme) {
  const root = document.documentElement;

  root.style.setProperty("--nc-bg", theme.bg);
  root.style.setProperty("--nc-surface", theme.surface);
  root.style.setProperty("--nc-border", theme.border);
  root.style.setProperty("--nc-text", theme.text);
  root.style.setProperty("--nc-dim", theme.dim);
  root.style.setProperty("--nc-muted", theme.muted);
  root.style.setProperty("--nc-accent", theme.accent);
  root.style.setProperty("--nc-success", theme.success);
  root.style.setProperty("--nc-danger", theme.danger);

  root.style.setProperty("--nc-font-display", theme.font);
  root.style.setProperty("--nc-font-body", theme.body);
  root.style.setProperty("--nc-font-mono", theme.mono);

  root.style.setProperty("--nc-card-radius", theme.card.borderRadius);

  // Update color-scheme for light themes
  root.style.colorScheme = theme.isLight ? "light" : "dark";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [themeId, setThemeIdState] = useState<string>(() => {
    return localStorage.getItem("nc-theme") || "gothic";
  });

  const theme = themes[themeId] ?? themes.gothic;

  const setThemeId = useCallback((id: string) => {
    if (themes[id]) {
      setThemeIdState(id);
      localStorage.setItem("nc-theme", id);

      // Also persist to backend
      fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_theme: id }),
      }).catch(() => {
        // Silently fail — theme is already saved to localStorage
      });
    }
  }, []);

  // Apply theme CSS variables whenever theme changes
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // Load Google Fonts once
  useEffect(() => {
    if (!document.querySelector('link[data-nc-fonts]')) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = GOOGLE_FONTS_URL;
      link.setAttribute("data-nc-fonts", "true");
      document.head.appendChild(link);
    }
  }, []);

  // Sync theme from backend settings on mount
  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((data) => {
        const backendTheme = data.settings?.active_theme;
        if (backendTheme && themes[backendTheme] && backendTheme !== themeId) {
          setThemeIdState(backendTheme);
          localStorage.setItem("nc-theme", backendTheme);
        }
      })
      .catch(() => {
        // Backend not available — use localStorage value
      });
    // Only run on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, themeId, setThemeId }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}

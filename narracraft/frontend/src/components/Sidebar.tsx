import { NavLink } from "react-router-dom";
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
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/franchises", icon: Gamepad2, label: "Franchises" },
  { to: "/assets", icon: ImageIcon, label: "Assets" },
  { to: "/discover", icon: Search, label: "Discover" },
  { to: "/queue", icon: ListTodo, label: "Queue" },
  { to: "/pipeline", icon: Play, label: "Pipeline" },
  { to: "/analytics", icon: BarChart3, label: "Analytics" },
  { to: "/settings", icon: Settings, label: "Settings" },
] as const;

export function Sidebar() {
  const { theme } = useTheme();

  return (
    <aside
      className="flex flex-col shrink-0 w-56 h-screen sticky top-0 overflow-y-auto"
      style={{
        background: theme.surface,
        borderRight: `1px solid ${theme.border}`,
      }}
    >
      {/* Logo area */}
      <div className="px-4 py-5" style={{ borderBottom: `1px solid ${theme.border}` }}>
        <div
          className="text-[9px] font-bold tracking-[2.5px] mb-1"
          style={{ color: theme.muted, fontFamily: theme.mono }}
        >
          NARRACRAFT
        </div>
        <div
          className="text-base font-bold"
          style={{ fontFamily: theme.font, color: theme.text }}
        >
          Mission Control
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 px-2">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className="flex items-center gap-3 px-3 py-2.5 rounded-md mb-0.5 no-underline transition-colors"
            style={({ isActive }) => ({
              background: isActive ? `${theme.accent}15` : "transparent",
              color: isActive ? theme.accent : theme.dim,
              fontFamily: theme.body,
              fontSize: "13px",
              fontWeight: isActive ? 700 : 500,
            })}
          >
            <Icon size={16} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div
        className="px-4 py-3 text-[9px] tracking-wider"
        style={{
          borderTop: `1px solid ${theme.border}`,
          color: theme.muted,
          fontFamily: theme.mono,
        }}
      >
        v0.1.0
      </div>
    </aside>
  );
}

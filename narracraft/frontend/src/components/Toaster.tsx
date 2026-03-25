/**
 * Toast notification system for NarraCraft.
 *
 * Provides a global toast queue with auto-dismiss, theme-aware styling,
 * and support for success/error/warning/info types.
 *
 * Usage:
 *   import { toast } from "@/components/Toaster";
 *   toast.success("Pipeline completed!");
 *   toast.error("Upload failed");
 *   toast.info("Collecting analytics...");
 */

import { useState, useEffect, useCallback, createContext, useContext, type ReactNode } from "react";
import { useTheme } from "@/components/ThemeProvider";
import { CheckCircle, XCircle, AlertTriangle, Info, X } from "lucide-react";

// ---------- Toast types & store ----------
export type ToastType = "success" | "error" | "warning" | "info";

interface Toast {
  id: number;
  type: ToastType;
  message: string;
  duration: number;
}

type ToastListener = (toasts: Toast[]) => void;

let _nextId = 1;
let _toasts: Toast[] = [];
let _listener: ToastListener | null = null;

function _notify() {
  _listener?.([..._toasts]);
}

function _add(type: ToastType, message: string, duration = 4000) {
  const t: Toast = { id: _nextId++, type, message, duration };
  _toasts = [..._toasts, t];
  _notify();

  // Auto-remove
  setTimeout(() => {
    _toasts = _toasts.filter((x) => x.id !== t.id);
    _notify();
  }, duration);
}

function _dismiss(id: number) {
  _toasts = _toasts.filter((x) => x.id !== id);
  _notify();
}

/** Global toast API — import and call from anywhere. */
export const toast = {
  success: (msg: string, duration?: number) => _add("success", msg, duration),
  error: (msg: string, duration?: number) => _add("error", msg, duration ?? 6000),
  warning: (msg: string, duration?: number) => _add("warning", msg, duration ?? 5000),
  info: (msg: string, duration?: number) => _add("info", msg, duration),
};

// ---------- Context for components that need toast programmatically ----------
const ToastContext = createContext(toast);
export const useToast = () => useContext(ToastContext);

// ---------- Toaster UI component ----------
export function Toaster() {
  const { theme } = useTheme();
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    _listener = setToasts;
    return () => {
      _listener = null;
    };
  }, []);

  if (toasts.length === 0) return null;

  const h = theme;
  const isPx = h.font.includes("Press Start");
  const fs = (n: number) => (isPx ? Math.max(n - 4, 6) : n);

  const iconMap = {
    success: CheckCircle,
    error: XCircle,
    warning: AlertTriangle,
    info: Info,
  };

  const colorMap = {
    success: h.success,
    error: h.danger,
    warning: h.accent,
    info: h.accent,
  };

  return (
    <div
      style={{
        position: "fixed",
        bottom: 20,
        right: 20,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        zIndex: 9990,
        pointerEvents: "none",
      }}
    >
      {toasts.map((t) => {
        const Icon = iconMap[t.type];
        const color = colorMap[t.type];

        return (
          <div
            key={t.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 14px",
              background: h.surface,
              border: `1px solid ${h.border}`,
              borderLeft: `3px solid ${color}`,
              borderRadius: h.card.borderRadius,
              boxShadow: `0 8px 24px rgba(0,0,0,0.3)`,
              maxWidth: 380,
              fontFamily: h.body,
              fontSize: fs(12),
              color: h.text,
              pointerEvents: "auto",
              animation: "nc-toast-slide-in 0.25s ease-out",
            }}
          >
            <Icon size={16} style={{ color, flexShrink: 0 }} />
            <span className="flex-1" style={{ lineHeight: 1.4 }}>
              {t.message}
            </span>
            <button
              onClick={() => _dismiss(t.id)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 2,
                color: h.muted,
                flexShrink: 0,
              }}
            >
              <X size={14} />
            </button>
          </div>
        );
      })}

      {/* Inline animation keyframes */}
      <style>{`
        @keyframes nc-toast-slide-in {
          from { opacity: 0; transform: translateX(20px); }
          to   { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}

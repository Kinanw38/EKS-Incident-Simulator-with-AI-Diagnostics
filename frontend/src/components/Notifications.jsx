import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Info,
  X,
  XCircle
} from "lucide-react";

const TOAST_VISIBLE_MS = 4200;
const TOAST_EXIT_MS = 280;

const TOAST_CONFIG = {
  success: {
    icon: CheckCircle2,
    iconClass: "text-emerald-400",
    borderClass: "border-emerald-400/25"
  },
  warning: {
    icon: AlertTriangle,
    iconClass: "text-amber-400",
    borderClass: "border-amber-400/25"
  },
  error: {
    icon: XCircle,
    iconClass: "text-rose-400",
    borderClass: "border-rose-400/25"
  },
  info: {
    icon: Info,
    iconClass: "text-blue-400",
    borderClass: "border-blue-400/25"
  }
};

function Toast({ toast, removeToast }) {
  const [exiting, setExiting] = useState(false);

  const config = TOAST_CONFIG[toast.type] || TOAST_CONFIG.info;
  const Icon = config.icon;

  useEffect(() => {
    const exitTimer = window.setTimeout(() => {
      setExiting(true);
    }, TOAST_VISIBLE_MS);

    const removeTimer = window.setTimeout(() => {
      removeToast(toast.id);
    }, TOAST_VISIBLE_MS + TOAST_EXIT_MS);

    return () => {
      window.clearTimeout(exitTimer);
      window.clearTimeout(removeTimer);
    };
  }, [toast.id, removeToast]);

  const dismiss = () => {
    if (exiting) return;
    setExiting(true);

    window.setTimeout(() => {
      removeToast(toast.id);
    }, TOAST_EXIT_MS);
  };

  return (
    <div
      className={`notification-toast ${
        exiting ? "notification-toast-exit" : ""
      } pointer-events-auto relative flex w-full items-start gap-3 overflow-hidden rounded-xl border bg-zinc-950/70 p-4 shadow-2xl shadow-black/30 backdrop-blur-2xl ${config.borderClass}`}
      role="status"
      aria-live="polite"
    >
      <div className="pointer-events-none absolute inset-0 bg-white/[0.025]" />

      <Icon
        className={`relative mt-0.5 h-5 w-5 shrink-0 ${config.iconClass}`}
      />

      <div className="relative min-w-0 flex-1 text-xs leading-relaxed">
        {toast.title && (
          <p className="truncate font-semibold text-zinc-100">
            {toast.title}
          </p>
        )}

        {toast.message && (
          <p className="mt-1 max-h-24 overflow-y-auto break-words whitespace-pre-wrap text-zinc-400">
            {toast.message}
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={dismiss}
        aria-label="Dismiss notification"
        className="relative shrink-0 rounded-md p-1 text-zinc-500 transition-all duration-200 hover:bg-white/[0.07] hover:text-zinc-200 active:scale-95"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export default function ToastContainer({ toasts, removeToast }) {
  const visibleToasts = toasts.slice(-3);

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-[100] flex w-[calc(100vw-2rem)] max-w-sm flex-col gap-2.5 sm:right-6 sm:top-6">
      {visibleToasts.map((toast) => (
        <Toast
          key={toast.id}
          toast={toast}
          removeToast={removeToast}
        />
      ))}
    </div>
  );
}
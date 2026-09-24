import React from 'react';
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from 'lucide-react';

export default function ToastContainer({ toasts, removeToast }) {
  // Strict limit: Max 3 visible notifications to prevent UI overlap
  const visibleToasts = toasts.slice(-3);

  return (
    <div className="fixed top-5 right-5 z-[100] flex flex-col gap-2.5 max-w-sm w-full pointer-events-none px-4 sm:px-0">
      {visibleToasts.map((toast) => {
        const icons = {
          success: <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />,
          warning: <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />,
          error: <XCircle className="w-5 h-5 text-rose-400 shrink-0" />,
          info: <Info className="w-5 h-5 text-blue-400 shrink-0" />
        };

        const bgBorders = {
          success: "bg-zinc-900/95 border-emerald-500/30 text-emerald-200",
          warning: "bg-zinc-900/95 border-amber-500/30 text-amber-200",
          error: "bg-zinc-900/95 border-rose-500/30 text-rose-200",
          info: "bg-zinc-900/95 border-blue-500/30 text-blue-200"
        };

        return (
          <div
            key={toast.id}
            className={`animate-toast-in pointer-events-auto flex items-start gap-3 p-4 rounded-xl border shadow-2xl shadow-black/40 backdrop-blur-md transition-all duration-200 hover:-translate-y-0.5 hover:shadow-black/60 w-full overflow-hidden ${bgBorders[toast.type] || bgBorders.info}`}
          >
            {icons[toast.type]}
            <div className="flex-1 min-w-0 text-xs leading-relaxed">
              {toast.title && (
                <p className="font-semibold text-zinc-100 truncate">{toast.title}</p>
              )}
              {toast.message && (
                <p className="text-zinc-400 mt-0.5 break-words whitespace-pre-wrap max-h-32 overflow-y-auto">
                  {toast.message}
                </p>
              )}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-zinc-500 hover:text-zinc-300 shrink-0 transition-colors p-0.5 rounded hover:bg-zinc-800"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
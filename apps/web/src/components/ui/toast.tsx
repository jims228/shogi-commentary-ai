"use client";
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

type ToastVariant = "success" | "warning" | "error" | "default";
type ToastOptions = {
  id?: string;
  title: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number; // ms
};

type ToastRecord = ToastOptions & { key: string };

type ToastContextType = {
  show: (opts: ToastOptions) => void;
  dismiss: (key: string) => void;
};

const ToastContext = createContext<ToastContextType | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);

  const show = useCallback((opts: ToastOptions) => {
    const key = opts.id ?? `${opts.title}-${(opts.description || "").slice(0,20)}`;
    setToasts((prev) => {
      // dedupe: if same key exists recently, reuse
      const exists = prev.find((t) => t.key === key);
      if (exists) {
        return prev.map((t) => (t.key === key ? { ...t, ...opts } : t));
      }
      const rec: ToastRecord = { ...opts, key };
      return [...prev, rec];
    });
  }, []);

  const dismiss = useCallback((key: string) => {
    setToasts((prev) => prev.filter((t) => t.key !== key));
  }, []);

  const value = useMemo(() => ({ show, dismiss }), [show, dismiss]);

  // mirror to singleton store so Toaster can observe without complex wiring
  useEffect(() => {
    // whenever toasts change, sync to store via custom event - but since we didn't expose toasts here,
    // callers should use showToast() helper below. Keep provider for potential future context use.
  }, [toasts]);

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

// Minimal Toaster component to place in the app root
export function Toaster() {
  return <ToasterInner />;
}

// Internal singleton store to allow Toaster to read toasts without complex context wiring
const store = (() => {
  let toasts: ToastRecord[] = [];
  const listeners: ((t: ToastRecord[]) => void)[] = [];
  return {
    add: (t: ToastRecord) => {
      const idx = toasts.findIndex((x) => x.key === t.key);
      if (idx >= 0) {
        toasts[idx] = { ...toasts[idx], ...t };
      } else {
        toasts = [...toasts, t];
      }
      listeners.forEach((l) => l(toasts));
    },
    remove: (key: string) => {
      toasts = toasts.filter((x) => x.key !== key);
      listeners.forEach((l) => l(toasts));
    },
    subscribe: (fn: (t: ToastRecord[]) => void) => {
      listeners.push(fn);
      fn(toasts);
      return () => {
        const i = listeners.indexOf(fn);
        if (i >= 0) listeners.splice(i, 1);
      };
    },
  };
})();

// Exposed helpers
export function showToast(opts: ToastOptions) {
  const key = opts.id ?? `${opts.title}-${(opts.description || "").slice(0,20)}`;
  const rec: ToastRecord = { ...opts, key };
  store.add(rec);
  // auto-dismiss
  const dur = opts.duration ?? 4000;
  setTimeout(() => store.remove(rec.key), dur);
}

export function dismissToast(key: string) {
  store.remove(key);
}

function ToasterInner() {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  useEffect(() => store.subscribe(setToasts), []);

  return (
    <div aria-live="polite" className="fixed top-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.key}
          className={`max-w-sm w-full p-3 rounded shadow-lg border ${variantClass(t.variant)}`}
        >
          <div className="font-medium text-sm">{t.title}</div>
          {t.description ? <div className="text-xs text-muted-foreground">{t.description}</div> : null}
        </div>
      ))}
    </div>
  );
}

function variantClass(v?: ToastVariant) {
  switch (v) {
    case "success":
      return "bg-emerald-50 text-emerald-800 border-emerald-200";
    case "warning":
      return "bg-amber-50 text-amber-800 border-amber-200";
    case "error":
      return "bg-rose-50 text-rose-800 border-rose-200";
    default:
      return "bg-slate-50 text-slate-800 border-slate-200";
  }
}

export default function Dummy() {
  return null;
}

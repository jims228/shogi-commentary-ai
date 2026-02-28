"use client";
import React, { createContext, useContext, useEffect, useState } from "react";

export type ProgressState = {
  xp: number;
  hearts: number;
  streak: number;
  lastPlayedISO?: string | null;
  clearedIds: string[];
};

const STORAGE_KEY = "learn.progress.v1";

const defaultState: ProgressState = { xp: 0, hearts: 5, streak: 0, lastPlayedISO: null, clearedIds: [] };

const ProgressContext = createContext<{
  state: ProgressState;
  addXp: (n: number) => void;
  loseHeart: () => void;
  markCleared: (id: string) => void;
  nextDayAdjust: () => void;
} | null>(null);

export function ProgressProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<ProgressState>(defaultState);

  useEffect(() => {
    // SSRガード
    if (typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) setState(JSON.parse(raw) as ProgressState);
    } catch {}
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {}
  }, [state]);

  const addXp = (n: number) => setState((s) => ({ ...s, xp: s.xp + n }));
  const loseHeart = () => setState((s) => ({ ...s, hearts: Math.max(0, s.hearts - 1) }));
  const markCleared = (id: string) => setState((s) => ({ ...s, clearedIds: Array.from(new Set([...s.clearedIds, id])) }));
  const nextDayAdjust = () => setState((s) => ({ ...s, streak: s.streak + 1, lastPlayedISO: new Date().toISOString() }));

  return (
    <ProgressContext.Provider value={{ state, addXp, loseHeart, markCleared, nextDayAdjust }}>
      {children}
    </ProgressContext.Provider>
  );
}

export function useProgress() {
  const ctx = useContext(ProgressContext);
  if (!ctx) throw new Error("useProgress must be used within ProgressProvider");
  return ctx;
}

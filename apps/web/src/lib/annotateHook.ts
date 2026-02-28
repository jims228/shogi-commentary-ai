"use client";
import { useState } from "react";
import { fetchWithAuth } from "@/lib/fetchWithAuth";

// Engine URL policy: NEXT_PUBLIC_ENGINE_URL -> ENGINE_URL -> default
const API_BASE: string =
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  process.env.NEXT_PUBLIC_ENGINE_URL ||
  process.env.ENGINE_URL ||
  "http://localhost:8787";

export type AnnotationNote = {
  ply?: number | string;
  move?: string;
  bestmove?: string;
  score_before_cp?: number | null;
  score_after_cp?: number | null;
  delta_cp?: number | null;
  time_ms?: number | null;
  score_cp?: number | null; // legacy / convenience (after)
  mate?: number | null;
  pv?: string;
  verdict?: string;
  tags?: string[];
  principles?: string[];
  evidence?: Record<string, unknown>;
  comment?: string;
};
export type AnnotationResponse = {
  summary?: string;
  notes?: AnnotationNote[];
};

// Engine /analyze response from engine_server.py
export type EngineMultipvItem = {
  multipv: number;
  score: {
    type: "cp" | "mate";
    cp?: number;
    mate?: number;
  };
  pv: string;
  depth?: number;
};
export type EngineAnalyzeResponse = {
  ok: boolean;
  bestmove?: string;
  multipv?: EngineMultipvItem[];
  raw?: string;
  error?: string;
  detail?: string;
};

export type KeyMoment = {
  ply: number;
  move: string;
  bestmove?: string;
  delta_cp?: number | null;
  tags?: string[];
  principles?: string[];
  evidence?: Record<string, unknown>;
  pv?: string;
};

export type DigestResponse = {
  summary?: string[];
  stats?: Record<string, unknown>;
  key_moments?: KeyMoment[];
  notes?: KeyMoment[];
  error?: string;
};

// Game analysis types (from backend /analyze-game)
export type AnalyzeGameMove = {
  ply: number;
  move: string;
  side: "sente" | "gote";
  eval: number | null;
  povEval: number | null;
  delta: number | null;
  label: "brilliant" | "good" | "inaccuracy" | "mistake" | "blunder" | "normal";
};

export type AnalyzeGameResponse = {
  moves: AnalyzeGameMove[];
};

export function useAnnotate() {
  const [usi, setUsi] = useState<string>("startpos moves 7g7f 3c3d 2g2f 8c8d");
  const [isPending, setPending] = useState(false);
  const [data, setData] = useState<EngineAnalyzeResponse | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);

  async function submit() {
    setLocalError(null);
    setError(null);
    setPending(true);
    try {
      const url = `${API_BASE}/annotate`;
      // eslint-disable-next-line no-console
      console.log("[web] annotate fetch to:", url);
      const res = await fetchWithAuth(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ usi, byoyomi_ms: 500 }),
      });
      // eslint-disable-next-line no-console
      console.log("[web] annotate response status:", res.status);
      if (!res.ok) {
        const errText = await res.text();
        console.error(`[web] annotate error: ${url} status=${res.status} body=${errText}`);
        throw new Error(`注釈APIエラー: ${res.status} ${errText}`);
      }
      const json = await res.json();
      // eslint-disable-next-line no-console
      console.log("[web] annotate response body keys:", json && Object.keys(json));
      setData(json as EngineAnalyzeResponse);
    } catch (e: unknown) {
      if (e instanceof Error) setError(e);
      else setLocalError(String(e));
    } finally {
      setPending(false);
    }
  }

  // simple health check helper (optional for UI)
  async function checkHealth(): Promise<string> {
    try {
      const url = `${API_BASE}/health`;
      // eslint-disable-next-line no-console
      console.log("[web] health fetch to:", url);
      const r = await fetchWithAuth(url, { cache: "no-store" });
      const j = await r.json().catch(() => ({}));
      // eslint-disable-next-line no-console
      console.log("[web] engine health:", r.status, j);
      return r.ok ? "ok" : `bad(${r.status})`;
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("[web] engine health error:", err);
      return "error";
    }
  }

  function downloadCsv(notes: AnnotationNote[] | null | undefined) {
    if (!notes) return;
    const header = [
      "ply",
      "move",
      "bestmove",
      "score_before_cp",
      "score_after_cp",
      "delta_cp",
      "mate",
      "verdict",
      "tags",
      "principles",
      "evidence_tactical",
      "pv",
      "comment",
    ];
    const rows = notes.map((n) => [
      String(n.ply ?? ""),
      n.move ?? "",
      n.bestmove ?? "",
      typeof n.score_before_cp === "number" ? String(n.score_before_cp) : "",
      typeof n.score_after_cp === "number" ? String(n.score_after_cp) : "",
      typeof n.delta_cp === "number" ? String(n.delta_cp) : "",
      typeof n.mate === "number" ? String(n.mate) : "",
      n.verdict ?? "",
      (n.tags || []).join(";") || "",
      (n.principles || []).join(";") || "",
      JSON.stringify(n.evidence?.tactical ?? {}),
      n.pv ?? "",
      n.comment ?? "",
    ]);
    const escape = (s: string) => `"${String(s).replace(/"/g, '""')}"`;
    const csv = [header.map(escape).join(","), ...rows.map((r) => r.map(escape).join(","))].join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "annotation.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return { usi, setUsi, submit, isPending, data, localError, error, downloadCsv, checkHealth } as const;
}

// Hook for game analysis (evaluation graph + move labels)
export function useGameAnalysis() {
  const [analysis, setAnalysis] = useState<AnalyzeGameResponse | null>(null);
  const [isPending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function analyzeGame(usi: string, pov: "sente" | "gote" = "sente", depth: number = 10) {
    setError(null);
    setPending(true);
    try {
      const url = `${API_BASE}/analyze-game`;
      // eslint-disable-next-line no-console
      console.log("[web] game analysis fetch to:", url);
      const res = await fetchWithAuth(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ usi, pov, depth }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`API error ${res.status}: ${text}`);
      }
      const json = await res.json();
      setAnalysis(json as AnalyzeGameResponse);
    } catch (e: unknown) {
      if (e instanceof Error) setError(e.message);
      else setError(String(e));
    } finally {
      setPending(false);
    }
  }

  return { analysis, isPending, error, analyzeGame } as const;
}

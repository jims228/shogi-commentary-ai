import { parseCsv } from "./csv";

export type Puzzle = {
  id: string;
  sfen: string;
  turn: string;
  goal: string;
  solution: string;
  hint?: string;
  tags?: string;
  difficulty?: number;
};

export async function loadTsumeDaily(limit = 5): Promise<Puzzle[]> {
  const res = await fetch("/puzzles/tsume.csv");
  const txt = await res.text();
  const rows = parseCsv(txt);
  const puzzles: Puzzle[] = rows.map((r: Record<string, string>) => ({
    id: r.id,
    sfen: r.sfen,
    turn: r.turn,
    goal: r.goal,
    solution: r.solution,
    hint: r.hint,
    tags: r.tags,
    difficulty: Number(r.difficulty) || 1,
  }));
  return puzzles.slice(0, limit);
}

export function normalizeMove(s: string): string {
  if (!s) return "";
  try {
    // NFKC to convert full-width to half-width
    s = (s || "").normalize?.("NFKC") ?? s;
  } catch {
    // ignore
  }
  // remove commas, full-width commas handled by NFKC
  let t = String(s).replace(/[，,]/g, "");
  // remove surrounding parentheses
  t = t.replace(/[（）()]/g, "");
  // collapse whitespace
  t = t.replace(/\s+/g, " ").trim();
  return t.toLowerCase();
}


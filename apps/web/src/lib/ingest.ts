// apps/web/src/lib/ingest.ts
import { normalizeKifInput, kifToUsiMoves, kifLongToUsiMoves, csaToUsiMoves } from "./convertKif";

/** 入力がUSIかの簡易判定 */
function isUSI(text: string) {
  const t = text.trim();
  return t.startsWith("startpos") || t.startsWith("sfen");
}

/** 入力がCSAかの簡易判定 */
function isCSA(text: string) {
  const t = text.trim();
  return /^\s*[+-]\d{4}[A-Z]{2}/m.test(t) || /BEGIN\s+CSA/i.test(t);
}

/** 入力がKIFっぽいか */
function isKIF(text: string) {
  const t = text.trim();
  return /▲|△|同|まで|先手|後手|手\s*数|開始日時|終了日時/.test(t);
}

function kifToStartpos(text: string) {
  const norm = normalizeKifInput(text);
  let moves: string[] = [];
  try {
    moves = kifToUsiMoves(norm);
  } catch {
    moves = kifLongToUsiMoves(norm);
  }
  return `startpos moves ${moves.join(" ")}`;
}

function csaToStartpos(text: string) {
  const moves = csaToUsiMoves(text);
  return `startpos moves ${moves.join(" ")}`;
}

export function toStartposUSI(input: string): string {
  if (!input || !input.trim()) throw new Error("空の入力です。");
  if (isUSI(input)) return input.trim();
  if (isCSA(input)) return csaToStartpos(input);
  if (isKIF(input)) return kifToStartpos(input);

  try {
    return kifToStartpos(input);
  } catch {
    try {
      return csaToStartpos(input);
    } catch {
      throw new Error("形式を判定できませんでした（USI/KIF/CSA を想定）。");
    }
  }
}

export default toStartposUSI;

/**
 * Split KIF text that may contain multiple games into individual game texts.
 * Heuristic split: two-or-more blank lines, or lines containing 開始日時/終了日時 or 'までNN手'.
 */
export function splitKifGames(text: string): string[] {
  if (!text) return [];
  // normalize newlines
  const src = text.replace(/\r/g, "");
  // first split on two-or-more blank lines
  const parts = src.split(/\n{2,}/).map(p => p.trim()).filter(Boolean);

  // further split parts that contain 'までNN手' occurrences into smaller pieces
  const out: string[] = [];
  for (const p of parts) {
    // if contains 'まで' followed by digits and '手', split after that line
    if (/まで\s*\d+手/.test(p)) {
      const lines = p.split('\n');
      let cur: string[] = [];
      for (const ln of lines) {
        cur.push(ln);
        if (/まで\s*\d+手/.test(ln)) {
          out.push(cur.join('\n').trim());
          cur = [];
        }
      }
      if (cur.length) out.push(cur.join('\n').trim());
    } else if (/^\s*(開始日時|終了日時)\b/m.test(p)) {
      // split on lines starting with 開始日時 or 終了日時
      const lines = p.split('\n');
      let cur: string[] = [];
      for (const ln of lines) {
        if (/^\s*(開始日時|終了日時)\b/.test(ln) && cur.length) {
          out.push(cur.join('\n').trim());
          cur = [ln];
        } else {
          cur.push(ln);
        }
      }
      if (cur.length) out.push(cur.join('\n').trim());
    } else {
      out.push(p);
    }
  }

  return out.map(s => s.trim()).filter(Boolean);
}

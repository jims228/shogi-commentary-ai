// src/lib/usi.ts
export function usiToMoves(usi: string): string[] {
  const trimmed = usi.trim();

  // "startpos moves 7g7f 3c3d 2g2f" の形式
  const movesMatch = trimmed.match(/(?:startpos|sfen[^m]*?)\s+moves\s+(.+)/i);
  if (movesMatch) {
    return movesMatch[1].trim().split(/\s+/).filter(Boolean);
  }

  // "startpos" のみの場合は手の履歴なし
  if (trimmed === "startpos") {
    return [];
  }

  // "sfen ... b - 1" のような形式で moves がない場合
  if (trimmed.startsWith("sfen") && !trimmed.includes("moves")) {
    return [];
  }

  // その他の形式は空配列
  return [];
}

export function buildUsiPositionForPly(original: string, ply: number): string {
  const trimmed = original.trim();
  if (!trimmed) return "";

  const body = trimmed.startsWith("position") ? trimmed.slice("position".length).trim() : trimmed;
  if (!body) return "";

  const lowerBody = body.toLowerCase();
  const movesIndex = lowerBody.indexOf("moves");

  if (movesIndex === -1 || ply <= 0) {
    return `position ${body}`.trim();
  }

  const head = body.slice(0, movesIndex + 5).trim();
  const tail = body.slice(movesIndex + 5).trim();
  if (!tail) {
    return `position ${head}`.trim();
  }

  const allMoves = tail.split(/\s+/).filter(Boolean);
  const partial = allMoves.slice(0, Math.min(ply, allMoves.length));
  const movesSegment = partial.join(" ");

  return `position ${head} ${movesSegment}`.trim();
}
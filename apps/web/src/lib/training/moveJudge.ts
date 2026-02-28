import type { PieceBase, PieceCode } from "@/lib/sfen";
import type { MoveSpec, Square } from "@/lib/training/lessonTypes";

export type BoardMove = {
  from?: { x: number; y: number };
  to: { x: number; y: number };
  piece: PieceCode | string;
  drop?: boolean;
};

export function squareToXY(sq: Square): { x: number; y: number } {
  return { x: 9 - sq.file, y: sq.rank - 1 };
}

function basePieceOf(code: string): PieceBase | null {
  const raw = code.startsWith("+") ? code.slice(1) : code;
  const up = raw.toUpperCase();
  if (!up) return null;
  const base = up[0] as PieceBase;
  if (!["P", "L", "N", "S", "G", "B", "R", "K"].includes(base)) return null;
  return base;
}

function isPromotedCode(code: string): boolean {
  return code.startsWith("+");
}

function sameXY(a: { x: number; y: number }, b: { x: number; y: number }) {
  return a.x === b.x && a.y === b.y;
}

export function matchesMoveSpec(actual: BoardMove, spec: MoveSpec): boolean {
  const actualPieceStr = typeof actual.piece === "string" ? actual.piece : String(actual.piece);
  const actualBase = basePieceOf(actualPieceStr);

  if (spec.kind === "drop") {
    const isDrop = actual.drop === true || actual.from == null;
    if (!isDrop) return false;
    if (!actualBase) return false;
    if (actualBase !== spec.piece) return false;
    return sameXY(actual.to, squareToXY(spec.to));
  }

  // kind === "move"
  const isDrop = actual.drop === true || actual.from == null;
  if (isDrop) return false;
  if (!actual.from) return false;
  if (!sameXY(actual.from, squareToXY(spec.from))) return false;
  if (!sameXY(actual.to, squareToXY(spec.to))) return false;

  if (typeof spec.promote === "boolean") {
    const promoted = isPromotedCode(actualPieceStr);
    if (promoted !== spec.promote) return false;
  }

  return true;
}

export function isExpectedMove(actual: BoardMove, expectedMoves: MoveSpec[]): boolean {
  return expectedMoves.some((s) => matchesMoveSpec(actual, s));
}



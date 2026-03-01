import { useCallback, useMemo } from "react";
import { getPieceOwner, type BoardMatrix } from "@/lib/board";
import type { PieceCode } from "@/lib/sfen";
import type { Square, SelectedHand } from "@/components/ShogiBoard";

export type UsePieceMovesParams = {
  board: BoardMatrix;
  selectedHand: SelectedHand;
};

export type UsePieceMovesReturn = {
  isPromotionZone: (y: number) => boolean;
  canPromotePiece: (piece: string) => boolean;
  isLegalDropTarget: (target: Square, hand: SelectedHand) => boolean;
  isLegalPieceMove: (from: Square, to: Square, piece: PieceCode) => boolean;
  legalDropSquares: Square[];
  legalDropSquareKeySet: Set<string>;
};

export const usePieceMoves = ({
  board,
  selectedHand,
}: UsePieceMovesParams): UsePieceMovesReturn => {
  const isPromotionZone = useCallback((y: number) => {
    return y <= 2;
  }, []);

  const canPromotePiece = useCallback((piece: string) => {
    const base = piece.toUpperCase().replace("+", "");
    return ["P", "L", "N", "S", "B", "R"].includes(base) && !piece.startsWith("+");
  }, []);

  const isLegalDropTarget = useCallback((target: Square, hand: SelectedHand) => {
    if (!hand) return false;
    if (board[target.y]?.[target.x]) return false;

    const owner = hand.side === "b" ? "sente" : "gote";
    const isSente = owner === "sente";
    const base = hand.base;

    if (base === "P" || base === "L") {
      if ((isSente && target.y === 0) || (!isSente && target.y === 8)) return false;
    }

    if (base === "N") {
      if ((isSente && target.y <= 1) || (!isSente && target.y >= 7)) return false;
    }

    return true;
  }, [board]);

  const legalDropSquares = useMemo(() => {
    if (!selectedHand) return [] as Square[];

    const targets: Square[] = [];
    for (let y = 0; y < 9; y += 1) {
      for (let x = 0; x < 9; x += 1) {
        const target = { x, y };
        if (isLegalDropTarget(target, selectedHand)) targets.push(target);
      }
    }
    return targets;
  }, [isLegalDropTarget, selectedHand]);

  const legalDropSquareKeySet = useMemo(() => {
    return new Set(legalDropSquares.map((sq) => `${sq.x},${sq.y}`));
  }, [legalDropSquares]);

  // Basic move legality check (piece movement + line blocking).
  // Used to avoid showing promotion dialog on impossible destinations.
  const isLegalPieceMove = useCallback((from: Square, to: Square, piece: PieceCode) => {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    if (dx === 0 && dy === 0) return false;

    const owner = getPieceOwner(piece);
    const forwardSign = owner === "sente" ? -1 : 1;
    const nx = dx;
    const ny = dy * forwardSign; // normalize: ny=+1 means "forward" for both sides

    const absDx = Math.abs(dx);
    const absDy = Math.abs(dy);
    const promoted = piece.startsWith("+");
    const base = piece.replace("+", "").toUpperCase();

    const isPathClear = () => {
      const stepX = Math.sign(dx);
      const stepY = Math.sign(dy);
      const steps = Math.max(absDx, absDy);
      for (let i = 1; i < steps; i += 1) {
        const x = from.x + stepX * i;
        const y = from.y + stepY * i;
        if (board[y]?.[x]) return false;
      }
      return true;
    };

    const isGoldLike = () =>
      (ny === 1 && absDx <= 1) ||
      (ny === 0 && absDx === 1) ||
      (ny === -1 && nx === 0);

    if (promoted && ["P", "L", "N", "S"].includes(base)) return isGoldLike();
    if (promoted && base === "B") {
      const bishopMove = absDx === absDy && isPathClear();
      const kingOrthogonal = (absDx === 1 && absDy === 0) || (absDx === 0 && absDy === 1);
      return bishopMove || kingOrthogonal;
    }
    if (promoted && base === "R") {
      const rookMove = (dx === 0 || dy === 0) && isPathClear();
      const kingDiagonal = absDx === 1 && absDy === 1;
      return rookMove || kingDiagonal;
    }

    switch (base) {
      case "P":
        return nx === 0 && ny === 1;
      case "L":
        return nx === 0 && ny > 0 && isPathClear();
      case "N":
        return absDx === 1 && ny === 2;
      case "S":
        return (ny === 1 && absDx <= 1) || (ny === -1 && absDx === 1);
      case "G":
        return isGoldLike();
      case "K":
        return absDx <= 1 && absDy <= 1;
      case "B":
        return absDx === absDy && isPathClear();
      case "R":
        return (dx === 0 || dy === 0) && isPathClear();
      default:
        return false;
    }
  }, [board]);

  return {
    isPromotionZone,
    canPromotePiece,
    isLegalDropTarget,
    isLegalPieceMove,
    legalDropSquares,
    legalDropSquareKeySet,
  };
};

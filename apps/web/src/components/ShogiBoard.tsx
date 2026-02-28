"use client";

import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import BoardHintsOverlay, { type HintArrow } from "./training/BoardHintsOverlay";
import ArrowOverlay from "./board/ArrowOverlay";
import { shogiToDisplay, type Arrow as ArrowDatum } from "@/lib/arrowGeometry";
import { PieceSprite, type OrientationMode, type PieceMotionConfig } from "./PieceSprite";
import type { PieceBase, PieceCode } from "@/lib/sfen";
import {
  boardToPlaced,
  getPieceOwner,
  promotePiece,
  demotePiece,
  type BoardMatrix,
  type HandsState,
} from "@/lib/board";

// SSR では useLayoutEffect が使えないため、クライアントのみ useLayoutEffect を使う
const useIsomorphicLayoutEffect =
  typeof window !== "undefined" ? useLayoutEffect : useEffect;

export type BoardMode = "view" | "edit";
export type HandsPlacement = "default" | "corners";

export interface ShogiBoardProps {
  board: BoardMatrix;
  mode?: BoardMode;
  bestmove?: { from: { x: number; y: number }; to: { x: number; y: number } } | null;
  lastMove?: { from: { x: number; y: number }; to: { x: number; y: number } } | null;
  onBoardChange?: (next: BoardMatrix) => void;
  onHandsChange?: (next: HandsState) => void;
  onMove?: (move: { from?: { x: number; y: number }; to: { x: number; y: number }; piece: PieceCode; drop?: boolean }) => void;
  onSquareClick?: (x: number, y: number) => void;
  highlightSquares?: { x: number; y: number }[];
  hintSquares?: { file: number; rank: number }[];
  hintStars?: { file: number; rank: number }[];
  hintArrows?: HintArrow[];
  flipped?: boolean;
  orientation?: "sente" | "gote";
  orientationMode?: OrientationMode;
  hands?: HandsState;
  autoPromote?: boolean;
  showPromotionZone?: boolean;
  showHands?: boolean;
  /** Show coordinate labels (files/ranks). Default: true */
  showCoordinates?: boolean;
  selectedHand?: SelectedHand;
  onHandClick?: (base: PieceBase, side: "b" | "w") => void;
  onSelectedHandChange?: (hand: SelectedHand) => void;

  /** ★追加：持ち駒の表示位置 */
  handsPlacement?: HandsPlacement;
  /** embed向け: 持ち駒欄の高さ/間隔を圧縮 */
  compactHands?: boolean;
  /** Optional piece motion rules for reusable effects (shake, etc.) */
  pieceMotionRules?: PieceMotionRule[];
  /** Disable all player interactions on board/hands */
  interactionDisabled?: boolean;
  /** Two-choice dialog shown on top of board (promotion-like frame) */
  choiceDialog?: {
    prompt: string;
    options: [
      { label: string; onSelect: () => void },
      { label: string; onSelect: () => void },
    ];
  } | null;
}

export type PieceMotionRule = {
  match: {
    x?: number;
    y?: number;
    owner?: "sente" | "gote";
    /** exact piece code, e.g. "K", "k", "+R" */
    piece?: string;
    /** normalized base piece (uppercase), e.g. "K", "G", "P" */
    pieceBase?: PieceBase;
  };
  motion: PieceMotionConfig;
};

const BASE_CELL_SIZE = 50;
const BASE_PIECE_SIZE = 49;
const PIECE_SIZE_MULTIPLIER = 1.31; // 駒の表示倍率（盤上・持ち駒共通）
/** 自分の駒の縦位置オフセット（px）。負で上方向 */
const PIECE_OFFSET_Y_OWN_PX = -3.4;
/** 相手の駒の縦位置オフセット（px）。負で上方向 */
const PIECE_OFFSET_Y_OPPONENT_PX = -3.9;
const HAND_ORDER: PieceBase[] = ["P", "L", "N", "S", "G", "B", "R", "K"];
const BASE_HAND_CELL_SIZE = 40;
const BASE_HAND_PIECE_SIZE = 39;

const HOSHI_POINTS = [
  { file: 2, rank: 2 }, { file: 5, rank: 2 }, { file: 8, rank: 2 },
  { file: 2, rank: 5 }, { file: 5, rank: 5 }, { file: 8, rank: 5 },
  { file: 2, rank: 8 }, { file: 5, rank: 8 }, { file: 8, rank: 8 },
];

export type Square = { x: number; y: number };
export type SelectedHand = { base: PieceBase; side: "b" | "w" } | null;

type PendingMove = {
  sourceSquare: Square;
  targetSquare: Square;
  piece: PieceCode;
};

const FILE_LABELS_SENTE = ["9", "8", "7", "6", "5", "4", "3", "2", "1"];
const FILE_LABELS_GOTE = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];
const RANK_LABELS_SENTE = ["一", "二", "三", "四", "五", "六", "七", "八", "九"];
const RANK_LABELS_GOTE = ["九", "八", "七", "六", "五", "四", "三", "二", "一"];
const BASE_LABEL_GAP = 26;

const TOUCH_DOUBLE_TAP_MS = 320;

export const ShogiBoard: React.FC<ShogiBoardProps> = ({
  board,
  mode = "view",
  bestmove,
  lastMove,
  onBoardChange,
  onHandsChange,
  onMove,
  onSquareClick,
  highlightSquares,
  hintSquares,
  hintStars,
  hintArrows = [],
  flipped = false,
  orientation = undefined,
  orientationMode = "sprite",
  hands,
  autoPromote = false,
  showPromotionZone = false,
  showHands = true,
  showCoordinates = true,
  selectedHand: propSelectedHand,
  onSelectedHandChange,

  handsPlacement = "default",
  compactHands = false,
  pieceMotionRules = [],
  interactionDisabled = false,
  choiceDialog = null,
}) => {
  const placedPieces = useMemo(() => boardToPlaced(board), [board]);
  const containerRef = useRef<HTMLDivElement>(null);
  const touchTapRef = useRef<{ square: Square; timestamp: number } | null>(null);

  // Mobile sizing: scale via CSS variable only (no `zoom` on wrappers).
  // useIsomorphicLayoutEffect でブラウザ描画前に同期読み取りし、
  // ResizeObserver で data-mobile="1" 適用後の CSS 変数変化にも追従する。
  const [uiScale, setUiScale] = useState(1);
  const [pieceScale, setPieceScale] = useState(1);
  useIsomorphicLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const readScales = () => {
      const v = window.getComputedStyle(el).getPropertyValue("--piece-scale");
      const n = parseFloat(v);
      if (Number.isFinite(n) && n > 0) setUiScale(n);

      const pv = window.getComputedStyle(el).getPropertyValue("--piece-sprite-scale");
      const pn = parseFloat(pv);
      if (Number.isFinite(pn) && pn > 0) setPieceScale(pn);
    };

    readScales();

    // ResizeObserver: 親の data-mobile="1" 適用後に CSS 変数が変わる場合に対応。
    // 要素サイズの変化ではなく CSS 変数の変化を渡接私形でも掴う。
    const obs = new ResizeObserver(readScales);
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const CELL_SIZE = Math.round(BASE_CELL_SIZE * uiScale);
  const PIECE_SIZE = Math.round(BASE_PIECE_SIZE * uiScale * pieceScale * PIECE_SIZE_MULTIPLIER);
  const HAND_CELL_SIZE = Math.round(BASE_HAND_CELL_SIZE * uiScale);
  const HAND_PIECE_SIZE = Math.round(BASE_HAND_PIECE_SIZE * uiScale * pieceScale * PIECE_SIZE_MULTIPLIER);
  const LABEL_GAP = Math.round(BASE_LABEL_GAP * uiScale);
  const boardSize = CELL_SIZE * 9;

  const [selectedSquare, setSelectedSquare] = useState<Square | null>(null);
  const [internalSelectedHand, setInternalSelectedHand] = useState<SelectedHand>(null);
  const selectedHand = propSelectedHand !== undefined ? propSelectedHand : internalSelectedHand;

  const updateSelectedHand = useCallback((newHand: SelectedHand) => {
    if (propSelectedHand !== undefined) {
      onSelectedHandChange?.(newHand);
    } else {
      setInternalSelectedHand(newHand);
    }
  }, [propSelectedHand, onSelectedHandChange]);

  const [pendingMove, setPendingMove] = useState<PendingMove | null>(null);

  const viewerOrientation: "sente" | "gote" = orientation ?? (flipped ? "gote" : "sente");
  const isGoteView = viewerOrientation === "gote";
  const canEdit = mode === "edit" && Boolean(onBoardChange) && !interactionDisabled;

  useEffect(() => {
    if (!canEdit) {
      setSelectedSquare(null);
      updateSelectedHand(null);
      setPendingMove(null);
    }
  }, [canEdit, updateSelectedHand]);

  const getDisplayPos = useCallback((x: number, y: number) => {
    return isGoteView ? { x: 8 - x, y: 8 - y } : { x, y };
  }, [isGoteView]);

  const isHighlighted = useCallback((x: number, y: number) => {
    return highlightSquares?.some((sq) => sq.x === x && sq.y === y) ?? false;
  }, [highlightSquares]);

  const isHintSquare = useCallback((x: number, y: number) => {
    if (!hintSquares || hintSquares.length === 0) return false;

    // Build tolerant candidate coordinates for each hint.
    // Accept multiple conventions: 1) file->x as (9-file)  2) file->x as (file-1)
    // Also consider flipped board coordinates.
    for (const h of hintSquares) {
      const file = h.file;
      const rank = h.rank;
      if (typeof file !== "number" || typeof rank !== "number") continue;

      const candidates = [] as { x: number; y: number }[];
      // interpretation A: file 1..9 -> x = 9-file (sente rightmost=1)
      candidates.push({ x: 9 - file, y: rank - 1 });
      // interpretation B: file 1..9 -> x = file-1 (left-origin)
      candidates.push({ x: file - 1, y: rank - 1 });
      // flipped variants
      candidates.push({ x: 8 - (9 - file), y: 8 - (rank - 1) });
      candidates.push({ x: 8 - (file - 1), y: 8 - (rank - 1) });

      for (const c of candidates) {
        if (c.x === x && c.y === y) return true;
      }
    }

    return false;
  }, [hintSquares]);

  const normalizedHintStars = useMemo(() => {
    if (!hintStars || hintStars.length === 0) return [] as { x: number; y: number }[];

    const out: { x: number; y: number }[] = [];

    for (const h of hintStars) {
      const file = h.file;
      const rank = h.rank;
      if (typeof file !== "number" || typeof rank !== "number") continue;

      const c = { x: 9 - file, y: rank - 1 };
      if (c.x < 0 || c.x > 8 || c.y < 0 || c.y > 8) continue;
      out.push(c);
    }

    return out;
  }, [hintStars]);

  const [consumedHintStars, setConsumedHintStars] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    setConsumedHintStars(new Set());
  }, [hintStars]);

  const visibleHintStars = useMemo(() => {
    if (normalizedHintStars.length === 0) return normalizedHintStars;
    return normalizedHintStars.filter((s) => !consumedHintStars.has(`${s.x},${s.y}`));
  }, [normalizedHintStars, consumedHintStars]);

  const isPromotionZone = useCallback((y: number) => {
    return y <= 2;
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

  const canPromotePiece = (piece: string) => {
    const base = piece.toUpperCase().replace("+", "");
    return ["P", "L", "N", "S", "B", "R"].includes(base) && !piece.startsWith("+");
  };

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

  const isTouchDoubleTap = useCallback((square: Square) => {
    const now = performance.now();
    const previous = touchTapRef.current;
    if (previous && now - previous.timestamp < TOUCH_DOUBLE_TAP_MS && previous.square.x === square.x && previous.square.y === square.y) {
      touchTapRef.current = null;
      return true;
    }
    touchTapRef.current = { square, timestamp: now };
    return false;
  }, []);

  // 音
  const playPieceSound = useCallback(() => {
    try {
      const audio = new Audio("/sounds/koma.mp3");
      audio.volume = 0.6;
      audio.currentTime = 0;
      audio.play().catch((e) => console.log("Audio play blocked", e));
    } catch (e) {
      // ignore
    }
  }, []);

  const handleHandClick = useCallback((base: PieceBase, side: "b" | "w") => {
    if (!canEdit) return;
    const handOwner = side === "b" ? "sente" : "gote";
    if (handOwner !== viewerOrientation) return;
    if (selectedHand && selectedHand.base === base && selectedHand.side === side) {
      updateSelectedHand(null);
    } else {
      updateSelectedHand({ base, side });
      setSelectedSquare(null);
    }
  }, [canEdit, selectedHand, updateSelectedHand, viewerOrientation]);

  const executeMove = useCallback((source: Square, target: Square, pieceCode: PieceCode, isDrop: boolean) => {
    if (!onBoardChange) return;

    const nextBoard = board.map(row => row.slice());

    if (isDrop && selectedHand && hands && onHandsChange) {
      const nextHands = { b: { ...hands.b }, w: { ...hands.w } };
      const count = nextHands[selectedHand.side][selectedHand.base] || 0;
      if (count > 0) {
        nextHands[selectedHand.side][selectedHand.base] = count - 1;
        if (nextHands[selectedHand.side][selectedHand.base] === 0) delete nextHands[selectedHand.side][selectedHand.base];
        onHandsChange(nextHands);
      }
    } else {
      nextBoard[source.y][source.x] = null;
    }

    const targetPiece = board[target.y][target.x];
    if (!isDrop && targetPiece && hands && onHandsChange) {
      const nextHands = { b: { ...hands.b }, w: { ...hands.w } };
      const sourcePieceObj = board[source.y][source.x];
      if (sourcePieceObj) {
        const capturedBase = targetPiece.replace("+", "").toUpperCase() as PieceBase;
        const capturerSide = getPieceOwner(sourcePieceObj) === "sente" ? "b" : "w";
        nextHands[capturerSide][capturedBase] = (nextHands[capturerSide][capturedBase] || 0) + 1;
        onHandsChange(nextHands);
      }
    }

    nextBoard[target.y][target.x] = pieceCode;
    onBoardChange(nextBoard);

    const landedStarKey = `${target.x},${target.y}`;
    if (normalizedHintStars.some((s) => s.x === target.x && s.y === target.y)) {
      setConsumedHintStars((prev) => {
        if (prev.has(landedStarKey)) return prev;
        const next = new Set(prev);
        next.add(landedStarKey);
        return next;
      });
    }

    playPieceSound();

    onMove?.({ from: isDrop ? undefined : source, to: target, piece: pieceCode, drop: isDrop });

    setSelectedSquare(null);
    updateSelectedHand(null);
    setPendingMove(null);
  }, [board, hands, normalizedHintStars, onBoardChange, onHandsChange, onMove, selectedHand, playPieceSound, updateSelectedHand]);

  const attemptAction = useCallback((target: Square) => {
    if (!onBoardChange) return false;

    // ケース1: 持ち駒を打つ
    if (selectedHand) {
      if (!isLegalDropTarget(target, selectedHand)) return false;
      const pieceCode = (selectedHand.side === "b" ? selectedHand.base : selectedHand.base.toLowerCase()) as PieceCode;
      executeMove({ x: -1, y: -1 }, target, pieceCode, true);
      return true;
    }

    // ケース2: 盤上の駒を移動
    if (selectedSquare) {
      if (selectedSquare.x === target.x && selectedSquare.y === target.y) return false;

      const sourcePiece = board[selectedSquare.y]?.[selectedSquare.x];
      if (!sourcePiece) {
        setSelectedSquare(null);
        return false;
      }
      // 自分の駒だけ操作可能
      if (getPieceOwner(sourcePiece) !== viewerOrientation) {
        setSelectedSquare(null);
        return true;
      }

      const targetPiece = board[target.y][target.x];
      if (targetPiece && getPieceOwner(targetPiece) === getPieceOwner(sourcePiece)) {
        return false;
      }

      // そもそも駒の利きとして成立しない移動なら、成り/不成は出さない（移動もしない）。
      if (!isLegalPieceMove(selectedSquare, target, sourcePiece)) {
        return true;
      }

      const owner = getPieceOwner(sourcePiece);
      const isSente = owner === "sente";
      const isZone = isSente
        ? (target.y <= 2 || selectedSquare.y <= 2)
        : (target.y >= 6 || selectedSquare.y >= 6);

      if (isZone && canPromotePiece(sourcePiece)) {
        if (autoPromote) {
          executeMove(selectedSquare, target, promotePiece(sourcePiece) as PieceCode, false);
        } else {
          setPendingMove({
            sourceSquare: selectedSquare,
            targetSquare: target,
            piece: sourcePiece,
          });
        }
        return true;
      }

      executeMove(selectedSquare, target, sourcePiece, false);
      return true;
    }

    return false;
  }, [board, onBoardChange, selectedHand, selectedSquare, autoPromote, canPromotePiece, executeMove, isLegalPieceMove, viewerOrientation]);

  const togglePromotionAt = useCallback((square: Square) => {
    if (!canEdit || !onBoardChange) return;
    const piece = board[square.y]?.[square.x];
    if (!piece) return;
    const nextBoard = board.map((row) => row.slice());
    nextBoard[square.y][square.x] = piece.startsWith("+") ? demotePiece(piece) : promotePiece(piece);
    onBoardChange(nextBoard);

    playPieceSound();

    setSelectedSquare(null);
    updateSelectedHand(null);
  }, [board, canEdit, onBoardChange, playPieceSound, updateSelectedHand]);

  const handleEditSquareClick = useCallback((square: Square) => {
    if (!onBoardChange) return;
    if (attemptAction(square)) return;

    const pieceAtTarget = board[square.y]?.[square.x];
    if (pieceAtTarget) {
      // 相手の駒は選択不可
      if (getPieceOwner(pieceAtTarget) !== viewerOrientation) {
        setSelectedSquare(null);
        updateSelectedHand(null);
        return;
      }
      // 同じ駒を再タップしたら選択解除
      if (selectedSquare && selectedSquare.x === square.x && selectedSquare.y === square.y) {
        setSelectedSquare(null);
        updateSelectedHand(null);
        return;
      }
      setSelectedSquare({ ...square });
      updateSelectedHand(null);
    } else {
      setSelectedSquare(null);
    }
  }, [attemptAction, board, onBoardChange, selectedSquare, updateSelectedHand, viewerOrientation]);

  const handleBoardClick = useCallback((event: React.MouseEvent<HTMLDivElement> | React.TouchEvent<HTMLDivElement>) => {
    if (!canEdit) return;
    if (pendingMove) return;

    const rect = event.currentTarget.getBoundingClientRect();
    let clientX: number | undefined;
    let clientY: number | undefined;

    if ("touches" in event) {
      if (event.touches.length > 0) {
        clientX = event.touches[0].clientX;
        clientY = event.touches[0].clientY;
      } else {
        return;
      }
    } else {
      clientX = (event as React.MouseEvent).clientX;
      clientY = (event as React.MouseEvent).clientY;
    }

    const xRel = clientX - rect.left;
    const yRel = clientY - rect.top;

    const rawX = Math.floor((xRel / rect.width) * 9);
    const rawY = Math.floor((yRel / rect.height) * 9);
    if (rawX < 0 || rawX > 8 || rawY < 0 || rawY > 8) return;

    const x = isGoteView ? 8 - rawX : rawX;
    const y = isGoteView ? 8 - rawY : rawY;
    const square = { x, y };

    // ダブルタップ直接昇格は純粋な盤面編集モード（onMove なし）のみ有効。
    // レッスン/パズルモード（onMove あり）では誤タップで駒が成ってしまうため無効化。
    if ("touches" in event && isTouchDoubleTap(square) && !onMove) {
      togglePromotionAt(square);
      return;
    }

    handleEditSquareClick(square);
    onSquareClick?.(square.x, square.y);
  }, [canEdit, pendingMove, isGoteView, isTouchDoubleTap, togglePromotionAt, handleEditSquareClick, onSquareClick, onMove]);

  const handleBoardDoubleClick = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    // レッスン/パズルモード（onMove あり）では直接昇格を無効化
    if (!canEdit || onMove) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const xRel = event.clientX - rect.left;
    const yRel = event.clientY - rect.top;

    const rawX = Math.floor((xRel / rect.width) * 9);
    const rawY = Math.floor((yRel / rect.height) * 9);
    if (rawX < 0 || rawX > 8 || rawY < 0 || rawY > 8) return;

    const x = isGoteView ? 8 - rawX : rawX;
    const y = isGoteView ? 8 - rawY : rawY;

    togglePromotionAt({ x, y });
  }, [canEdit, isGoteView, togglePromotionAt, onMove]);

  // ── 矢印の分離: from あり → ArrowOverlay / from なし → BoardHintsOverlay ──
  const { moveArrowData, dropArrows } = useMemo(() => {
    const move: ArrowDatum[] = [];
    const drop: HintArrow[] = [];
    for (const a of hintArrows) {
      if (a.from) {
        move.push({
          id: `${a.from.file}${a.from.rank}-${a.to.file}${a.to.rank}`,
          from: shogiToDisplay(a.from.file, a.from.rank, flipped),
          to: shogiToDisplay(a.to.file, a.to.rank, flipped),
        });
      } else {
        drop.push(a);
      }
    }
    return { moveArrowData: move, dropArrows: drop };
  }, [hintArrows, flipped]);

  const effectiveLastMove = mode === "edit" ? null : lastMove;
  const effectiveBestMove = mode === "edit" ? null : bestmove;

  const boardElement = (
      <div className="relative select-none shrink-0" style={{ width: boardSize, height: boardSize }}>
      <div
        className="absolute inset-0 rounded-xl shadow-2xl border-[6px] border-[#5d4037]"
        style={{
          background: "linear-gradient(135deg, #eecfa1 0%, #d4a373 100%)",
          boxShadow: "0 10px 30px -5px rgba(0, 0, 0, 0.5)",
        }}
      />

        {/* 9x9 マス領域のコンテナ（明示的に幅高を持たせる） */}
        <div
          ref={containerRef}
          data-shogi-board-root="1"
          className="relative overflow-visible"
          style={{ width: boardSize, height: boardSize }}
        >
          {/* ★ 矢印オーバーレイ（move 系: from→to）
              boardSize 不要 — absolute inset-0 w-full h-full で親追従 */}
          <ArrowOverlay
            arrows={moveArrowData}
            className="z-[9998]"
          />
          {/* ヒントマス + drop 系矢印 */}
          <BoardHintsOverlay
            hintSquares={hintSquares ?? []}
            hintArrows={dropArrows}
            coordMode="shogi"
            className="absolute inset-0 z-[9999] text-amber-400"
            flipped={flipped}
          />
          <svg width={boardSize} height={boardSize} className="absolute inset-0 pointer-events-none z-0">
          {/* 合法打ち先ハイライト (SVG rect — 罫線と同じ座標系で確実に一致) */}
          {selectedHand && legalDropSquares.map((sq) => {
            const display = getDisplayPos(sq.x, sq.y);
            return (
              <rect
                key={`drop-hl-${sq.x}-${sq.y}`}
                x={display.x * CELL_SIZE}
                y={display.y * CELL_SIZE}
                width={CELL_SIZE}
                height={CELL_SIZE}
                fill="rgba(0,0,0,0.30)"
              />
            );
          })}
          {[...Array(10)].map((_, i) => (
            <line
              key={`v-${i}`}
              x1={i * CELL_SIZE}
              y1={0}
              x2={i * CELL_SIZE}
              y2={boardSize}
              stroke="#5d4037"
              strokeWidth={i === 0 || i === 9 ? 2 : 1}
            />
          ))}
          {[...Array(10)].map((_, i) => (
            <line
              key={`h-${i}`}
              x1={0}
              y1={i * CELL_SIZE}
              x2={boardSize}
              y2={i * CELL_SIZE}
              stroke="#5d4037"
              strokeWidth={i === 0 || i === 9 ? 2 : 1}
            />
          ))}
          </svg>

          <div className="absolute inset-0 pointer-events-none z-[1]">
          {HOSHI_POINTS.map(({ file, rank }) => {
            const display = getDisplayPos(file - 1, rank - 1);
            return (
              <div
                key={`hoshi-${file}-${rank}`}
                className="absolute h-1.5 w-1.5 rounded-full bg-amber-900"
                style={{
                  left: `${((display.x + 0.5) / 9) * 100}%`,
                  top: `${((display.y + 0.5) / 9) * 100}%`,
                  transform: "translate(-50%, -50%)",
                }}
              />
            );
          })}
          </div>

          <div className="absolute inset-0 grid grid-cols-9 grid-rows-9 z-[15] pointer-events-none">
          {[...Array(81)].map((_, index) => {
            const x = index % 9;
            const y = Math.floor(index / 9);
            const display = getDisplayPos(x, y);
            const isSelected = selectedSquare && selectedSquare.x === x && selectedSquare.y === y;
            const isZone = showPromotionZone && isPromotionZone(y);
            const isLegalDropHighlight = selectedHand ? legalDropSquareKeySet.has(`${x},${y}`) : false;

            const hasHintStar = visibleHintStars.some((s) => s.x === x && s.y === y);

            return (
              <div
                key={`hl-${x}-${y}`}
                className={isZone ? "animate-pulse" : ""}
                style={{
                  gridColumnStart: display.x + 1,
                  gridRowStart: display.y + 1,
                  backgroundColor: (() => {
                    if (mode === "edit" && isSelected) return "rgba(251, 191, 36, 0.5)";
                    if (isHintSquare(x, y)) return "rgba(250, 204, 21, 0.28)";
                    if (isHighlighted(x, y)) return "rgba(59, 130, 246, 0.18)";
                    if (isLegalDropHighlight) return "rgba(0, 0, 0, 0.35)";
                    if (isZone) return "rgba(239, 68, 68, 0.25)";
                    return "transparent";
                  })(),
                  boxShadow: isLegalDropHighlight ? "inset 0 0 0 1px rgba(0,0,0,0.32)" : undefined,
                  overflow: "visible",
                }}
              >
                {hasHintStar && (
                  <img
                    src="/images/lesson/star.png"
                    alt=""
                    draggable={false}
                    style={{
                      display: "block",
                      width: "100%",
                      height: "100%",
                      padding: "10%",
                      boxSizing: "border-box",
                      zIndex: 9997,
                      pointerEvents: "none",
                    }}
                  />
                )}
              </div>
            );
          })}
          </div>

          <div
            className="absolute inset-0 z-10 pointer-events-none"
            style={{ transform: "translateY(var(--piece-offset-y, 0px))" }}
          >
          {placedPieces.map((piece, idx) => {
            const display = getDisplayPos(piece.x, piece.y);
            const pieceOwner = getPieceOwner(piece.piece);
            const pieceBase = piece.piece.replace("+", "").toUpperCase() as PieceBase;
            const isViewerPiece = pieceOwner === viewerOrientation;
            const shiftY = isViewerPiece ? PIECE_OFFSET_Y_OWN_PX : PIECE_OFFSET_Y_OPPONENT_PX;
            const isMovingPiece =
              Boolean(selectedSquare) && selectedSquare!.x === piece.x && selectedSquare!.y === piece.y && canEdit;
            const activeMotion = pieceMotionRules.find((r) => {
              const m = r.match;
              if (typeof m.x === "number" && m.x !== piece.x) return false;
              if (typeof m.y === "number" && m.y !== piece.y) return false;
              if (m.owner && m.owner !== pieceOwner) return false;
              if (m.piece && m.piece !== piece.piece) return false;
              if (m.pieceBase && m.pieceBase !== pieceBase) return false;
              return true;
            })?.motion;
            const stableKey = `sq:${piece.x}:${piece.y}:${piece.piece}`;
            return (
              <div
                key={stableKey}
                className="contents"
              >
                <PieceSprite
                  dataShogiPiece="1"
                  dataBoardDisplayX={display.x}
                  dataBoardDisplayY={display.y}
                  piece={piece.piece}
                  x={display.x}
                  y={display.y}
                  size={PIECE_SIZE}
                  cellSize={CELL_SIZE}
                  shiftY={shiftY}
                  owner={pieceOwner}
                  orientationMode={orientationMode}
                  viewerSide={viewerOrientation}
                  style={isMovingPiece ? { opacity: 0.55 } : undefined}
                  scaleMultiplier={isMovingPiece ? 1.15 : undefined}
                  motionConfig={activeMotion}
                />
              </div>
            );
          })}
          </div>

          {effectiveBestMove && (
            <svg width={boardSize} height={boardSize} className="absolute inset-0 pointer-events-none z-30">
              <Arrow
                x1={getDisplayPos(effectiveBestMove.from.x, effectiveBestMove.from.y).x * CELL_SIZE + CELL_SIZE / 2}
                y1={getDisplayPos(effectiveBestMove.from.x, effectiveBestMove.from.y).y * CELL_SIZE + CELL_SIZE / 2}
                x2={getDisplayPos(effectiveBestMove.to.x, effectiveBestMove.to.y).x * CELL_SIZE + CELL_SIZE / 2}
                y2={getDisplayPos(effectiveBestMove.to.x, effectiveBestMove.to.y).y * CELL_SIZE + CELL_SIZE / 2}
              />
            </svg>
          )}

          {/* 盤面クリック用レイヤー（z=100） */}
          <div
            className="absolute top-0 left-0 z-[100]"
            style={{
              width: `${boardSize}px`,
              height: `${boardSize}px`,
              backgroundColor: "transparent",
              cursor: mode === "edit" ? "pointer" : "default",
              pointerEvents: "auto",
              WebkitTapHighlightColor: "transparent",
            }}
            onClick={handleBoardClick}
            onDoubleClick={handleBoardDoubleClick}
          />

          {pendingMove && (() => {
            const pieceOwner = getPieceOwner(pendingMove.piece);
            const viewerSide = viewerOrientation;
            const spriteSize = Math.max(64, Math.round(CELL_SIZE * 1.4 * pieceScale * PIECE_SIZE_MULTIPLIER));
            const btnSize = Math.round(boardSize * 0.42);

            const doPromote = () => executeMove(
              pendingMove.sourceSquare,
              pendingMove.targetSquare,
              promotePiece(pendingMove.piece) as PieceCode,
              false,
            );
            const doKeep = () => executeMove(
              pendingMove.sourceSquare,
              pendingMove.targetSquare,
              pendingMove.piece,
              false,
            );

            return (
              // Full-board overlay: covers entire board so taps always hit buttons regardless of CSS scale transforms
              <div
                style={{
                  position: "absolute", inset: 0, zIndex: 200,
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 12,
                  background: "rgba(0,0,0,0.45)",
                  touchAction: "none",
                }}
                onClick={() => setPendingMove(null)}
                onTouchEnd={(e) => {
                  e.preventDefault();
                  setPendingMove(null);
                }}
              >
                {/* 成り button */}
                <div
                  role="button"
                  style={{
                    width: btnSize, height: btnSize,
                    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                    gap: 8,
                    background: "#fef3c7", border: "3px solid #d97706", borderRadius: 20,
                    cursor: "pointer", userSelect: "none", WebkitUserSelect: "none",
                    boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
                  }}
                  onClick={(e) => { e.stopPropagation(); doPromote(); }}
                  onTouchEnd={(e) => { e.preventDefault(); e.stopPropagation(); doPromote(); }}
                >
                  <div style={{ position: "relative", width: spriteSize, height: spriteSize, flexShrink: 0 }}>
                    <PieceSprite
                      piece={promotePiece(pendingMove.piece) as PieceCode}
                      x={0} y={0}
                      size={spriteSize} cellSize={spriteSize}
                      orientationMode="sprite"
                      owner={pieceOwner} viewerSide={viewerSide}
                    />
                  </div>
                  <span style={{ fontWeight: 900, color: "#92400e", fontSize: 44, lineHeight: 1 }}>成</span>
                </div>

                {/* 不成 button */}
                <div
                  role="button"
                  style={{
                    width: btnSize, height: btnSize,
                    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                    gap: 8,
                    background: "#f1f5f9", border: "3px solid #94a3b8", borderRadius: 20,
                    cursor: "pointer", userSelect: "none", WebkitUserSelect: "none",
                    boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
                  }}
                  onClick={(e) => { e.stopPropagation(); doKeep(); }}
                  onTouchEnd={(e) => { e.preventDefault(); e.stopPropagation(); doKeep(); }}
                >
                  <div style={{ position: "relative", width: spriteSize, height: spriteSize, flexShrink: 0 }}>
                    <PieceSprite
                      piece={pendingMove.piece}
                      x={0} y={0}
                      size={spriteSize} cellSize={spriteSize}
                      orientationMode="sprite"
                      owner={pieceOwner} viewerSide={viewerSide}
                    />
                  </div>
                  <span style={{ fontWeight: 900, color: "#374151", fontSize: 44, lineHeight: 1 }}>不成</span>
                </div>
              </div>
            );
          })()}

          {choiceDialog && (() => {
            const btnSize = Math.round(boardSize * 0.42);
            return (
              <div
                style={{
                  position: "absolute", inset: 0, zIndex: 210,
                  display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12,
                  background: "transparent",
                  touchAction: "none",
                }}
                onClick={(e) => e.stopPropagation()}
                onTouchEnd={(e) => e.preventDefault()}
              >
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, transform: "translateY(24px)" }}>
                  <div
                    style={{
                      maxWidth: Math.round(boardSize * 0.9),
                      background: "rgba(255,247,237,0.96)",
                      border: "2px solid #f59e0b",
                      borderRadius: 14,
                      padding: "10px 14px",
                      color: "#7c2d12",
                      fontWeight: 800,
                      textAlign: "center",
                      boxShadow: "0 4px 20px rgba(0,0,0,0.18)",
                    }}
                  >
                    {choiceDialog.prompt}
                  </div>

                  <div style={{ display: "flex", gap: 12 }}>
                  {choiceDialog.options.map((opt) => (
                    <div
                      key={opt.label}
                      role="button"
                      style={{
                        width: btnSize,
                        height: btnSize,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        background: "#fef3c7",
                        border: "3px solid #d97706",
                        borderRadius: 20,
                        cursor: "pointer",
                        userSelect: "none",
                        WebkitUserSelect: "none",
                        boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
                        fontWeight: 900,
                        color: "#7c2d12",
                        fontSize: 22,
                        lineHeight: 1.2,
                        textAlign: "center",
                        padding: 10,
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        opt.onSelect();
                      }}
                      onTouchEnd={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        opt.onSelect();
                      }}
                    >
                      {opt.label}
                    </div>
                  ))}
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
    </div>
  );

  const topFileLabels = viewerOrientation === "sente" ? FILE_LABELS_SENTE : FILE_LABELS_GOTE;
  const rightRankLabels = viewerOrientation === "sente" ? RANK_LABELS_SENTE : RANK_LABELS_GOTE;
  const labelGap = showCoordinates ? LABEL_GAP : 0;

  const boardWithLabels = (
    <div
      className="grid select-none"
      style={{
        // NOTE: We intentionally do NOT apply `--piece-scale` here.
        // Scaling the entire board container can make the whole lesson feel "zoomed".
        // Instead, scale at the specific usage site (training mobile shells) if needed.
        gridTemplateColumns: `repeat(9, ${CELL_SIZE}px) ${labelGap}px`,
        gridTemplateRows: `${labelGap}px repeat(9, ${CELL_SIZE}px)`,
        gap: 0,
      }}
    >
      <div style={{ gridColumn: "1 / span 9", gridRow: "2 / span 9" }}>{boardElement}</div>

      {showCoordinates
        ? topFileLabels.map((label, index) => (
            <div
              key={`file-top-${label}-${index}`}
              className="flex items-center justify-center text-xs font-bold text-[#5d4037]"
              style={{ gridColumn: index + 1, gridRow: 1 }}
            >
              {label}
            </div>
          ))
        : null}

      {showCoordinates
        ? rightRankLabels.map((label, index) => (
            <div
              key={`rank-right-${label}-${index}`}
              className="flex items-center justify-center text-xs font-bold text-[#5d4037]"
              style={{ gridColumn: 10, gridRow: index + 2 }}
            >
              {label}
            </div>
          ))
        : null}
    </div>
  );

  if (!hands || !showHands) return boardWithLabels;

  // 「上＝相手」「下＝自分」をビュー基準で維持
  const topHandSide = viewerOrientation === "sente" ? "w" : "b";
  const bottomHandSide = viewerOrientation === "sente" ? "b" : "w";

  // ★ corners: 盤面の左上 & 右下に重ねる
  if (handsPlacement === "corners") {
    return (
      <div className="relative inline-block">
        {boardWithLabels}

        {/* 相手の持ち駒：盤面 左上（ラベル分だけ下にずらす） */}
        <div
          className="absolute z-[160] pointer-events-auto"
          style={{
            left: 6,
            top: labelGap + 6,
          }}
        >
          <HandArea
            side={topHandSide}
            hands={hands[topHandSide]}
            orientationMode={orientationMode}
            viewerSide={viewerOrientation}
            cellSize={HAND_CELL_SIZE}
            pieceSize={HAND_PIECE_SIZE}
            shiftYForViewer={PIECE_OFFSET_Y_OWN_PX}
            shiftYForOpponent={PIECE_OFFSET_Y_OPPONENT_PX}
            canEdit={canEdit}
            selectedHand={selectedHand}
            onHandClick={handleHandClick}
            compact
          />
        </div>

        {/* 自分の持ち駒：盤面 右下（右のラベル分だけ左にずらす） */}
        <div
          className="absolute z-[160] pointer-events-auto"
          style={{
            right: labelGap + 6,
            bottom: 6,
          }}
        >
          <HandArea
            side={bottomHandSide}
            hands={hands[bottomHandSide]}
            orientationMode={orientationMode}
            viewerSide={viewerOrientation}
            cellSize={HAND_CELL_SIZE}
            pieceSize={HAND_PIECE_SIZE}
            shiftYForViewer={PIECE_OFFSET_Y_OWN_PX}
            shiftYForOpponent={PIECE_OFFSET_Y_OPPONENT_PX}
            canEdit={canEdit}
            selectedHand={selectedHand}
            onHandClick={handleHandClick}
            compact
          />
        </div>
      </div>
    );
  }

  // default: これまで通り上下
  return (
    <div className={compactHands ? "flex flex-col items-center gap-1" : "flex flex-col items-center gap-3"}>
      <HandArea
        side={topHandSide}
        hands={hands[topHandSide]}
        orientationMode={orientationMode}
        viewerSide={viewerOrientation}
        cellSize={HAND_CELL_SIZE}
        pieceSize={HAND_PIECE_SIZE}
        shiftYForViewer={PIECE_OFFSET_Y_OWN_PX}
        shiftYForOpponent={PIECE_OFFSET_Y_OPPONENT_PX}
        canEdit={canEdit}
        selectedHand={selectedHand}
        onHandClick={handleHandClick}
        dense={compactHands}
      />
      {boardWithLabels}
      <HandArea
        side={bottomHandSide}
        hands={hands[bottomHandSide]}
        orientationMode={orientationMode}
        viewerSide={viewerOrientation}
        cellSize={HAND_CELL_SIZE}
        pieceSize={HAND_PIECE_SIZE}
        shiftYForViewer={PIECE_OFFSET_Y_OWN_PX}
        shiftYForOpponent={PIECE_OFFSET_Y_OPPONENT_PX}
        canEdit={canEdit}
        selectedHand={selectedHand}
        onHandClick={handleHandClick}
        dense={compactHands}
      />
    </div>
  );
};

// -------------------------
// HandArea と Arrow
// -------------------------
type HandAreaProps = {
  side: "b" | "w";
  hands?: Partial<Record<PieceBase, number>>;
  orientationMode: OrientationMode;
  viewerSide: "sente" | "gote";
  cellSize: number;
  pieceSize: number;
  /** 自分の駒の縦オフセット（px）。盤面の PIECE_OFFSET_Y_OWN_PX に合わせる */
  shiftYForViewer?: number;
  /** 相手の駒の縦オフセット（px）。盤面の PIECE_OFFSET_Y_OPPONENT_PX に合わせる */
  shiftYForOpponent?: number;
  canEdit?: boolean;
  selectedHand?: SelectedHand;
  onHandClick?: (base: PieceBase, side: "b" | "w") => void;

  /** corners 用：ラベル小さくして圧縮表示 */
  compact?: boolean;
  /** default 用：上下の持ち駒欄をやや圧縮 */
  dense?: boolean;
};

const HandArea: React.FC<HandAreaProps> = ({
  side,
  hands,
  orientationMode,
  viewerSide,
  cellSize,
  pieceSize,
  shiftYForViewer = 0,
  shiftYForOpponent = 0,
  canEdit,
  selectedHand,
  onHandClick,
  compact = false,
  dense = false,
}) => {
  const owner = side === "b" ? "sente" : "gote";
  const label = owner === "sente" ? "先手の持ち駒" : "後手の持ち駒";
  const isViewerHand = owner === viewerSide;
  const shiftY = isViewerHand ? shiftYForViewer : shiftYForOpponent;

  const items = HAND_ORDER.map((base) => {
    const count = hands?.[base];
    if (!count) return null;

    const piece = (side === "b" ? base : base.toLowerCase()) as PieceCode;
    const isSelected = selectedHand && selectedHand.base === base && selectedHand.side === side;

    return (
      <div
        key={`${side}-${base}`}
        className="relative transition-transform"
        data-testid={base === "P" ? `hand-piece-${owner}-P` : undefined}
        style={{
          width: cellSize,
          height: cellSize,
          cursor: canEdit ? "pointer" : "default",
          WebkitTapHighlightColor: "transparent",
          WebkitUserSelect: "none",
          userSelect: "none",
        }}
        onClick={() => canEdit && onHandClick?.(base, side)}
        onTouchEnd={(e) => {
          e.preventDefault();
          if (canEdit) onHandClick?.(base, side);
        }}
      >
        <PieceSprite
          piece={piece}
          x={0}
          y={0}
          size={pieceSize}
          cellSize={cellSize}
          shiftY={shiftY}
          orientationMode={orientationMode}
          owner={owner}
          viewerSide={viewerSide}
          style={canEdit && isSelected ? { opacity: 0.55 } : undefined}
          scaleMultiplier={canEdit && isSelected ? 1.15 : undefined}
        />
        {count > 1 && (
          <span className="absolute -top-1 -right-1 rounded-full bg-[#fef1d6] px-1 text-xs font-semibold text-[#2b2b2b] border border-black/10">
            {count}
          </span>
        )}
      </div>
    );
  }).filter(Boolean) as React.ReactNode[];

  return (
    <div
      className={
        compact
          ? "flex flex-col items-start justify-start gap-1"
          : dense
            ? "flex flex-col items-center justify-center gap-0.5 h-[52px] shrink-0"
            : "flex flex-col items-center justify-center gap-1 min-h-[60px]"
      }
    >
      {!compact && <span className="text-xs font-semibold text-[#5d4037]">{label}</span>}
      <div className={compact ? "flex items-center justify-start gap-2" : dense ? "flex items-center justify-center gap-1.5 min-h-[40px]" : "flex items-center justify-center gap-2"}>
        {items.length ? items : <span className="text-xs text-slate-500">--</span>}
      </div>
    </div>
  );
};

const Arrow: React.FC<{ x1: number; y1: number; x2: number; y2: number }> = ({ x1, y1, x2, y2 }) => {
  if (x1 === x2 && y1 === y2) return null;
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const length = Math.hypot(x2 - x1, y2 - y1);
  const startX = x1 + Math.cos(angle) * 10;
  const startY = y1 + Math.sin(angle) * 10;
  const endX = x1 + Math.cos(angle) * (length - 10);
  const endY = y1 + Math.sin(angle) * (length - 10);

  return (
    <g>
      <line
        x1={startX}
        y1={startY}
        x2={endX}
        y2={endY}
        stroke="#22c55e"
        strokeWidth={4}
        strokeOpacity={0.6}
        strokeLinecap="round"
      />
      <polygon
        points={`${endX},${endY} ${endX - 10 * Math.cos(angle - Math.PI / 6)},${endY - 10 * Math.sin(angle - Math.PI / 6)} ${endX - 10 * Math.cos(angle + Math.PI / 6)},${endY - 10 * Math.sin(angle + Math.PI / 6)}`}
        fill="#22c55e"
        fillOpacity={0.8}
      />
    </g>
  );
};

"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ShogiBoard, type BoardMode, type SelectedHand } from "@/components/ShogiBoard";
import { PieceSprite, type OrientationMode } from "@/components/PieceSprite";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { showToast } from "@/components/ui/toast";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import {
  boardToPlaced,
  buildBoardTimeline,
  buildPositionFromUsi,
  getStartBoard,
  applyMove,
  type BoardMatrix,
  type HandsState,
  type Side,
} from "@/lib/board";
import { toStartposUSI } from "@/lib/ingest";
import { formatUsiMoveJapanese, usiMoveToCoords, type PieceBase, type PieceCode } from "@/lib/sfen";
import { buildUsiPositionForPly } from "@/lib/usi";
import type { EngineAnalyzeResponse, EngineMultipvItem } from "@/lib/annotateHook";
import { buildMoveImpacts, getPrimaryEvalScore } from "@/lib/analysisUtils";
import { FileText, RotateCcw, Search, Play, Sparkles, Upload, ChevronFirst, ChevronLeft, ChevronRight, ChevronLast, ArrowRight, BrainCircuit, X, ScrollText, Eye, ArrowLeft, Pencil, ArrowLeftRight, GraduationCap, BookOpen } from "lucide-react";
import MoveListPanel from "@/components/annotate/MoveListPanel";
import EvalGraph from "@/components/annotate/EvalGraph";
import BioshogiPanel from "@/components/annotate/BioshogiPanel";
import { useBatchAnalysis } from "@/hooks/useBatchAnalysis";
import { useDigest } from "@/hooks/useDigest";
import { useExplanation } from "@/hooks/useExplanation";
import { useRealtimeAnalysis } from "@/hooks/useRealtimeAnalysis";
import { useBoardEdit } from "@/hooks/useBoardEdit";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8787";

const HAND_DISPLAY_ORDER: PieceBase[] = ["P", "L", "N", "S", "G", "B", "R", "K"];

const formatHandLabel = (base: PieceBase): string => { 
    switch (base) { case "P": return "歩"; case "L": return "香"; case "N": return "桂"; case "S": return "銀"; case "G": return "金"; case "B": return "角"; case "R": return "飛"; case "K": return "玉"; default: return base; } 
};

type HandsColumnProps = { 
    side: Side; 
    hands: Partial<Record<PieceBase, number>>; 
    orientationMode: OrientationMode; 
    align?: "start" | "end";
    isEditMode?: boolean;
    selectedHand?: SelectedHand;
    onHandClick?: (base: PieceBase, side: Side) => void;
};

const HandsColumn: React.FC<HandsColumnProps> = ({ side, hands, orientationMode, align = "start", isEditMode, selectedHand, onHandClick }) => {
  const owner = side === "b" ? "sente" : "gote";
  const entries = HAND_DISPLAY_ORDER.map((base) => {
    const count = hands?.[base];
    if (!count) return null;
    const piece = (side === "b" ? base : base.toLowerCase()) as PieceCode;
    const isSelected = selectedHand && selectedHand.base === base && selectedHand.side === side;
    
    return (
      <div 
        key={`${side}-${base}`} 
        className={`flex items-center gap-2 text-sm text-[#2b1c10] transition-all rounded-md p-1 ${isEditMode ? "cursor-pointer hover:bg-amber-100" : ""} ${isSelected ? "bg-amber-200 ring-2 ring-amber-400" : ""}`}
        onClick={() => isEditMode && onHandClick?.(base, side)}
      >
        <div className="relative h-10 w-10">
          <PieceSprite piece={piece} x={0} y={0} size={34} cellSize={40} orientationMode={orientationMode} owner={owner} />
          {count > 1 && <span className="absolute -top-1 -right-1 rounded-full bg-white/90 px-1 text-xs font-semibold text-[#2b1c10]">x{count}</span>}
        </div>
        <span className="font-semibold">{formatHandLabel(base)} x{count}</span>
      </div>
    );
  }).filter(Boolean) as React.ReactNode[];
  
  return (
    <div className={`flex w-24 flex-col gap-3 ${align === "end" ? "self-end items-end text-right" : "items-start text-left"}`}>
      <span className="text-xs font-semibold text-[#7a5f36]">{side === "b" ? "先手の持ち駒" : "後手の持ち駒"}</span>
      <div className="flex flex-col gap-2">{entries.length ? entries : <span className="text-[11px] text-[#9a8a78]">持ち駒なし</span>}</div>
    </div>
  );
};

const convertFullPvToJapanese = (baseUsi: string, pv: string): string => {
    if (!pv) return "";
    const moves = pv.trim().split(" ");
    const displayMoves = moves.slice(0, 5);
    try {
        const baseMoveCount = baseUsi.split(" ").filter(s => s !== "startpos" && s !== "moves").length;
        const fullUsi = baseUsi + " " + displayMoves.join(" ");
        const timeline = buildBoardTimeline(fullUsi);
        const result: string[] = [];
        for (let i = 0; i < displayMoves.length; i++) {
            const boardState = timeline.boards[baseMoveCount + i];
            const turn = (baseMoveCount + i) % 2 === 0 ? "b" : "w";
            if (!boardState) break;
            const placed = boardToPlaced(boardState);
            const jp = formatUsiMoveJapanese(displayMoves[i], placed, turn);
            result.push(jp);
        }
        return result.join(" ");
    } catch { return pv; }
};

const boardToSfen = (board: BoardMatrix, hands: HandsState, turn: Side): string => {
  let sfen = "";
  let emptyCount = 0;
  for (let y = 0; y < 9; y++) {
    for (let x = 0; x < 9; x++) {
      const piece = board[y][x];
      if (piece) {
        if (emptyCount > 0) { sfen += emptyCount.toString(); emptyCount = 0; }
        sfen += piece;
      } else { emptyCount++; }
    }
    if (emptyCount > 0) { sfen += emptyCount.toString(); emptyCount = 0; }
    if (y < 8) sfen += "/";
  }
  sfen += ` ${turn} `;
  const handOrder: PieceBase[] = ["R", "B", "G", "S", "N", "L", "P"];
  let handStr = "";
  handOrder.forEach((p) => {
    const count = hands.b[p] || 0;
    if (count === 1) handStr += p; else if (count > 1) handStr += count + p;
  });
  handOrder.forEach((p) => {
    const count = hands.w[p] || 0;
    if (count === 1) handStr += p.toLowerCase(); else if (count > 1) handStr += count + p.toLowerCase();
  });
  if (handStr === "") handStr = "-";
  sfen += handStr;
  sfen += " 1";
  return `sfen ${sfen}`;
};

const flipTurn = (side: Side): Side => (side === "b" ? "w" : "b");
const clampIndex = (index: number, boards: BoardMatrix[]): number => {
  if (!boards.length) return 0;
  return Math.max(0, Math.min(index, boards.length - 1));
};
const formatScoreLabel = (score?: EngineMultipvItem["score"]): string => {
  if (!score) return "?";
  if (score.type === "mate") return typeof score.mate === "number" && score.mate !== 0 ? `Mate ${score.mate}` : "Mate";
  const cp = typeof score.cp === "number" ? score.cp : 0;
  return `${cp > 0 ? "+" : ""}${cp}cp`;
};

// ヘルパー関数: 指定手数でUSI文字列をカットする
const getSubsetUSI = (originalUsi: string, ply: number): string => {
  const parts = originalUsi.trim().split(" moves ");
  const header = parts[0]; 
  const moveStr = parts[1];
  
  if (!moveStr) return header;
  
  const moves = moveStr.trim().split(" ");
  
  if (ply === 0) return header;

  const neededMoves = moves.slice(0, ply);
  
  if (neededMoves.length === 0) return header;
  
  return `${header} moves ${neededMoves.join(" ")}`;
};

type AnalysisTabProps = {
  usi: string;
  setUsi: (next: string) => void;
  orientationMode?: OrientationMode;
};

export default function AnalysisTab({ usi, setUsi, orientationMode = "sprite" }: AnalysisTabProps) {
  const router = useRouter();
  const [currentPly, setCurrentPly] = useState(0);

  const {
    batchData,
    setBatchData,
    isBatchAnalyzing,
    setIsBatchAnalyzing,
    progress: batchProgress,
    runBatchAnalysis,
    cancelBatchAnalysis,
    resetBatchData
  } = useBatchAnalysis();

  const [kifuText, setKifuText] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isEditMode, setIsEditMode] = useState(false);
  const [isTsumeMode, setIsTsumeMode] = useState(false);
  const [isLearningMenuOpen, setIsLearningMenuOpen] = useState(false);
  const [isRoadmapOpen, setIsRoadmapOpen] = useState(false);
  const [boardOrientation, setBoardOrientation] = useState<"sente" | "gote">("sente");
  const [selectedHand, setSelectedHand] = useState<SelectedHand>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);

  const [previewSequence, setPreviewSequence] = useState<string[] | null>(null);
  const [previewStep, setPreviewStep] = useState<number>(0);

  const timeline = useMemo(() => {
    try { return buildBoardTimeline(usi); } 
    catch { return { boards: [getStartBoard()], hands: [{ b: {}, w: {} }], moves: [] }; }
  }, [usi]);

  const parsedPosition = useMemo(() => {
    try { return buildPositionFromUsi(usi); } 
    catch { return { board: getStartBoard(), moves: [], turn: "b" as Side }; }
  }, [usi]);

  const initialTurn = useMemo(() => {
    const moveCount = parsedPosition.moves.length;
    return moveCount % 2 === 0 ? parsedPosition.turn : flipTurn(parsedPosition.turn);
  }, [parsedPosition.moves.length, parsedPosition.turn]);

  const moveSequence = timeline.moves;
  const totalMoves = moveSequence.length;
  const maxPly = totalMoves;
  const safeCurrentPly = useMemo(() => clampIndex(currentPly, timeline.boards), [currentPly, timeline.boards]);

  const {
    realtimeAnalysis,
    setRealtimeAnalysis,
    isAnalyzing,
    setIsAnalyzing,
    stopEngineAnalysis,
    startEngineAnalysis,
    requestAnalysisForPly,
    disconnectStream,
    cleanup: cleanupRealtimeAnalysis,
  } = useRealtimeAnalysis({ safeCurrentPly, isEditMode, usi });

  const {
    snapshotOverrides,
    handsOverrides,
    editHistory,
    handleUndo,
    handleBoardEdit: handleBoardEditRaw,
    handleHandsEdit: handleHandsEditRaw,
    clearEditHistory,
    resetBoardEdit,
  } = useBoardEdit({ safeCurrentPly, isEditMode, isTsumeMode, isAnalyzing, stopEngineAnalysis });

  const baseBoard = timeline.boards[safeCurrentPly] ?? getStartBoard();

  const previewState = useMemo(() => {
    if (!previewSequence) return null;
    const currentUsi = getSubsetUSI(usi, safeCurrentPly);
    if (!currentUsi) return null;

    const activeMoves = previewSequence.slice(0, previewStep);

    const baseStr = currentUsi;
    const connector = baseStr.includes("moves") ? " " : " moves ";
    const finalUsi = activeMoves.length > 0 ? baseStr + connector + activeMoves.join(" ") : baseStr;

    try {
        const previewTimeline = buildBoardTimeline(finalUsi);
        const lastIndex = previewTimeline.boards.length - 1;
        return {
            board: previewTimeline.boards[lastIndex],
            hands: previewTimeline.hands[lastIndex],
            lastMove: previewTimeline.moves[previewTimeline.moves.length - 1]
        };
    } catch {
        return null;
    }
  }, [previewSequence, previewStep, usi, safeCurrentPly]);

  const displayedBoard = previewState ? previewState.board : (snapshotOverrides[safeCurrentPly] ?? baseBoard);
  const fallbackHands = useMemo<HandsState>(() => ({ b: {}, w: {} }), []);
  const timelineHands = useMemo<HandsState[]>(() => timeline.hands ?? [], [timeline.hands]);
  const baseHands = timelineHands[safeCurrentPly] ?? fallbackHands;
  const activeHands = previewState ? previewState.hands : (handsOverrides[safeCurrentPly] ?? baseHands);

  // useBoardEdit の raw ハンドラに現在の盤面・持駒を束縛
  const handleBoardEdit = useCallback((next: BoardMatrix) => {
    handleBoardEditRaw(next, displayedBoard, activeHands);
  }, [handleBoardEditRaw, displayedBoard, activeHands]);

  const handleHandsEdit = useCallback((next: HandsState) => {
    handleHandsEditRaw(next, displayedBoard, activeHands);
  }, [handleHandsEditRaw, displayedBoard, activeHands]);

  const timelinePlacedPieces = useMemo(() => {
    if (!timeline.boards.length) return [boardToPlaced(getStartBoard())];
    return timeline.boards.map((board) => boardToPlaced(board));
  }, [timeline.boards]);

  const currentPlacedPieces = useMemo(() => boardToPlaced(displayedBoard), [displayedBoard]);
  const currentSideToMove = useMemo(() => {
    let side = initialTurn;
    if (safeCurrentPly % 2 === 1) side = flipTurn(side);
    return side;
  }, [safeCurrentPly, initialTurn]);

  const evalSource = useMemo(() => {
    return { ...batchData, ...realtimeAnalysis };
  }, [batchData, realtimeAnalysis]);

  const moveImpacts = useMemo(
    () => buildMoveImpacts(evalSource, totalMoves, initialTurn),
    [evalSource, initialTurn, totalMoves]
  );

  const {
    gameDigest,
    digestMetaSource,
    bioshogiData,
    isDigesting,
    digestCooldownLeft,
    isReportModalOpen,
    setIsReportModalOpen,
    handleGenerateGameDigest,
    resetDigest,
  } = useDigest({
    batchData,
    isBatchAnalyzing,
    totalMoves,
    moveSequence,
    moveImpacts,
    initialTurn,
    usi,
  });

  const {
    explanation,
    isExplaining,
    handleGenerateExplanation,
    resetExplanation,
  } = useExplanation({
    isEditMode,
    safeCurrentPly,
    initialTurn,
    displayedBoard,
    activeHands,
    evalSource,
    moveSequence,
    timelineBoards: timeline.boards,
    timelineHands,
    moveImpacts,
    boardToSfen,
  });

  const currentAnalysis = evalSource[safeCurrentPly];
  const hasCurrentAnalysis = Boolean(currentAnalysis);
  
  const showArrow = !isEditMode && (isAnalyzing || !!currentAnalysis);

  const bestmoveCoords = (showArrow && currentAnalysis?.bestmove) 
      ? usiMoveToCoords(currentAnalysis.bestmove) 
      : null;
  
  const prevMove = safeCurrentPly > 0 ? moveSequence[safeCurrentPly - 1] : null;
  const lastMoveCoords = previewState 
      ? (previewState.lastMove ? usiMoveToCoords(previewState.lastMove) : null)
      : (!isEditMode && prevMove ? usiMoveToCoords(prevMove) : null);
  
  const handleHandClick = useCallback((base: PieceBase, side: Side) => {
    if (!isEditMode) return;
    if (selectedHand && selectedHand.base === base && selectedHand.side === side) {
        setSelectedHand(null);
    } else {
        setSelectedHand({ base, side });
    }
  }, [isEditMode, selectedHand]);

  // ★修正: 手数を変更したときの処理
  const handlePlyChange = useCallback((nextPly: number) => {
    if (isEditMode) return;

    // ここで stopEngineAnalysis() を呼んでしまうと「検討モード」自体がOFFになってしまうため削除。
    // 代わりに「通信だけ」を切断して、リソースを解放する。
    disconnectStream();

    setPreviewSequence(null);
    setPreviewStep(0);
    setCurrentPly(clampIndex(nextPly, timeline.boards));
  }, [isEditMode, timeline.boards, disconnectStream]);

  const goToStart = useCallback(() => {
      if (previewSequence) {
          setPreviewStep(0);
      } else {
          handlePlyChange(0);
      }
  }, [handlePlyChange, previewSequence]);

  const goToPrev = useCallback(() => {
      if (previewSequence) {
          setPreviewStep(p => Math.max(0, p - 1));
      } else {
          handlePlyChange(safeCurrentPly - 1);
      }
  }, [handlePlyChange, safeCurrentPly, previewSequence]);

  const goToNext = useCallback(() => {
      if (previewSequence) {
          setPreviewStep(p => Math.min(previewSequence.length, p + 1));
      } else {
          handlePlyChange(safeCurrentPly + 1);
      }
  }, [handlePlyChange, safeCurrentPly, previewSequence]);

  const goToEnd = useCallback(() => {
      if (previewSequence) {
          setPreviewStep(previewSequence.length);
      } else {
          handlePlyChange(maxPly);
      }
  }, [handlePlyChange, maxPly, previewSequence]);
  
  const navDisabled = isEditMode;
  const canGoPrev = previewSequence ? previewStep > 0 : safeCurrentPly > 0;
  const canGoNext = previewSequence ? previewStep < previewSequence.length : safeCurrentPly < maxPly;

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isEditMode) return;
      if (e.key === "ArrowLeft") {
        goToPrev();
      } else if (e.key === "ArrowRight") {
        goToNext();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isEditMode, goToPrev, goToNext]);

  const handleStartStreamingAnalysis = useCallback(() => {
    if (isEditMode || !timeline.boards.length) return;
    setIsAnalyzing(true);
    requestAnalysisForPly(safeCurrentPly, { force: true });
  }, [isEditMode, requestAnalysisForPly, safeCurrentPly, timeline.boards.length]);

  const handleStopAnalysis = useCallback(() => {
    stopEngineAnalysis();
  }, [stopEngineAnalysis]);

  const handleAnalyzeEditedPosition = useCallback(() => {
    if (!isEditMode) return;
    const sfenCommand = `position ${boardToSfen(displayedBoard, activeHands, currentSideToMove)}`;
    startEngineAnalysis(sfenCommand, safeCurrentPly);
    showToast({ title: "編集局面の解析を開始しました", variant: "default" });
  }, [isEditMode, displayedBoard, activeHands, currentSideToMove, safeCurrentPly, startEngineAnalysis]);

  const handleBatchAnalysisClick = useCallback(async () => {
    if (isEditMode || isBatchAnalyzing) return;
    if (!timeline.boards.length) return;
    
    const basePosition = buildUsiPositionForPly(usi, totalMoves);
    if (!basePosition?.trim()) return;

    resetBatchData(); // フックの関数を使用
    stopEngineAnalysis(); // ストリーム解析などを止める
    void runBatchAnalysis(basePosition, totalMoves, moveSequence);
  }, [isEditMode, isBatchAnalyzing, timeline.boards.length, usi, totalMoves, moveSequence, stopEngineAnalysis, resetBatchData, runBatchAnalysis]);

  const handleLoadKifu = useCallback(() => {
    setErrorMessage("");
    if (!kifuText.trim()) return;
    try {
      const newUsi = toStartposUSI(kifuText);
      if (!newUsi) throw new Error("形式を認識できませんでした");
      setUsi(newUsi);
      showToast({ title: "読み込みました", variant: "default" });
      setIsModalOpen(false);
    } catch (e) { 
        setErrorMessage(String(e)); 
        showToast({ title: "エラー", description: String(e), variant: "error" });
    }
  }, [kifuText, setUsi]);

  const handleCandidateClick = useCallback((pvStr: string) => {
      const moves = pvStr.trim().split(/\s+/);
      if (moves.length === 0) return;
      setPreviewSequence(moves);
      setPreviewStep(1);
  }, []);

  useEffect(() => {
      return () => {
          cancelBatchAnalysis();
          cleanupRealtimeAnalysis();
      };
  }, [cancelBatchAnalysis, cleanupRealtimeAnalysis]);
  
  useEffect(() => {
    setCurrentPly(0);
    setRealtimeAnalysis({});
    resetBoardEdit();
    resetExplanation();
    resetDigest();
    setPreviewSequence(null);
    setPreviewStep(0);
    stopEngineAnalysis();
    resetBatchData();
  }, [stopEngineAnalysis, usi, resetBatchData, resetDigest, resetExplanation, resetBoardEdit]);

  useEffect(() => {
    if (isEditMode) {
      clearEditHistory();
      resetExplanation();
      setPreviewSequence(null);
      setPreviewStep(0);
    } else {
      // 編集モードでない場合はここでは何もしない（継続解析のため）
      // ただし、「停止ボタン」を押したときは stopEngineAnalysis が呼ばれるのでOK
    }
  }, [isEditMode, resetExplanation, clearEditHistory]);

  const moveListEntries = useMemo(() => {
    if (!moveSequence.length) return [];
    return moveSequence.map((move, index) => {
      const ply = index + 1;
      const analysis = evalSource[ply];
      const score = analysis?.multipv?.[0]?.score;
      return {
        ply: ply,
        label: formatUsiMoveJapanese(move, timelinePlacedPieces[index] ?? [], index % 2 === 0 ? initialTurn : flipTurn(initialTurn)),
        diff: moveImpacts[ply]?.diff ?? null,
        score: score
      };
    });
  }, [initialTurn, moveImpacts, moveSequence, timelinePlacedPieces, evalSource]);
  
  const evalPoints = useMemo(
    () =>
      Array.from({ length: timeline.boards.length || totalMoves + 1 }, (_, ply) => {
        const cp = getPrimaryEvalScore(evalSource[ply]);
        return { ply, cp: typeof cp === "number" && Number.isFinite(cp) ? cp : null };
      }),
    [evalSource, timeline.boards.length, totalMoves]
  );
  const hasEvalPoints = useMemo(() => evalPoints.some((p) => typeof p.cp === "number"), [evalPoints]);

  const boardMode: BoardMode = isEditMode ? "edit" : "view";
  const topHandSide: Side = boardOrientation === "sente" ? "w" : "b";
  const bottomHandSide: Side = boardOrientation === "sente" ? "b" : "w";

  // 盤面スケーリング用のRefとState
  const boardContainerRef = useRef<HTMLDivElement>(null);
  const [boardScale, setBoardScale] = useState(1);
  const [layoutMode, setLayoutMode] = useState<"horizontal" | "vertical">("horizontal");

  useEffect(() => {
    const updateScale = () => {
        if (!boardContainerRef.current) return;
        const { clientWidth, clientHeight } = boardContainerRef.current;
        
        const availableWidth = clientWidth - 16;
        const availableHeight = clientHeight - 16;

        // Horizontal Layout Specs
        const H_WIDTH = 700;
        const H_HEIGHT = 520;
        const scaleH = Math.min(availableWidth / H_WIDTH, availableHeight / H_HEIGHT);

        // Vertical Layout Specs
        // Board width ~476 + margins ~24 = 500
        // Height: Board 476 + Hands (60*2) + Gaps ~ 650
        const V_WIDTH = 480;
        const V_HEIGHT = 630;
        const scaleV = Math.min(availableWidth / V_WIDTH, availableHeight / V_HEIGHT);

        // Decide layout
        // If vertical scale is significantly better (e.g. > 10% larger) or horizontal is too small
        if (scaleV > scaleH * 1.1) {
             setLayoutMode("vertical");
             setBoardScale(scaleV);
        } else {
             setLayoutMode("horizontal");
             setBoardScale(scaleH);
        }
    };

    // 初回実行
    updateScale();

    // ResizeObserverで監視
    const observer = new ResizeObserver(updateScale);
    if (boardContainerRef.current) {
        observer.observe(boardContainerRef.current);
    }

    return () => observer.disconnect();
  }, []);

  return (
    <div className="relative h-screen flex flex-col gap-2 p-2 text-[#1c1209] overflow-hidden bg-[#fbf7ef]">
      <div className="flex-none flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm relative z-10">
        <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => router.push("/")} className="h-9 w-9 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-full">
                <ArrowLeft className="w-5 h-5" />
            </Button>
            <div className="text-sm text-slate-500 font-medium">局面: {safeCurrentPly} / {maxPly}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setIsModalOpen(true)} className="border-slate-300 text-slate-700 h-9 text-sm cursor-pointer active:scale-95 transition-transform px-3">
            <Upload className="w-4 h-4 mr-2" /> 棋譜読み込み
          </Button>
          {!isEditMode ? (
            <>
              <Button 
                variant="outline" 
                onClick={handleBatchAnalysisClick} 
                disabled={isBatchAnalyzing} 
                className="border-slate-300 text-slate-700 h-9 text-sm relative overflow-hidden px-3"
              >
                {isBatchAnalyzing && (
                  <span 
                    className="absolute left-0 top-0 bottom-0 bg-green-100 opacity-50 transition-all duration-300" 
                    style={{ width: `${batchProgress}%` }} 
                  />
                )}
                <span className="relative z-10">
                    {isBatchAnalyzing ? `解析中 ${batchProgress}%` : "全体解析"}
                </span>
              </Button>
              {Object.keys(batchData).length > 5 && (
                  <Button
                    variant="outline"
                    onClick={() => handleGenerateGameDigest(true)}
                    disabled={isDigesting || digestCooldownLeft > 0}
                    className="border-amber-400 text-amber-700 bg-amber-50 h-9 text-sm px-3"
                  >
                      <ScrollText className="w-4 h-4 mr-2" />
                      {isDigesting ? "生成中..." : (digestCooldownLeft > 0 ? `クールダウン(残り${digestCooldownLeft}s)` : "レポート")}
                  </Button>
              )}
              <Button variant="outline" onClick={handleStartStreamingAnalysis} disabled={isAnalyzing} className="border-slate-300 text-slate-700 h-9 text-sm px-3"><Play className="w-4 h-4 mr-2" /> 検討開始</Button>
              <Button variant="default" onClick={handleGenerateExplanation} disabled={isExplaining || !hasCurrentAnalysis} className="bg-gradient-to-r from-purple-500 to-indigo-600 text-white border-none h-9 text-sm px-3 shadow-sm hover:shadow-md transition-all">{isExplaining ? "思考中..." : <><Sparkles className="w-4 h-4 mr-2" /> AI解説</>}</Button>
            </>
          ) : (
            <div className="flex items-center gap-2">
                <Button variant="outline" onClick={handleUndo} disabled={editHistory.length === 0} className="border-slate-300 text-slate-700 h-9 text-sm px-3"><RotateCcw className="w-4 h-4 mr-2" /> 1手戻す</Button>
                <Button variant="outline" onClick={handleAnalyzeEditedPosition} disabled={isAnalyzing} className="border-amber-600 text-amber-700 h-9 text-sm px-3"><Search className="w-4 h-4 mr-2" /> 現局面を解析</Button>
                <Button variant="default" onClick={handleGenerateExplanation} disabled={isExplaining || !hasCurrentAnalysis} className="bg-gradient-to-r from-purple-500 to-indigo-600 text-white border-none h-9 text-sm px-3 shadow-sm hover:shadow-md transition-all">{isExplaining ? "思考中..." : <><Sparkles className="w-4 h-4 mr-2" /> AI解説</>}</Button>
            </div>
          )}
          <Button variant="outline" onClick={handleStopAnalysis} disabled={!isAnalyzing} className="border-slate-300 text-slate-700 hover:bg-red-50 hover:text-red-600 h-9 text-sm px-3">停止</Button>
        </div>
        <div className="flex flex-wrap gap-2">
           <Button variant="outline" onClick={() => setBoardOrientation((prev) => (prev === "sente" ? "gote" : "sente"))} className="border-slate-300 text-slate-700 h-9 text-sm px-3"><ArrowLeftRight className="w-4 h-4 mr-2" />{boardOrientation === "gote" ? "後手視点" : "先手視点"}</Button>
           <Button variant="outline" onClick={() => setIsEditMode((prev) => !prev)} className={`${isEditMode ? "bg-amber-100 text-amber-800 border-amber-300" : "border-slate-300 text-slate-700"} h-9 text-sm px-3`}>{isEditMode ? <><X className="w-4 h-4 mr-2" />編集終了</> : <><Pencil className="w-4 h-4 mr-2" />編集</>}</Button>
        </div>
      </div>

      <div className="flex-1 flex flex-row gap-4 min-h-0 overflow-hidden relative z-0">
        <div className="flex-1 flex flex-col gap-4 overflow-y-auto min-w-0">
          <div ref={boardContainerRef} className="flex-1 rounded-xl border border-slate-200 bg-[#f9f8f3] p-2 shadow-md flex flex-col items-center gap-4 relative min-h-0 overflow-hidden">
            
            <div className="flex flex-col items-center justify-center w-full gap-2 mb-2 absolute top-4 left-0 right-0 z-20 pointer-events-none [&>*]:pointer-events-auto">
                {previewSequence && (
                    <div className="bg-amber-100 text-amber-800 px-4 py-1.5 rounded-full flex items-center gap-3 animate-in fade-in slide-in-from-top-2 mb-1 shadow-sm border border-amber-200">
                        <div className="flex items-center gap-1.5 font-bold text-sm">
                            <Eye className="w-4 h-4" />
                            <span>読み筋を確認中: {previewStep}手目</span>
                        </div>
                        <Button size="sm" variant="ghost" onClick={() => { setPreviewSequence(null); setPreviewStep(0); }} className="h-6 text-xs hover:bg-amber-200 px-2 text-amber-900">
                            本譜に戻る
                        </Button>
                    </div>
                )}

                <div className="flex items-center justify-center gap-4">
                    <Button variant="outline" size="icon" className="w-8 h-8 bg-white/80 backdrop-blur-sm" onClick={goToStart} disabled={navDisabled || !canGoPrev}><ChevronFirst className="w-4 h-4"/></Button>
                    <Button variant="outline" size="icon" className="w-8 h-8 bg-white/80 backdrop-blur-sm" onClick={goToPrev} disabled={navDisabled || !canGoPrev}><ChevronLeft className="w-4 h-4"/></Button>
                    <Button variant="outline" size="icon" className="w-8 h-8 bg-white/80 backdrop-blur-sm" onClick={goToNext} disabled={navDisabled || !canGoNext}><ChevronRight className="w-4 h-4"/></Button>
                    <Button variant="outline" size="icon" className="w-8 h-8 bg-white/80 backdrop-blur-sm" onClick={goToEnd} disabled={navDisabled || !canGoNext}><ChevronLast className="w-4 h-4"/></Button>
                </div>
            </div>

            <div className="flex-1 w-full h-full flex items-center justify-center">
                <div style={{ transform: `scale(${boardScale})`, transformOrigin: "center center", transition: "transform 0.1s ease-out" }}>
                    {layoutMode === "horizontal" ? (
                        <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-4 pt-12">
                            <HandsColumn 
                                side={topHandSide} 
                                hands={activeHands[topHandSide] ?? {}} 
                                orientationMode={orientationMode} 
                                align="start" 
                                isEditMode={isEditMode}
                                selectedHand={selectedHand}
                                onHandClick={handleHandClick}
                            />
                            <div className={`flex justify-center shadow-lg rounded-lg overflow-hidden border-4 transition-colors duration-300 ${previewSequence ? 'border-amber-500' : 'border-[#5d4037]'}`}>
                                <ShogiBoard
                                board={displayedBoard}
                                hands={activeHands}
                                mode={boardMode}
                                lastMove={isEditMode ? undefined : lastMoveCoords ?? undefined}
                                bestmove={bestmoveCoords}
                                orientationMode={orientationMode}
                                orientation={boardOrientation}
                                onBoardChange={isEditMode ? handleBoardEdit : undefined}
                                onHandsChange={isEditMode ? handleHandsEdit : undefined}
                                showHands={false}
                                selectedHand={selectedHand}
                                onHandClick={handleHandClick}
                                onSelectedHandChange={setSelectedHand}
                                />
                            </div>
                            <HandsColumn 
                                side={bottomHandSide} 
                                hands={activeHands[bottomHandSide] ?? {}} 
                                orientationMode={orientationMode} 
                                align="end" 
                                isEditMode={isEditMode}
                                selectedHand={selectedHand}
                                onHandClick={handleHandClick}
                            />
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center pt-4">
                            <div className={`flex justify-center shadow-lg rounded-lg overflow-hidden border-4 transition-colors duration-300 ${previewSequence ? 'border-amber-500' : 'border-[#5d4037]'}`}>
                                <ShogiBoard
                                board={displayedBoard}
                                hands={activeHands}
                                mode={boardMode}
                                lastMove={isEditMode ? undefined : lastMoveCoords ?? undefined}
                                bestmove={bestmoveCoords}
                                orientationMode={orientationMode}
                                orientation={boardOrientation}
                                onBoardChange={isEditMode ? handleBoardEdit : undefined}
                                onHandsChange={isEditMode ? handleHandsEdit : undefined}
                                showHands={true}
                                selectedHand={selectedHand}
                                onHandClick={handleHandClick}
                                onSelectedHandChange={setSelectedHand}
                                />
                            </div>
                        </div>
                    )}
                </div>
            </div>
          </div>
          
          {/* レポート表示エリア (盤面の下) */}
          {/* BioshogiPanel: データ取得は維持（digest用）、UI表示のみ非表示 */}
          {gameDigest && (
            <div className="flex-none p-4 bg-white rounded-xl border border-amber-200 shadow-sm animate-in fade-in slide-in-from-bottom-4 max-h-[300px] overflow-y-auto">
                <div className="font-bold text-amber-700 mb-2 flex items-center gap-2 border-b border-amber-100 pb-2 sticky top-0 bg-white z-10">
                    <ScrollText className="w-5 h-5 text-amber-600"/> 対局総評レポート
                </div>
                <div className="prose prose-sm max-w-none text-slate-700 leading-relaxed whitespace-pre-wrap font-sans text-sm">
                    {gameDigest}
                </div>
            </div>
          )}
        </div>

        <div className="w-[300px] flex-none flex flex-col gap-2 h-full overflow-hidden border-x border-slate-100 px-2">
            <div className="text-sm font-bold text-slate-600 flex items-center gap-2 px-1">
                <BrainCircuit className="w-4 h-4" />
                AI解析 (候補手)
                {isAnalyzing && !hasCurrentAnalysis && <span className="text-[10px] text-green-600 animate-pulse ml-auto">思考中...</span>}
            </div>
            <div className="flex-1 overflow-y-auto pr-1 space-y-2 min-h-[200px]">
                {(showArrow && currentAnalysis?.multipv?.length) ? currentAnalysis.multipv.map((pv: EngineMultipvItem, idx: number) => {
                    const currentUsi = getSubsetUSI(usi, safeCurrentPly);
                    const firstMoveUSI = pv.pv?.split(" ")[0] || "";
                    const firstMoveLabel = formatUsiMoveJapanese(firstMoveUSI, currentPlacedPieces, currentSideToMove);
                    const fullPvLabel = convertFullPvToJapanese(currentUsi, pv.pv || "");
                    const isSelected = previewSequence && pv.pv === previewSequence.join(" ");
                    
                    return (
                    <div 
                        key={`${idx}-${pv.score.cp}`} 
                        onClick={() => handleCandidateClick(pv.pv || "")} 
                        className={`group p-3 rounded-xl border cursor-pointer transition-all shadow-sm ${isSelected ? 'border-amber-500 bg-amber-50 ring-1 ring-amber-500' : 'border-slate-200 bg-white hover:border-amber-400 hover:bg-amber-50'}`}
                    >
                        <div className="flex justify-between items-center mb-2">
                            <div className="flex items-center gap-2">
                                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${idx === 0 ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>#{idx + 1}</span>
                                <span className="text-base font-bold text-slate-800">{firstMoveLabel}</span>
                            </div>
                            <span className={`text-sm font-mono font-bold ${pv.score.type === 'mate' ? 'text-rose-600' : ((pv.score.cp ?? 0) > 0 ? 'text-emerald-600' : 'text-slate-600')}`}>{formatScoreLabel(pv.score)}</span>
                        </div>
                        <div className="flex items-start gap-1 text-xs text-slate-400 group-hover:text-slate-600 bg-slate-50 p-1 rounded">
                            <ArrowRight className="w-3 h-3 mt-0.5 shrink-0" />
                            <span className="break-words leading-tight font-mono opacity-80">{fullPvLabel || pv.pv}</span>
                        </div>
                    </div>
                )}) : (
                    <div className="h-40 flex items-center justify-center text-slate-400 text-xs border-2 border-dashed border-slate-100 rounded-xl">
                        {isAnalyzing ? "解析中..." : "解析データなし"}
                    </div>
                )}
            </div>
            
            {/* AI解説エリア (候補手の下) */}
            {explanation && (
                <div className="flex-none p-3 bg-white rounded-xl border border-purple-200 shadow-sm animate-in fade-in slide-in-from-bottom-4 max-h-[40%] overflow-y-auto">
                    <div className="font-bold text-purple-700 mb-2 flex items-center gap-2 border-b border-purple-100 pb-2 sticky top-0 bg-white z-10">
                        <Sparkles className="w-4 h-4 fill-purple-100"/> 将棋仙人の解説
                    </div>
                    <div className="prose prose-sm max-w-none text-slate-700 leading-relaxed whitespace-pre-wrap font-sans text-xs">
                        {explanation}
                    </div>
                </div>
            )}
        </div>

        <div className="w-[320px] flex-none flex flex-col gap-4 h-full overflow-hidden pl-1">
            <div className="flex-1 min-h-0 shadow-md border border-slate-300 rounded-xl overflow-hidden bg-white">
                <MoveListPanel entries={moveListEntries} activePly={safeCurrentPly} onSelectPly={handlePlyChange} className="h-full border-0 rounded-none" />
            </div>
            <div className="h-[180px] min-h-[180px] shrink-0 rounded-xl border border-slate-200 bg-white p-2 shadow-sm">
                {hasEvalPoints ? (
                  <EvalGraph data={evalPoints} currentPly={safeCurrentPly} onPlyClick={handlePlyChange} />
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-slate-400">
                    解析データがありません
                  </div>
                )}
            </div>
        </div>
      </div>
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="fixed z-50 left-1/2 top-1/2 w-[90vw] max-w-[500px] -translate-x-1/2 -translate-y-1/2 rounded-xl bg-white p-0 shadow-2xl border border-slate-200 gap-0 [&>button]:hidden">
          <DialogHeader className="flex flex-row items-center justify-between border-b border-slate-100 bg-slate-50 px-4 py-3 space-y-0">
            <div className="flex flex-col gap-0.5 text-left">
                <DialogTitle className="flex items-center gap-2 text-slate-700 text-base font-bold">
                <FileText className="w-4 h-4 text-slate-500" /> 棋譜読み込み
                </DialogTitle>
                <DialogDescription className="text-slate-500 text-xs">
                KIF, CSA, USI形式、またはSFEN
                </DialogDescription>
            </div>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-400 hover:text-slate-600 hover:bg-slate-200 rounded-full" onClick={() => setIsModalOpen(false)}>
                <X className="w-4 h-4" />
            </Button>
          </DialogHeader>
          <div className="p-4 flex flex-col gap-4 bg-white">
            <Textarea 
              value={kifuText} 
              onChange={(e) => setKifuText(e.target.value)} 
              className="min-h-[200px] font-mono text-xs resize-none bg-white text-slate-900 border-slate-300 focus:border-slate-400 focus:ring-slate-200 placeholder:text-slate-400" 
              placeholder={`Example:\nposition startpos moves 7g7f 3c3d...`} 
            />
            {errorMessage && (
              <div className="text-xs text-red-600 bg-red-50 p-2 rounded border border-red-200 font-bold">
                エラー: {errorMessage}
              </div>
            )}
          </div>
          <DialogFooter className="flex items-center justify-end gap-2 border-t border-slate-100 bg-slate-50 px-4 py-3 sm:justify-end">
            <Button variant="outline" onClick={() => setIsModalOpen(false)} className="text-slate-600 border-slate-300 bg-white hover:bg-slate-50">
              キャンセル
            </Button>
            <Button onClick={handleLoadKifu} className="bg-slate-800 hover:bg-slate-700 text-white shadow-sm">
              <Upload className="w-4 h-4 mr-2" /> 読み込む
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={isReportModalOpen} onOpenChange={setIsReportModalOpen}>
        <DialogContent className="fixed z-50 left-1/2 top-1/2 w-[90vw] max-w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-xl bg-white p-0 shadow-2xl border border-slate-200 gap-0">
          <DialogHeader className="border-b border-purple-100 bg-purple-50 px-6 py-4">
            <DialogTitle className="flex items-center gap-2 text-purple-800 text-lg font-bold">
                <ScrollText className="w-5 h-5" /> 対局総評レポート
            </DialogTitle>
          </DialogHeader>
          <div className="p-6 max-h-[60vh] overflow-y-auto">
            {isDigesting ? (
                <div className="flex flex-col items-center justify-center gap-4 py-10">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
                    <p className="text-sm text-slate-500">将棋仙人が対局を振り返っています...</p>
                </div>
            ) : (
                <div className="prose prose-sm max-w-none text-slate-700 leading-relaxed whitespace-pre-wrap">
                    {digestMetaSource ? (
                      <div className="mb-2 text-xs text-slate-500">生成元: {digestMetaSource}</div>
                    ) : null}
                    {gameDigest}
                </div>
            )}
          </div>
          <DialogFooter className="border-t border-slate-100 bg-slate-50 px-6 py-3">
            <Button onClick={() => setIsReportModalOpen(false)}>閉じる</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isLearningMenuOpen} onOpenChange={setIsLearningMenuOpen}>
        <DialogContent className="fixed z-50 left-1/2 top-1/2 w-[90vw] max-w-[400px] -translate-x-1/2 -translate-y-1/2 rounded-xl bg-white p-6 shadow-2xl border border-slate-200">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-slate-800 text-lg font-bold">
              <GraduationCap className="w-6 h-6 text-indigo-600" /> 学習メニュー
            </DialogTitle>
            <DialogDescription>
              将棋の上達に役立つ機能を選択してください。
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3 mt-4">
            <Button variant="outline" className="h-14 justify-start text-base font-bold border-slate-200 hover:bg-indigo-50 hover:text-indigo-700 hover:border-indigo-200" onClick={() => { setIsLearningMenuOpen(false); setIsRoadmapOpen(true); }}>
              <BookOpen className="w-5 h-5 mr-3 text-indigo-500" /> 初心者ロードマップ
            </Button>
            <Button variant="outline" className="h-14 justify-start text-base font-bold border-slate-200 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-200" onClick={() => { setIsLearningMenuOpen(false); setIsTsumeMode(true); if(isAnalyzing) handleStopAnalysis(); }}>
              <Sparkles className="w-5 h-5 mr-3 text-rose-500" /> 実践詰将棋モード
            </Button>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsLearningMenuOpen(false)}>閉じる</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isRoadmapOpen} onOpenChange={setIsRoadmapOpen}>
        <DialogContent className="fixed z-50 left-1/2 top-1/2 w-[90vw] max-w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-xl bg-white p-0 shadow-2xl border border-slate-200">
          <DialogHeader className="border-b border-indigo-100 bg-indigo-50 px-6 py-4">
            <DialogTitle className="flex items-center gap-2 text-indigo-800 text-lg font-bold">
              <BookOpen className="w-5 h-5" /> 初心者ロードマップ
            </DialogTitle>
          </DialogHeader>
          <div className="p-6 max-h-[60vh] overflow-y-auto">
            <div className="space-y-6">
                <div className="flex gap-4">
                    <div className="flex-none w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold">1</div>
                    <div>
                        <h3 className="font-bold text-slate-800 mb-1">ルールを覚える</h3>
                        <p className="text-sm text-slate-600">駒の動き、反則、成りを覚えましょう。</p>
                    </div>
                </div>
                <div className="flex gap-4">
                    <div className="flex-none w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold">2</div>
                    <div>
                        <h3 className="font-bold text-slate-800 mb-1">1手詰を解く</h3>
                        <p className="text-sm text-slate-600">「詰み」の形を体に染み込ませましょう。毎日10問が目安です。</p>
                    </div>
                </div>
                <div className="flex gap-4">
                    <div className="flex-none w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold">3</div>
                    <div>
                        <h3 className="font-bold text-slate-800 mb-1">棒銀戦法を試す</h3>
                        <p className="text-sm text-slate-600">攻めの基本「棒銀」を使って、実際にAIと対局してみましょう。</p>
                    </div>
                </div>
                <div className="flex gap-4">
                    <div className="flex-none w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold">4</div>
                    <div>
                        <h3 className="font-bold text-slate-800 mb-1">3手詰に挑戦</h3>
                        <p className="text-sm text-slate-600">少し読みが必要になります。読みの力を鍛えましょう。</p>
                    </div>
                </div>
            </div>
          </div>
          <DialogFooter className="border-t border-slate-100 bg-slate-50 px-6 py-3">
            <Button onClick={() => setIsRoadmapOpen(false)}>閉じる</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
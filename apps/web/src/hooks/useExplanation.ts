import { useState, useCallback } from "react";
import { showToast } from "@/components/ui/toast";
import { fetchWithAuth } from "@/lib/fetchWithAuth";
import type { AnalysisCache } from "@/lib/analysisUtils";
import type { BoardMatrix, HandsState, Side } from "@/lib/board";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8787";

const flipTurn = (side: Side): Side => (side === "b" ? "w" : "b");

export type PlannerPlan = {
  flow: string;
  topic_keyword: string;
  surface_reason: string;
  deep_reason: string;
  evidence: string;
  [key: string]: unknown;
};

export type UseExplanationParams = {
  isEditMode: boolean;
  safeCurrentPly: number;
  initialTurn: Side;
  displayedBoard: BoardMatrix;
  activeHands: HandsState;
  evalSource: AnalysisCache;
  moveSequence: string[];
  timelineBoards: BoardMatrix[];
  timelineHands: HandsState[];
  moveImpacts: Record<number, { diff: number | null }>;
  boardToSfen: (board: BoardMatrix, hands: HandsState, turn: Side) => string;
  usePlanner?: boolean;
};

export type UseExplanationReturn = {
  explanation: string;
  isExplaining: boolean;
  plan: PlannerPlan | null;
  handleGenerateExplanation: () => Promise<void>;
  resetExplanation: () => void;
};

export const useExplanation = ({
  isEditMode,
  safeCurrentPly,
  initialTurn,
  displayedBoard,
  activeHands,
  evalSource,
  moveSequence,
  timelineBoards,
  timelineHands,
  moveImpacts,
  boardToSfen,
  usePlanner = false,
}: UseExplanationParams): UseExplanationReturn => {
  const [explanation, setExplanation] = useState("");
  const [isExplaining, setIsExplaining] = useState(false);
  const [plan, setPlan] = useState<PlannerPlan | null>(null);

  const handleGenerateExplanation = useCallback(async () => {
    const analyzePly = !isEditMode && safeCurrentPly > 0 ? safeCurrentPly - 1 : safeCurrentPly;

    const analysis = evalSource[analyzePly];
    if (!analysis || !analysis.bestmove) {
      showToast({ title: "先に解析を行ってください", variant: "default" });
      return;
    }

    const board = timelineBoards[analyzePly] ?? displayedBoard;
    const hands = timelineHands[analyzePly] ?? activeHands;
    const sideToMove: Side = analyzePly % 2 === 0 ? initialTurn : flipTurn(initialTurn);
    const positionSfen = `position ${boardToSfen(board, hands, sideToMove)}`;

    const userMove = !isEditMode && safeCurrentPly > 0 ? moveSequence[analyzePly] : null;

    const candidates =
      analysis.multipv
        ?.slice(0, 3)
        .map((item) => ({
          move: item.pv?.split(" ")[0] || "",
          score_cp: item.score.type === "cp" ? item.score.cp : null,
          score_mate: item.score.type === "mate" ? item.score.mate : null,
        })) ?? [];

    const deltaCp =
      !isEditMode && safeCurrentPly > 0 ? (moveImpacts[safeCurrentPly]?.diff ?? null) : null;

    // planner用: 直前最大5手
    const prevMoves = usePlanner && analyzePly > 0
      ? moveSequence.slice(Math.max(0, analyzePly - 5), analyzePly)
      : undefined;

    setIsExplaining(true);
    setExplanation("");
    setPlan(null);
    try {
      const body: Record<string, unknown> = {
        ply: analyzePly,
        sfen: positionSfen,
        candidates,
        user_move: userMove,
        delta_cp: deltaCp,
      };
      if (usePlanner) {
        body.use_planner = true;
        if (prevMoves && prevMoves.length > 0) {
          body.prev_moves = prevMoves;
        }
      }

      const res = await fetchWithAuth(`${API_BASE}/api/explain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setExplanation(data.explanation);
      if (data.plan) {
        setPlan(data.plan as PlannerPlan);
      }
    } catch {
      showToast({ title: "解説生成エラー", variant: "error" });
    } finally {
      setIsExplaining(false);
    }
  }, [
    isEditMode,
    safeCurrentPly,
    initialTurn,
    displayedBoard,
    activeHands,
    evalSource,
    moveSequence,
    timelineBoards,
    timelineHands,
    moveImpacts,
    boardToSfen,
    usePlanner,
  ]);

  const resetExplanation = useCallback(() => {
    setExplanation("");
    setPlan(null);
  }, []);

  return {
    explanation,
    isExplaining,
    plan,
    handleGenerateExplanation,
    resetExplanation,
  };
};

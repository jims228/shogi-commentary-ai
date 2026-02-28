import type { EngineAnalyzeResponse, EngineMultipvItem } from "@/lib/annotateHook";
import type { Side } from "@/lib/board";

export type AnalysisCache = Record<number, EngineAnalyzeResponse | undefined>;

export type EvalImpactCategory =
  | "good"       // 好手
  | "inaccuracy" // 疑問手
  | "mistake"    // 悪手
  | "blunder"    // 大悪手
  | "neutral"    // 普通
  | "unknown";

export type HighlightClassification = "good" | "inaccuracy" | "mistake" | "blunder";

export const THRESH = {
  good: 200,
  inaccuracy: -200,
  mistake: -350,
  blunder: -500,
} as const;

const DIFF_LABEL = {
  waiting: "解析待ち",
} as const;

export const extractCpScore = (item?: EngineMultipvItem): number | null => {
  if (!item) return null;
  if (item.score.type === "mate") {
    const mateVal = item.score.mate ?? 0;
    return mateVal >= 0 ? 30000 : -30000;
  }
  return typeof item.score.cp === "number" ? item.score.cp : null;
};

export const getPrimaryEvalScore = (payload?: EngineAnalyzeResponse): number | null => {
  if (!payload?.multipv?.length) return null;
  const bestItem = payload.multipv.find((pv) => pv.multipv === 1) ?? payload.multipv[0];
  return extractCpScore(bestItem);
};

export const classifyEvalImpact = (diff: number | null): EvalImpactCategory => {
  if (diff === null) return "unknown";
  
  if (diff >= THRESH.good) return "good";
  if (diff <= THRESH.blunder) return "blunder";
  if (diff <= THRESH.mistake) return "mistake";
  if (diff <= THRESH.inaccuracy) return "inaccuracy";
  
  return "neutral";
};

export const formatDiffLabel = (diff: number | null): string => {
  if (diff === null) return DIFF_LABEL.waiting;
  const prefix = diff > 0 ? "+" : "";
  return `${prefix}${diff}`;
};

export const isHighlightClassification = (
  value: EvalImpactCategory,
): value is HighlightClassification => ["good", "inaccuracy", "mistake", "blunder"].includes(value);

export const getImpactDescriptor = (diff: number | null) => {
  const classification = classifyEvalImpact(diff);
  return {
    classification,
    diffLabel: formatDiffLabel(diff),
    highlight: isHighlightClassification(classification),
  };
};

export type MoveImpact = {
  ply: number;
  diff: number | null;
  classification: EvalImpactCategory;
};

export const buildMoveImpacts = (
  analysisMap: AnalysisCache,
  totalMoves: number,
  initialTurn: Side
) => {
  const impacts: Record<number, { diff: number; label: string }> = {};

  let prevScore = getPrimaryEvalScore(analysisMap[0]) ?? 0;

  for (let i = 1; i <= totalMoves; i++) {
    const currentAnalysis = analysisMap[i];
    const currentScore = getPrimaryEvalScore(currentAnalysis);

    if (currentScore === null) {
      continue;
    }

    const rawDiff = currentScore - prevScore;
    
    // 手番側にとっての得失点に変換
    const turnSideDiff = (i % 2 !== 0) ? rawDiff : -rawDiff;

    const classification = classifyEvalImpact(turnSideDiff);

    let label = "";
    // ★ここが最重要: "大悪手" という文字をコードから消し去る
    if (classification === "good") label = "好手";
    else if (classification === "inaccuracy") label = "疑問手";
    else if (classification === "mistake" || classification === "blunder") label = "悪手";

    impacts[i] = { diff: turnSideDiff, label };
    
    prevScore = currentScore;
  }

  return impacts;
};
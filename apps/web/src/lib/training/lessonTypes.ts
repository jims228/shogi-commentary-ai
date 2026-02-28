import type { PieceBase } from "@/lib/sfen";

// 盤上のマス（将棋表記ベース: file=1..9, rank=1..9）
export type Square = { file: number; rank: number };

export type MoveSpec =
  | {
      kind: "move";
      from: Square;
      to: Square;
      /** 成り指定。true=成る / false=成らない / undefined=どちらでも */
      promote?: boolean;
    }
  | {
      kind: "drop";
      piece: PieceBase;
      to: Square;
    };

export type LessonStepBase = {
  id?: string;
  /** 盤面初期局面。USI "position ..." または "sfen ..." or 盤面のみSFENでも可（buildPositionFromUsiに渡すのでposition化される想定） */
  sfen: string;
  orientation?: "sente" | "gote";
};

export type GuidedSubstep = {
  id?: string;
  prompt: string;

  /** substep単位で局面を固定したい場合（既存のscriptPhases互換用） */
  sfen?: string;

  arrows?: { from?: Square; to: Square; kind?: "move" | "drop"; dir?: "up" | "down" | "left" | "right" | "hand"; hand?: "sente" | "gote" }[];
  highlights?: Square[];

  expectedMoves: MoveSpec[];
  /** correct後の遷移 */
  after?: "auto" | "nextButton";
  /** expectedMovesが空（=自動サブステップ）のときに自動遷移するまでの時間 */
  autoAdvanceMs?: number;

  /** 不正解時の軽い理由（1行） */
  wrongHint?: string;
};

export type GuidedStep = LessonStepBase & {
  type: "guided";
  title?: string;
  substeps: GuidedSubstep[];
};

export type PracticeProblem = {
  id?: string;
  sfen: string;
  question: string;
  expectedMoves: MoveSpec[];
  hints?: {
    arrows?: { from?: Square; to: Square; kind?: "move" | "drop"; dir?: "up" | "down" | "left" | "right" | "hand"; hand?: "sente" | "gote" }[];
    highlights?: Square[];
  };
  explanation?: string;
  /** よくある誤答（MVPでは表示のみ） */
  commonMistakes?: { moves: MoveSpec[]; note: string }[];
};

export type PracticeStep = LessonStepBase & {
  type: "practice";
  title?: string;
  problems: PracticeProblem[];
};

export type ReviewStep = LessonStepBase & {
  type: "review";
  title?: string;
  source: "mistakesInThisLesson" | "skillPool";
  count: number;
};

export type LessonStep = GuidedStep | PracticeStep | ReviewStep;



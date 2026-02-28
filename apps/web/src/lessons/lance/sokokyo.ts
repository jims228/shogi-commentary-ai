import type { LessonStep, Square } from "../../lib/training/lessonTypes";

const sq = (file: number, rank: number): Square => ({ file, rank });

/**
 * 底香（Lv1）
 * - TODO: 後で局面/狙いを厚くする（外部記事の転載はしない）
 */
export const LANCE_SOKOKYO_L1: LessonStep[] = [
  {
    type: "guided",
    title: "底香（Lv1）: ガイド",
    sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b 2L 1",
    orientation: "sente",
    substeps: [
      {
        prompt: "まずは形を作ろう。底香の“入口”として、ここに打ってみてね。",
        arrows: [{ to: sq(5, 5), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(5, 5)],
        expectedMoves: [{ kind: "drop", piece: "L", to: sq(5, 5) }],
        after: "auto",
        wrongHint: "まずは指定のマスに打って形を作ろう。",
      },
      {
        prompt: "（形ができた）",
        sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b 2L 1",
        expectedMoves: [],
        autoAdvanceMs: 240,
      },
      {
        prompt: "もう一度。次はここに打ってみてね。",
        arrows: [{ to: sq(5, 4), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(5, 4)],
        expectedMoves: [{ kind: "drop", piece: "L", to: sq(5, 4) }],
        after: "auto",
        wrongHint: "2回目も指定のマスに打とう。",
      },
      {
        prompt: "OK！次は練習問題（8問）へ。",
        expectedMoves: [],
        autoAdvanceMs: 450,
      },
    ],
  },
  {
    type: "practice",
    title: "底香（Lv1）: 練習",
    sfen: "position startpos",
    orientation: "sente",
    problems: [
      {
        question: "第1問：このマスに打って形を作ろう。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b 2L 1",
        expectedMoves: [{ kind: "drop", piece: "L", to: sq(5, 5) }],
        hints: {
          arrows: [{ to: sq(5, 5), kind: "drop", dir: "hand", hand: "sente" }],
          highlights: [sq(5, 5)],
        },
        explanation: "まずは“形”を作る練習。あとで局面を実戦寄りにします。",
      },
      {
        question: "第2問：このマスに打って形を作ろう。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b 2L 1",
        expectedMoves: [{ kind: "drop", piece: "L", to: sq(5, 4) }],
        hints: {
          arrows: [{ to: sq(5, 4), kind: "drop", dir: "hand", hand: "sente" }],
          highlights: [sq(5, 4)],
        },
        explanation: "まずは“形”を作る練習。あとで局面を実戦寄りにします。",
      },
      {
        question: "第3問：このマスに打って形を作ろう。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b 2L 1",
        expectedMoves: [{ kind: "drop", piece: "L", to: sq(4, 5) }],
        hints: {
          arrows: [{ to: sq(4, 5), kind: "drop", dir: "hand", hand: "sente" }],
          highlights: [sq(4, 5)],
        },
        explanation: "まずは“形”を作る練習。あとで局面を実戦寄りにします。",
      },
      {
        question: "第4問：このマスに打って形を作ろう。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b 2L 1",
        expectedMoves: [{ kind: "drop", piece: "L", to: sq(6, 5) }],
        hints: {
          arrows: [{ to: sq(6, 5), kind: "drop", dir: "hand", hand: "sente" }],
          highlights: [sq(6, 5)],
        },
        explanation: "まずは“形”を作る練習。あとで局面を実戦寄りにします。",
      },
      {
        question: "第5問：このマスに打って形を作ろう。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b 2L 1",
        expectedMoves: [{ kind: "drop", piece: "L", to: sq(4, 4) }],
        hints: {
          arrows: [{ to: sq(4, 4), kind: "drop", dir: "hand", hand: "sente" }],
          highlights: [sq(4, 4)],
        },
        explanation: "まずは“形”を作る練習。あとで局面を実戦寄りにします。",
      },
      {
        question: "第6問：このマスに打って形を作ろう。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b 2L 1",
        expectedMoves: [{ kind: "drop", piece: "L", to: sq(6, 4) }],
        hints: {
          arrows: [{ to: sq(6, 4), kind: "drop", dir: "hand", hand: "sente" }],
          highlights: [sq(6, 4)],
        },
        explanation: "まずは“形”を作る練習。あとで局面を実戦寄りにします。",
      },
      {
        question: "第7問：このマスに打って形を作ろう。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b 2L 1",
        expectedMoves: [{ kind: "drop", piece: "L", to: sq(5, 6) }],
        hints: {
          arrows: [{ to: sq(5, 6), kind: "drop", dir: "hand", hand: "sente" }],
          highlights: [sq(5, 6)],
        },
        explanation: "まずは“形”を作る練習。あとで局面を実戦寄りにします。",
      },
      {
        question: "第8問：このマスに打って形を作ろう。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b 2L 1",
        expectedMoves: [{ kind: "drop", piece: "L", to: sq(5, 3) }],
        hints: {
          arrows: [{ to: sq(5, 3), kind: "drop", dir: "hand", hand: "sente" }],
          highlights: [sq(5, 3)],
        },
        explanation: "まずは“形”を作る練習。あとで局面を実戦寄りにします。",
      },
    ],
  },
  {
    type: "review",
    title: "底香（Lv1）: 復習",
    sfen: "position startpos",
    orientation: "sente",
    source: "mistakesInThisLesson",
    count: 4,
  },
];

import type { LessonStep, Square } from "../../lib/training/lessonTypes";

const sq = (file: number, rank: number): Square => ({ file, rank });

/**
 * 割打ちの銀 Lv1（入門）
 * - “割って入る”銀打ちで、2つの駒を同時に狙う入口を作る
 * - 盤面・文章は自作（外部記事の転載はしない）
 */
export const SILVER_WARIUCHI_L1: LessonStep[] = [
  {
    type: "guided",
    title: "割打ちの銀（Lv1）: ガイド",
    // 相手の金が4三・6三に並んでいる。5四に銀を打つと両方に利く（4三/6三）
    sfen: "position sfen 4k4/9/3g1g3/9/9/9/9/9/4K4 b S 1",
    orientation: "sente",
    substeps: [
      {
        prompt: "まずは割って入ろう。5四に銀を打って、4三と6三を同時に狙う！",
        arrows: [{ to: sq(5, 4), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(5, 4), sq(4, 3), sq(6, 3)],
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(5, 4) }],
        after: "auto",
        wrongHint: "5四に銀を打つと、斜め前の4三・6三に利くよ。",
      },
      {
        prompt: "次は、どちらかを取ってみよう。5四の銀で4三を取って（成る）！",
        sfen: "position sfen 4k4/9/3g1g3/4S4/9/9/9/9/4K4 b - 1",
        arrows: [{ from: sq(5, 4), to: sq(4, 3), kind: "move" }],
        highlights: [sq(4, 3)],
        expectedMoves: [{ kind: "move", from: sq(5, 4), to: sq(4, 3), promote: true }],
        after: "auto",
        wrongHint: "5四→4三。今回は“成る”も選んでね。",
      },
      {
        prompt: "OK！割打ちの銀は“割って入って二枚を見る”のが核。次は練習！",
        sfen: "position sfen 4k4/9/3+S1g3/9/9/9/9/9/4K4 w - 1",
        expectedMoves: [],
        autoAdvanceMs: 450,
      },
    ],
  },
  {
    type: "practice",
    title: "割打ちの銀（Lv1）: 練習",
    sfen: "position startpos",
    orientation: "sente",
    problems: [
      {
        question: "この形。割打ちの銀はどこ？（4三・6三を同時に狙う）",
        sfen: "position sfen 4k4/9/3g1g3/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(5, 4) }],
        hints: { arrows: [{ to: sq(5, 4), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 4)] },
        explanation: "5四に銀を打つと、斜め前の4三と6三に利く。",
      },
      {
        question: "相手の金が3三・5三に並ぶ。割打ちは？",
        sfen: "position sfen 4k4/9/2g1g4/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(4, 4) }],
        hints: { arrows: [{ to: sq(4, 4), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(4, 4)] },
        explanation: "4四に銀を打つと、3三と5三を同時に狙える。",
      },
      {
        question: "相手の金が2四・4四に並ぶ。割打ちは？",
        sfen: "position sfen 4k4/9/9/1g1g5/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(3, 5) }],
        hints: { arrows: [{ to: sq(3, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(3, 5)] },
        explanation: "3五に銀を打つと、2四と4四に斜め前で利く。",
      },
      {
        question: "相手の銀が6三・8三に並ぶ。割打ちは？",
        sfen: "position sfen 4k4/9/5s1s1/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(7, 4) }],
        hints: { arrows: [{ to: sq(7, 4), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(7, 4)] },
        explanation: "7四の銀が6三・8三を同時に狙う。",
      },
      {
        question: "相手の金が4三・6三。割打ちを打った後、5四の銀で4三を取って（成る）",
        sfen: "position sfen 4k4/9/3g1g3/4S4/9/9/9/9/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 4), to: sq(4, 3), promote: true }],
        hints: { arrows: [{ from: sq(5, 4), to: sq(4, 3), kind: "move" }], highlights: [sq(4, 3)] },
        explanation: "割打ちの銀は“まず割って入る”。次に都合のいい方を取る。",
      },
      {
        question: "同じ局面。今度は5四の銀で6三を取って（成る）",
        sfen: "position sfen 4k4/9/3g1g3/4S4/9/9/9/9/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 4), to: sq(6, 3), promote: true }],
        hints: { arrows: [{ from: sq(5, 4), to: sq(6, 3), kind: "move" }], highlights: [sq(6, 3)] },
        explanation: "二枚を同時に見て、相手の対応次第で取る方を選べるのが強み。",
      },
    ],
  },
  {
    type: "review",
    title: "割打ちの銀（Lv1）: 復習",
    sfen: "position startpos",
    orientation: "sente",
    source: "mistakesInThisLesson",
    count: 4,
  },
];



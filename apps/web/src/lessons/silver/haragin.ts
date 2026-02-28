import type { LessonStep, Square } from "../../lib/training/lessonTypes";

const sq = (file: number, rank: number): Square => ({ file, rank });

/**
 * 腹銀 Lv1
 * - 玉の“斜め下（腹）”に銀を置いて、逃げ道を絞る/王手をかける
 * - 盤面・文章は自作
 */
export const SILVER_HARAGIN_L1: LessonStep[] = [
  {
    type: "guided",
    title: "腹銀（Lv1）: ガイド",
    // 相手玉(5一)。玉の“腹”(4二)に銀を打つと王手＆逃げ道を絞りやすい。
    sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b S 1",
    orientation: "sente",
    substeps: [
      {
        prompt: "玉の腹を狙おう。4二に銀を打って王手！",
        arrows: [{ to: sq(4, 2), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(4, 2), sq(5, 1)],
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(4, 2) }],
        after: "auto",
        wrongHint: "腹銀は、玉の斜め下（腹）に銀を置くイメージ。4二に銀。",
      },
      {
        prompt: "（腹の銀は逃げ道も絞る）",
        sfen: "position sfen 4k4/3S5/9/9/9/9/9/9/4K4 w - 1",
        expectedMoves: [],
        autoAdvanceMs: 260,
      },
      {
        prompt: "続けて圧をかけよう。4二の銀を5三へ動かして、さらに迫る。",
        sfen: "position sfen 4k4/3S5/9/9/9/9/9/9/4K4 b - 1",
        arrows: [{ from: sq(4, 2), to: sq(5, 3), kind: "move" }],
        highlights: [sq(5, 3)],
        expectedMoves: [{ kind: "move", from: sq(4, 2), to: sq(5, 3) }],
        after: "auto",
        wrongHint: "4二→5三。腹の銀を近づけて圧を強めよう。",
      },
      {
        prompt: "OK！腹銀は“斜め下に置いて絞る”。次は練習！",
        sfen: "position sfen 4k4/9/4S4/9/9/9/9/9/4K4 w - 1",
        expectedMoves: [],
        autoAdvanceMs: 450,
      },
    ],
  },
  {
    type: "practice",
    title: "腹銀（Lv1）: 練習",
    sfen: "position startpos",
    orientation: "sente",
    problems: [
      {
        question: "相手玉が5一。腹銀（斜め下）に銀を打つなら？",
        sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(4, 2) }],
        hints: { arrows: [{ to: sq(4, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(4, 2)] },
        explanation: "玉の斜め下に銀を置くと、逃げ道を絞りやすい。",
      },
      {
        question: "相手玉が5一。反対側の腹（6二）に打つなら？",
        sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(6, 2) }],
        hints: { arrows: [{ to: sq(6, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(6, 2)] },
        explanation: "腹は左右どちらでも。状況で選ぶ。",
      },
      {
        question: "相手玉が4一。腹銀は？（3二）",
        sfen: "position sfen 3k5/9/9/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(3, 2) }],
        hints: { arrows: [{ to: sq(3, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(3, 2)] },
        explanation: "玉の斜め下に銀。形で覚える。",
      },
      {
        question: "相手玉が6一。腹銀は？（7二）",
        sfen: "position sfen 5k3/9/9/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(7, 2) }],
        hints: { arrows: [{ to: sq(7, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(7, 2)] },
        explanation: "6一の斜め下は7二。",
      },
      {
        question: "相手玉が5二。腹銀は？（4三）",
        sfen: "position sfen 9/4k4/9/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(4, 3) }],
        hints: { arrows: [{ to: sq(4, 3), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(4, 3)] },
        explanation: "玉が1段下がっても、腹は斜め下。",
      },
      {
        question: "相手玉が5二。反対側の腹銀は？（6三）",
        sfen: "position sfen 9/4k4/9/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(6, 3) }],
        hints: { arrows: [{ to: sq(6, 3), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(6, 3)] },
        explanation: "腹は左右にある。盤面で選べるように。",
      },
      {
        question: "腹銀を打った後。銀を近づけて圧を強めるなら？（4二→5三）",
        sfen: "position sfen 4k4/3S5/9/9/9/9/9/9/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(4, 2), to: sq(5, 3) }],
        hints: { arrows: [{ from: sq(4, 2), to: sq(5, 3), kind: "move" }], highlights: [sq(5, 3)] },
        explanation: "腹に置いた銀は、次の一手でさらに近づけられる。",
      },
      {
        question: "確認：玉(5一)の腹（4二）に銀を打つなら？",
        sfen: "position sfen 4k4/9/9/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(4, 2) }],
        hints: { arrows: [{ to: sq(4, 2), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(4, 2)] },
        explanation: "玉の斜め下に銀。これが腹銀。",
      },
    ],
  },
  {
    type: "review",
    title: "腹銀（Lv1）: 復習",
    sfen: "position startpos",
    orientation: "sente",
    source: "mistakesInThisLesson",
    count: 4,
  },
];



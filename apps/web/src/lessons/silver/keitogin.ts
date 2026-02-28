import type { LessonStep, Square } from "../../lib/training/lessonTypes";

const sq = (file: number, rank: number): Square => ({ file, rank });

/**
 * 桂頭の銀 Lv1
 * - “桂の頭”に銀を打って、桂の逃げ場をつぶしながら攻める
 * - 盤面・文章は自作
 */
export const SILVER_KEITOGIN_L1: LessonStep[] = [
  {
    type: "guided",
    title: "桂頭の銀（Lv1）: ガイド",
    // 相手桂が5三。桂の頭(5四)に銀を打つ。
    sfen: "position sfen 4k4/9/4n4/9/9/9/9/9/4K4 b S 1",
    orientation: "sente",
    substeps: [
      {
        prompt: "桂の頭を狙おう。5四に銀を打ってね。",
        arrows: [{ to: sq(5, 4), kind: "drop", dir: "hand", hand: "sente" }],
        highlights: [sq(5, 4), sq(5, 3)],
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(5, 4) }],
        after: "auto",
        wrongHint: "“桂の頭”は桂の真上。そこに銀を置こう。",
      },
      {
        prompt: "（桂が動きにくくなる）",
        sfen: "position sfen 4k4/9/4n4/4S4/9/9/9/9/4K4 w - 1",
        expectedMoves: [],
        autoAdvanceMs: 250,
      },
      {
        prompt: "次は桂を取ろう。5四の銀で5三へ（成る）。",
        sfen: "position sfen 4k4/9/4n4/4S4/9/9/9/9/4K4 b - 1",
        arrows: [{ from: sq(5, 4), to: sq(5, 3), kind: "move" }],
        highlights: [sq(5, 3)],
        expectedMoves: [{ kind: "move", from: sq(5, 4), to: sq(5, 3), promote: true }],
        after: "auto",
        wrongHint: "5四→5三。今回は“成る”も選んでね。",
      },
      {
        prompt: "OK！桂頭の銀は“頭に置いて、動きを止める”。次は練習！",
        sfen: "position sfen 4k4/9/4+S4/9/9/9/9/9/4K4 w - 1",
        expectedMoves: [],
        autoAdvanceMs: 450,
      },
    ],
  },
  {
    type: "practice",
    title: "桂頭の銀（Lv1）: 練習",
    sfen: "position startpos",
    orientation: "sente",
    problems: [
      {
        question: "相手桂が5三。桂頭の銀はどこ？",
        sfen: "position sfen 4k4/9/4n4/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(5, 4) }],
        hints: { arrows: [{ to: sq(5, 4), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(5, 4)] },
        explanation: "桂の真上（頭）に銀を置いて、桂を動きにくくする。",
      },
      {
        question: "相手桂が3三。桂頭の銀は？",
        sfen: "position sfen 4k4/9/2n6/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(3, 4) }],
        hints: { arrows: [{ to: sq(3, 4), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(3, 4)] },
        explanation: "“桂の頭”は1つ上。3四に銀。",
      },
      {
        question: "相手桂が7三。桂頭の銀は？",
        sfen: "position sfen 4k4/9/6n2/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(7, 4) }],
        hints: { arrows: [{ to: sq(7, 4), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(7, 4)] },
        explanation: "7四に銀。桂の逃げ道をつぶしやすい。",
      },
      {
        question: "相手桂が4四。桂頭の銀は？",
        sfen: "position sfen 4k4/9/9/3n5/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(4, 5) }],
        hints: { arrows: [{ to: sq(4, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(4, 5)] },
        explanation: "桂の頭（1つ上）に銀を置こう。",
      },
      {
        question: "相手桂が6四。桂頭の銀は？",
        sfen: "position sfen 4k4/9/9/5n3/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(6, 5) }],
        hints: { arrows: [{ to: sq(6, 5), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(6, 5)] },
        explanation: "6五に銀。桂が飛びにくくなる。",
      },
      {
        question: "桂頭の銀を打った後。桂を取るなら？（5四→5三、成る）",
        sfen: "position sfen 4k4/9/4n4/4S4/9/9/9/9/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 4), to: sq(5, 3), promote: true }],
        hints: { arrows: [{ from: sq(5, 4), to: sq(5, 3), kind: "move" }], highlights: [sq(5, 3)] },
        explanation: "頭に置いて、次に取る。形で覚える。",
      },
      {
        question: "相手桂が2三。桂頭の銀は？",
        sfen: "position sfen 4k4/9/1n7/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(2, 4) }],
        hints: { arrows: [{ to: sq(2, 4), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(2, 4)] },
        explanation: "2四に銀。端でも同じ発想。",
      },
      {
        question: "相手桂が8三。桂頭の銀は？",
        sfen: "position sfen 4k4/9/7n1/9/9/9/9/9/4K4 b S 1",
        expectedMoves: [{ kind: "drop", piece: "S", to: sq(8, 4) }],
        hints: { arrows: [{ to: sq(8, 4), kind: "drop", dir: "hand", hand: "sente" }], highlights: [sq(8, 4)] },
        explanation: "8四に銀。端でも“頭”は頭。",
      },
    ],
  },
  {
    type: "review",
    title: "桂頭の銀（Lv1）: 復習",
    sfen: "position startpos",
    orientation: "sente",
    source: "mistakesInThisLesson",
    count: 4,
  },
];



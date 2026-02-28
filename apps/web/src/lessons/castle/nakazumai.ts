import type { LessonStep, Square } from "../../lib/training/lessonTypes";

const sq = (file: number, rank: number): Square => ({ file, rank });

/**
 * 中住まい（Lv1）
 * - TODO: 後で実戦に近い局面へ差し替え（外部記事の転載はしない）
 */
export const CASTLE_NAKAZUMAI_L1: LessonStep[] = [
  {
    type: "guided",
    title: "中住まい（Lv1）: ガイド",
    sfen: "position sfen 4k4/9/9/9/9/9/9/5GS2/4K4 b - 1",
    orientation: "sente",
    substeps: [
      {
        prompt: "まずは守りの形を作ろう。金を1マス動かしてね（4八→4七）。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/5GS2/4K4 b - 1",
        arrows: [{ from: sq(4, 8), to: sq(4, 7), kind: "move" }],
        highlights: [sq(4, 7)],
        expectedMoves: [{ kind: "move", from: sq(4, 8), to: sq(4, 7) }],
        after: "auto",
        wrongHint: "金を指定のマスへ。囲いは“形”を順に作るよ。",
      },
      {
        prompt: "次は銀。銀を1マス動かしてね（3八→3七）。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/5GS2/4K4 b - 1",
        arrows: [{ from: sq(3, 8), to: sq(3, 7), kind: "move" }],
        highlights: [sq(3, 7)],
        expectedMoves: [{ kind: "move", from: sq(3, 8), to: sq(3, 7) }],
        after: "auto",
        wrongHint: "銀を指定のマスへ。金銀で玉を囲う感覚を覚えよう。",
      },
      {
        prompt: "OK！次は練習（8問）へ。",
        expectedMoves: [],
        autoAdvanceMs: 450,
      },
    ],
  },
  {
    type: "practice",
    title: "中住まい（Lv1）: 練習",
    sfen: "position startpos",
    orientation: "sente",
    problems: [
      {
        question: "第1問：金を4七へ。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/5GS2/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(4, 8), to: sq(4, 7) }],
        hints: { arrows: [{ from: sq(4, 8), to: sq(4, 7), kind: "move" }], highlights: [sq(4, 7)] },
        explanation: "まずは金を近づけて、玉の周りを固める。",
      },
      {
        question: "第2問：銀を3七へ。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/5GS2/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(3, 8), to: sq(3, 7) }],
        hints: { arrows: [{ from: sq(3, 8), to: sq(3, 7), kind: "move" }], highlights: [sq(3, 7)] },
        explanation: "銀も寄せて、守りの形を作る。",
      },
      {
        question: "第3問：金を4八→5八へ（横）。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/5G3/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(4, 8), to: sq(5, 8) }],
        hints: { arrows: [{ from: sq(4, 8), to: sq(5, 8), kind: "move" }], highlights: [sq(5, 8)] },
        explanation: "金は横にも動ける。玉の近くに寄せる。",
      },
      {
        question: "第4問：金を4八→3八へ（横）。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/5G3/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(4, 8), to: sq(3, 8) }],
        hints: { arrows: [{ from: sq(4, 8), to: sq(3, 8), kind: "move" }], highlights: [sq(3, 8)] },
        explanation: "金を横に寄せて、囲いの形を作る練習。",
      },
      {
        question: "第5問：銀を3八→4七へ（斜め）。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/6S2/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(3, 8), to: sq(4, 7) }],
        hints: { arrows: [{ from: sq(3, 8), to: sq(4, 7), kind: "move" }], highlights: [sq(4, 7)] },
        explanation: "銀は斜めにも動ける。玉の近くへ寄せよう。",
      },
      {
        question: "第6問：銀を3八→2七へ（斜め）。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/6S2/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(3, 8), to: sq(2, 7) }],
        hints: { arrows: [{ from: sq(3, 8), to: sq(2, 7), kind: "move" }], highlights: [sq(2, 7)] },
        explanation: "囲いは左右どちら側にも作れる。形を覚える。",
      },
      {
        question: "第7問：金銀を寄せる前準備：金を4八→4七。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/5G3/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(4, 8), to: sq(4, 7) }],
        hints: { arrows: [{ from: sq(4, 8), to: sq(4, 7), kind: "move" }], highlights: [sq(4, 7)] },
        explanation: "囲いは“まず金から”が多い。順番を体に入れる。",
      },
      {
        question: "第8問：銀を寄せる前準備：銀を3八→3七。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/6S2/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(3, 8), to: sq(3, 7) }],
        hints: { arrows: [{ from: sq(3, 8), to: sq(3, 7), kind: "move" }], highlights: [sq(3, 7)] },
        explanation: "金の次は銀。近づけて固める。",
      },
    ],
  },
  {
    type: "review",
    title: "中住まい（Lv1）: 復習",
    sfen: "position startpos",
    orientation: "sente",
    source: "mistakesInThisLesson",
    count: 4,
  },
];

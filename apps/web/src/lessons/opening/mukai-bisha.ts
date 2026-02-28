import type { LessonStep, Square } from "../../lib/training/lessonTypes";

const sq = (file: number, rank: number): Square => ({ file, rank });

/**
 * 向かい飛車（Lv1）
 * - TODO: 後で実戦に近い局面へ差し替え（外部記事の転載はしない）
 */
export const OPENING_MUKAI_BISHA_L1: LessonStep[] = [
  {
    type: "guided",
    title: "向かい飛車（Lv1）: ガイド",
    sfen: "position sfen 4k4/9/9/9/9/9/9/2P6/4K4 b - 1",
    orientation: "sente",
    substeps: [
      {
        prompt: "まずは歩を前へ。7八の歩を7七へ。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/2P6/4K4 b - 1",
        arrows: [{ from: sq(7, 8), to: sq(7, 7), kind: "move" }],
        highlights: [sq(7, 7)],
        expectedMoves: [{ kind: "move", from: sq(7, 8), to: sq(7, 7) }],
        after: "auto",
        wrongHint: "まずは歩を1つ進めて、形を作ろう。",
      },
      {
        prompt: "次は角道を意識。角を一歩動かしてみよう（8七→7六）。",
        sfen: "position sfen 4k4/9/9/9/9/9/1B7/9/4K4 b - 1",
        arrows: [{ from: sq(8, 7), to: sq(7, 6), kind: "move" }],
        highlights: [sq(7, 6)],
        expectedMoves: [{ kind: "move", from: sq(8, 7), to: sq(7, 6) }],
        after: "auto",
        wrongHint: "角を動かしてラインを作る練習。",
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
    title: "向かい飛車（Lv1）: 練習",
    sfen: "position startpos",
    orientation: "sente",
    problems: [
      {
        question: "第1問：歩を7七へ。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/2P6/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(7, 8), to: sq(7, 7) }],
        hints: { arrows: [{ from: sq(7, 8), to: sq(7, 7), kind: "move" }], highlights: [sq(7, 7)] },
        explanation: "序盤は、まず歩を進めて形を作る。",
      },
      {
        question: "第2問：歩を7六へ（もう1つ）。",
        sfen: "position sfen 4k4/9/9/9/9/9/2P6/9/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(7, 7), to: sq(7, 6) }],
        hints: { arrows: [{ from: sq(7, 7), to: sq(7, 6), kind: "move" }], highlights: [sq(7, 6)] },
        explanation: "歩を進めて、前線を作る。",
      },
      {
        question: "第3問：角を動かす（8七→7六）。",
        sfen: "position sfen 4k4/9/9/9/9/9/1B7/9/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(8, 7), to: sq(7, 6) }],
        hints: { arrows: [{ from: sq(8, 7), to: sq(7, 6), kind: "move" }], highlights: [sq(7, 6)] },
        explanation: "角道を通す意識を持とう。",
      },
      {
        question: "第4問：角を別のマスへ（8七→6五）。",
        sfen: "position sfen 4k4/9/9/9/9/9/1B7/9/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(8, 7), to: sq(6, 5) }],
        hints: { arrows: [{ from: sq(8, 7), to: sq(6, 5), kind: "move" }], highlights: [sq(6, 5)] },
        explanation: "角は斜めのラインで働く。",
      },
      {
        question: "第5問：飛車を前へ（5八→5七）。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/4R4/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 8), to: sq(5, 7) }],
        hints: { arrows: [{ from: sq(5, 8), to: sq(5, 7), kind: "move" }], highlights: [sq(5, 7)] },
        explanation: "大駒は“ライン”を作る意識。",
      },
      {
        question: "第6問：飛車を横へ（5八→6八）。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/4R4/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 8), to: sq(6, 8) }],
        hints: { arrows: [{ from: sq(5, 8), to: sq(6, 8), kind: "move" }], highlights: [sq(6, 8)] },
        explanation: "振り飛車の“振る”感覚の入口。",
      },
      {
        question: "第7問：飛車を横へ（5八→4八）。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/4R4/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(5, 8), to: sq(4, 8) }],
        hints: { arrows: [{ from: sq(5, 8), to: sq(4, 8), kind: "move" }], highlights: [sq(4, 8)] },
        explanation: "飛車は横にも動ける。",
      },
      {
        question: "第8問：基本の確認：歩を1つ進める（7八→7七）。",
        sfen: "position sfen 4k4/9/9/9/9/9/9/2P6/4K4 b - 1",
        expectedMoves: [{ kind: "move", from: sq(7, 8), to: sq(7, 7) }],
        hints: { arrows: [{ from: sq(7, 8), to: sq(7, 7), kind: "move" }], highlights: [sq(7, 7)] },
        explanation: "まずは“形”。1手ずつ積み上げる。",
      },
    ],
  },
  {
    type: "review",
    title: "向かい飛車（Lv1）: 復習",
    sfen: "position startpos",
    orientation: "sente",
    source: "mistakesInThisLesson",
    count: 4,
  },
];
